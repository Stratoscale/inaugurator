from inaugurator import sh
import contextlib


class Mount:
    _ROOT_MOUNT_POINT = "/destRoot"
    _BOOT_MOUNT_POINT = "/destBoot"

    def __init__(self, targetDevice):
        self._bootPartition = "%s1" % (targetDevice,)
        self._rootPartition = "%s2" % (targetDevice,)

    def rootPartition(self):
        return self._rootPartition

    def bootPartition(self):
        return self._bootPartition

    @contextlib.contextmanager
    def mountRoot(self):
        sh.run("/usr/sbin/busybox mkdir -p %s" % self._ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -t ext4 -o noatime,data=writeback %s %s" % (
            self._rootPartition, self._ROOT_MOUNT_POINT))
        yield self._ROOT_MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s" % self._ROOT_MOUNT_POINT)

    @contextlib.contextmanager
    def mountBoot(self):
        sh.run("/usr/sbin/busybox mkdir -p %s" % self._BOOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -t ext4 %s %s" % (self._bootPartition, self._BOOT_MOUNT_POINT))
        yield self._BOOT_MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s" % self._BOOT_MOUNT_POINT)
