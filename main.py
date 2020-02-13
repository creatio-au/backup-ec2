import boto
from boto import ec2
import time
from datetime import datetime, timedelta


# Need some changes to work with latest AWS (ms times)
# See https://github.com/boto/boto/issues/3869
from boto.exception import EC2ResponseError


def trim_snapshots(connection, hourly_backups=8, daily_backups=7,
                   weekly_backups=4, monthly_backups=True):
    """
    Trim excess snapshots, based on when they were taken. More current
    snapshots are retained, with the number retained decreasing as you
    move back in time.

    If ebs volumes have a 'Name' tag with a value, their snapshots
    will be assigned the same tag when they are created. The values
    of the 'Name' tags for snapshots are used by this function to
    group snapshots taken from the same volume (or from a series
    of like-named volumes over time) for trimming.

    For every group of like-named snapshots, this function retains
    the newest and oldest snapshots, as well as, by default,  the
    first snapshots taken in each of the last eight hours, the first
    snapshots taken in each of the last seven days, the first snapshots
    taken in the last 4 weeks (counting Midnight Sunday morning as
    the start of the week), and the first snapshot from the first
    day of each month forever.

    :type hourly_backups: int
    :param hourly_backups: How many recent hourly backups should be saved.

    :type daily_backups: int
    :param daily_backups: How many recent daily backups should be saved.

    :type weekly_backups: int
    :param weekly_backups: How many recent weekly backups should be saved.

    :type monthly_backups: int
    :param monthly_backups: How many monthly backups should be saved. Use True for no limit.
    """

    # This function first builds up an ordered list of target times
    # that snapshots should be saved for (last 8 hours, last 7 days, etc.).
    # Then a map of snapshots is constructed, with the keys being
    # the snapshot / volume names and the values being arrays of
    # chronologically sorted snapshots.
    # Finally, for each array in the map, we go through the snapshot
    # array and the target time array in an interleaved fashion,
    # deleting snapshots whose start_times don't immediately follow a
    # target time (we delete a snapshot if there's another snapshot
    # that was made closer to the preceding target time).

    now = datetime.utcnow()
    last_hour = datetime(now.year, now.month, now.day, now.hour)
    last_midnight = datetime(now.year, now.month, now.day)
    last_sunday = datetime(now.year, now.month, now.day) - timedelta(days=(now.weekday() + 1) % 7)
    start_of_month = datetime(now.year, now.month, 1)

    target_backup_times = []

    # there are no snapshots older than 1/1/2007
    oldest_snapshot_date = datetime(2007, 1, 1)

    for hour in range(0, hourly_backups):
        target_backup_times.append(last_hour - timedelta(hours=hour))

    for day in range(0, daily_backups):
        target_backup_times.append(last_midnight - timedelta(days=day))

    for week in range(0, weekly_backups):
        target_backup_times.append(last_sunday - timedelta(weeks=week))

    one_day = timedelta(days=1)
    monthly_snapshots_added = 0
    while (start_of_month > oldest_snapshot_date and
           (monthly_backups is True or
            monthly_snapshots_added < monthly_backups)):
        # append the start of the month to the list of
        # snapshot dates to save:
        target_backup_times.append(start_of_month)
        monthly_snapshots_added += 1
        # there's no timedelta setting for one month, so instead:
        # decrement the day by one, so we go to the final day of
        # the previous month...
        start_of_month -= one_day
        # ... and then go to the first day of that previous month:
        start_of_month = datetime(start_of_month.year,
                                  start_of_month.month, 1)

    temp = []

    for t in target_backup_times:
        if temp.__contains__(t) == False:
            temp.append(t)

    # sort to make the oldest dates first, and make sure the month start
    # and last four week's start are in the proper order
    target_backup_times = sorted(temp)

    # get all the snapshots, sort them by date and time, and
    # organize them into one array for each volume:
    all_snapshots = connection.get_all_snapshots(owner='self')
    all_snapshots.sort(key=lambda x: x.start_time)
    snaps_for_each_volume = {}
    for snap in all_snapshots:
        # the snapshot name and the volume name are the same.
        # The snapshot name is set from the volume
        # name at the time the snapshot is taken
        volume_name = snap.tags.get('Name')
        if volume_name:
            # only examine snapshots that have a volume name
            snaps_for_volume = snaps_for_each_volume.get(volume_name)
            if not snaps_for_volume:
                snaps_for_volume = []
                snaps_for_each_volume[volume_name] = snaps_for_volume
            snaps_for_volume.append(snap)

    # Do a running comparison of snapshot dates to desired time
    #periods, keeping the oldest snapshot in each
    # time period and deleting the rest:
    for volume_name in snaps_for_each_volume:
        snaps = snaps_for_each_volume[volume_name]
        snaps = snaps[:-1] # never delete the newest snapshot
        time_period_number = 0
        snap_found_for_this_time_period = False
        for snap in snaps:
            check_this_snap = True
            while check_this_snap and time_period_number < target_backup_times.__len__():
                snap_date = datetime.strptime(snap.start_time,
                                              '%Y-%m-%dT%H:%M:%S.%fZ')
                if snap_date < target_backup_times[time_period_number]:
                    # the snap date is before the cutoff date.
                    # Figure out if it's the first snap in this
                    # date range and act accordingly (since both
                    #date the date ranges and the snapshots
                    # are sorted chronologically, we know this
                    #snapshot isn't in an earlier date range):
                    if snap_found_for_this_time_period == True:
                        if not snap.tags.get('preserve_snapshot'):
                            # as long as the snapshot wasn't marked
                            # with the 'preserve_snapshot' tag, delete it:
                            try:
                                connection.delete_snapshot(snap.id)
                                boto.log.info('Trimmed snapshot %s (%s)' % (snap.tags['Name'], snap.start_time))
                            except EC2ResponseError:
                                boto.log.error('Attempt to trim snapshot %s (%s) failed. Possible result of a race condition with trimming on another server?' % (snap.tags['Name'], snap.start_time))
                        # go on and look at the next snapshot,
                        #leaving the time period alone
                    else:
                        # this was the first snapshot found for this
                        #time period. Leave it alone and look at the
                        # next snapshot:
                        snap_found_for_this_time_period = True
                    check_this_snap = False
                else:
                    # the snap is after the cutoff date. Check it
                    # against the next cutoff date
                    time_period_number += 1
                    snap_found_for_this_time_period = False

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
            trim_snapshots(conn, hourly_backups=0, daily_backups=7, weekly_backups=4)
    except Exception as e:
        print(f">>> Error encountered, continuing backups: {e}")
        exceptions.append(e)

print("Done in %.1fs" % (time.time() - start))
if len(exceptions) > 0:
    raise exceptions[0]
