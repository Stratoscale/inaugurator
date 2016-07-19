import os
import contextlib
import time
import glob
import re
import logging
from inaugurator import sh


class DiskOnKey:
    _MOUNT_POINT = "/sourceDOK"
    DEVICES_REGEX_PAT = "(/dev/sd[a-z]{1,}(?![0-9]))$"

    def __init__(self, expectedLabel=None):
        self._expectedLabel = expectedLabel
        self._device = self._findDevice()
        self._partiton = self._device + "1"

    @contextlib.contextmanager
    def mount(self):
        if os.path.exists(self._MOUNT_POINT):
            assert os.path.isdir(self._MOUNT_POINT)
        else:
            os.makedirs(self._MOUNT_POINT)
        sh.run("busybox modprobe vfat")
        sh.run("/usr/sbin/busybox mount -t vfat -o ro %s %s" % (
            self._partiton, self._MOUNT_POINT))
        try:
            yield self._MOUNT_POINT
        finally:
            sh.run("/usr/sbin/busybox umount %s" % self._MOUNT_POINT)

    def _findDevice(self):
        sh.run("busybox modprobe usb_storage")
        for i in xrange(10):
            try:
                return self._findDeviceOnce()
            except:
                time.sleep(1)
                sh.run("/usr/sbin/busybox mdev -s")
        return self._findDeviceOnce()

    def _findDeviceOnce(self):
        if self._expectedLabel is None:
            return self._findDeviceWithoutLabel()
        return self._findDeviceUsingExpectedLabel()

    def _findDeviceWithoutLabel(self):
        for device in self._getAllDevices():
            if self._deviceSizeGB(device) > 32:
                continue
            return device
        raise Exception("Unable to find a device that looks like a DOK")

    def _findDeviceUsingExpectedLabel(self):
        for device in self._getAllDevices():
            devicePartition = device + "1"
            if not os.path.exists(devicePartition):
                logging.info("Will not check device %s for installation since it does not"
                             "contain any partitions." % (device,))
                continue
            try:
                content = sh.run("dosfslabel %s" % (devicePartition,))
            except Exception as ex:
                logging.warning("Failed running dosfslabel on device '%s': '%s'" %
                                (devicePartition, str(ex)))
                continue
            if self._expectedLabel in content:
                return device
        raise Exception("Couldn't find device with '%s' label" % (self._expectedLabel,))

    def _deviceSizeGB(self, device):
        return int(sh.run("sfdisk -s %s" % device)) / 1024 / 1024

    @classmethod
    def _getAllDevices(cls):
        devices = glob.glob("/dev/sd*")
        for device in devices:
            if re.match(cls.DEVICES_REGEX_PAT, device):
                yield device
