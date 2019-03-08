from boto import ec2, ses
from boto.ses.connection import SESConnection
import time
import json
from os import path
import sys

start = time.time()

config_file = open(path.dirname(path.abspath(__file__)) + '/credentials.json', 'r')
config = json.load(config_file)

ses_conn = None

all_regions = [r for r in ec2.regions() if 'us-gov' not in r.name and 'cn-' not in r.name]

exceptions = []
monitoring = config.get('monitoring')
for account_config in config.get('accounts'):
    print("Backing up account %s" % account_config['name'])
    for region in all_regions:
        try:
            print(" Region %s" % region.name)
            conn = region.connect(
                aws_access_key_id=account_config['access_key_id'],
                aws_secret_access_key=account_config['secret_access_key']
            )
            for volume in conn.get_all_volumes():
                print("  Create snapshot for %s" % volume.id)
                volume.create_snapshot()

            print("  Trimming snapshots")
            conn.trim_snapshots(hourly_backups=0, daily_backups=7, weekly_backups=4)
        except Exception as e:
            print('>>> Error encountered, continuing backups: {}'.format(repr(e)))
            exceptions.append(e)
            if ses_conn is None:
                ses_conn = SESConnection(
                    aws_access_key_id=monitoring.get('access_key_id'),
                    aws_secret_access_key=monitoring.get('secret_access_key'),
                    region=[r for r in ses.regions() if r.name == monitoring.get('region')][0]
                )
            ses_conn.send_email(
                source=monitoring.get('sender'),
                to_addresses=[monitoring.get('receiver')],
                subject='Backup AWS Error',
                body='Error in backup EC2 [{0}]: {1}'.format(account_config['name'], repr(e))
            )

print("Done in %.1fs" % (time.time() - start))
sys.exit(len(exceptions))
