from boto import ec2
import time
import sys


start = time.time()

ses_conn = None

all_regions = [r for r in ec2.regions() if 'us-gov' not in r.name and 'cn-' not in r.name]

exceptions = []
# TODO: Display implicit profile name?
print("Backing up account")
for region in all_regions:
    try:
        print(" Region %s" % region.name)
        conn = region.connect()
        has_volume = False
        for volume in conn.get_all_volumes():
            print("  Create snapshot for %s" % volume.id)
            volume.create_snapshot()
            has_volume = True

        if has_volume:
            print("  Trimming snapshots")
            conn.trim_snapshots(hourly_backups=0, daily_backups=7, weekly_backups=4)
    except Exception as e:
        print('>>> Error encountered, continuing backups: {}'.format(repr(e)))
        exceptions.append(e)

print("Done in %.1fs" % (time.time() - start))
sys.exit(len(exceptions))
