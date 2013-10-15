from boto import ec2
import time
import json
from os import path

start = time.time()

config_file = open(path.dirname(path.abspath(__file__)) + '/credentials.json', 'r')
config = json.load(config_file)

for account_config in config:
    print("Backing up account %s" % account_config['name'])
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

print("Done in %.1fs" % (time.time() - start))
