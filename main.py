from boto import ec2
import time

start = time.time()

for region in ec2.regions():
    conn = region.connect(
        aws_access_key_id='AKIAJVM44OMLT75WWKRQ',
        aws_secret_access_key='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'
    )

    volumes = conn.get_all_volumes()

    print("Backing up region %s, %s volumes found" % (region.name, len(volumes)))
    for volume in volumes:
        print(" Create snapshot for %s" % volume.id)
        volume.create_snapshot()

    conn.trim_snapshots(hourly_backups=0, daily_backups=7, weekly_backups=4)

print("Done in %.1fs" % (time.time() - start))