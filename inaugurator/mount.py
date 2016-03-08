from inaugurator import sh
from inaugurator import partitiontable
import contextlib
import logging


class Mount:
    _ROOT_MOUNT_POINT = "/destRoot"
    _BOOT_MOUNT_POINT = "/destBoot"
    _OSMOSIS_CACHE_MOUNT_POINT = "/osmosisCache"

    def __init__(self, targetDevice):
        self._bootPartition = "%s2" % targetDevice
        self._swapPartition = "/dev/%s/swap" % partitiontable.PartitionTable.VOLUME_GROUP
        self._rootPartition = "/dev/%s/root" % partitiontable.PartitionTable.VOLUME_GROUP
        self._osmosisCachePartition = "/dev/%s/osmosis-cache" % partitiontable.PartitionTable.VOLUME_GROUP

    def rootPartition(self):
        return self._rootPartition

    def bootPartition(self):
        return self._bootPartition

    def swapPartition(self):
        return self._swapPartition

    @contextlib.contextmanager
    def _mountPartition(self, partitionPath, mountPoint, optimizePerformance=False):
        self._correctEXT4Errors(partitionPath)
        sh.run("/usr/sbin/busybox mkdir -p %s" % mountPoint)
        if optimizePerformance:
            options = "-o noatime,data=writeback"
        else:
            options = ""
        sh.run("/usr/sbin/busybox mount -t ext4 %s %s %s" % (options, partitionPath, mountPoint))
        yield mountPoint
        sh.run("/usr/sbin/busybox umount %s" % mountPoint)

    def mountRoot(self):
        return self._mountPartition(self._rootPartition, self._ROOT_MOUNT_POINT, optimizePerformance=True)

    def mountBoot(self):
        return self._mountPartition(self._bootPartition, self._BOOT_MOUNT_POINT)

    def mountOsmosisCache(self):
        return self._mountPartition(self._osmosisCachePartition,
                                    self._OSMOSIS_CACHE_MOUNT_POINT,
                                    optimizePerformance=True)

    @contextlib.contextmanager
    def mountBootInsideRoot(self):
        sh.run("/usr/sbin/busybox mount -t ext4 %s %s/boot" % (
            self._bootPartition, self._ROOT_MOUNT_POINT))
        sh.run("/usr/sbin/busybox cp -a /dev/* %s/dev/" % self._ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -t proc none %s/proc" % self._ROOT_MOUNT_POINT)
        yield self._ROOT_MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s/proc" % self._ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox umount %s/boot" % self._ROOT_MOUNT_POINT)

    def _correctEXT4Errors(self, device):
        try:
            sh.run("/usr/sbin/fsck.ext4 -y -f %s" % device)
        except:
            logging.exception(
                "fsck returned with errors, this most likely means it has corrected issues on disk."
                " attepting to continue")
