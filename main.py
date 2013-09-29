from boto import ec2
import time
import ConfigParser

start = time.time()

config = ConfigParser.ConfigParser()
config.read('credentials.ini')
if not config.has_option('default', 'access_key_id'):
    raise Exception('No access_key_id option')

if not config.has_option('default', 'secret_access_key'):
    raise Exception('No secret_access_key option')

for region in ec2.regions():
    conn = region.connect(
        aws_access_key_id=config.get('default', 'access_key_id'),
        aws_secret_access_key=config.get('default', 'secret_access_key')
    )

    volumes = conn.get_all_volumes()

    print("Backing up region %s, %s volumes found" % (region.name, len(volumes)))
    for volume in volumes:
        print(" Create snapshot for %s" % volume.id)
        volume.create_snapshot()

    conn.trim_snapshots(hourly_backups=0, daily_backups=7, weekly_backups=4)

print("Done in %.1fs" % (time.time() - start))