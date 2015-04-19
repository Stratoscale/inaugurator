import os
import contextlib
import time
from inaugurator import sh


class Cdrom:
    _MOUNT_POINT = "/sourceCdrom"

    def __init__(self):
        self._device = self._findDevice()

    @contextlib.contextmanager
    def mount(self):
        with self._mount(self._device):
            yield self._MOUNT_POINT

    @contextlib.contextmanager
    def _mount(self, device):
        if not os.path.isdir(self._MOUNT_POINT):
            os.makedirs(self._MOUNT_POINT)
        sh.run("busybox modprobe isofs")
        sh.run("/usr/sbin/busybox mount -t iso9660 -o ro %s %s" % (
            device, self._MOUNT_POINT))
        yield
        sh.run("/usr/sbin/busybox umount %s" % self._MOUNT_POINT)

    def _findDevice(self):
        sh.run("busybox modprobe sr_mod")
        sh.run("busybox modprobe isofs")
        for i in xrange(10):
            try:
                return self._findDeviceOnce()
            except:
                time.sleep(1)
                sh.run("/usr/sbin/busybox mdev -s")
        return self._findDeviceOnce()

    def _findDeviceOnce(self):
        for letter in ['0', '1', '2']:
            candidate = "/dev/sr%s" % letter
            if not os.path.exists(candidate):
                continue
            try:
                self._mount(candidate)
            except:
                continue
            return candidate
        raise Exception("Unable to find a device that looks like a the CDROM")
