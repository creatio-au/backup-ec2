from boto import ec2, ses
from boto.ses.connection import SESConnection
import time
import json
from os import path

start = time.time()

config_file = open(path.dirname(path.abspath(__file__)) + '/credentials.json', 'r')
config = json.load(config_file)

monitoring = config.get('monitoring')
for account_config in config.get('accounts'):
    print("Backing up account %s" % account_config['name'])
    try:
        for region in ec2.regions():
            conn = region.connect(
                aws_access_key_id=account_config['access_key_id'],
                aws_secret_access_key=account_config['secret_access_key']
            )

            volumes = conn.get_all_volumes()

            print("Backing up region %s, %s volumes found" % (region.name, len(volumes)))
            for volume in volumes:
                print(" Create snapshot for %s" % volume.id)
                volume.create_snapshot()

            conn.trim_snapshots(hourly_backups=0, daily_backups=7, weekly_backups=4)
    except Exception as e:
        print('Error encountered, continuing backups: {}'.format(repr(e)))
        conn = SESConnection(
            aws_access_key_id=monitoring.get('access_key_id'),
            aws_secret_access_key=monitoring.get('secret_access_key'),
            region=[r for r in ses.regions() if r.name == monitoring.get('region')][0]
        )
        r = conn.send_email(
            source=monitoring.get('sender'),
            to_addresses=[monitoring.get('receiver')],
            subject='Backup AWS Error',
            body='Error in backup AWS: {}'.format(repr(e))
        )
        print('response: ' + repr(r))

print("Done in %.1fs" % (time.time() - start))
