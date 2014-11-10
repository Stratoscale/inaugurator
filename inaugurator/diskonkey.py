import os
import contextlib
import time
from inaugurator import sh


class DiskOnKey:
    _MOUNT_POINT = "/sourceDOK"

    def __init__(self):
        self._device = self._findDevice()
        self._partiton = self._device + "1"

    @contextlib.contextmanager
    def mount(self):
        os.makedirs(self._MOUNT_POINT)
        sh.run("busybox modprobe vfat")
        sh.run("/usr/sbin/busybox mount -t vfat -o ro %s %s" % (
            self._partiton, self._MOUNT_POINT))
        yield self._MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s" % self._MOUNT_POINT)

    def _findDevice(self):
        for i in xrange(10):
            try:
                return self._findDeviceOnce()
            except:
                time.sleep(1)
                sh.run("/usr/sbin/busybox mdev -s")
        return self._findDeviceOnce()

    def _findDeviceOnce(self):
        for letter in ['a', 'b', 'c', 'd', 'e', 'f']:
            candidate = "/dev/sd%s" % letter
            if not os.path.exists(candidate):
                continue
            if self._deviceSizeGB(candidate) > 32:
                continue
            return candidate
        raise Exception("Unable to find a device that looks like a DOK")

    def _deviceSizeGB(self, device):
        return int(sh.run("sfdisk -s %s" % device)) / 1024 / 1024
