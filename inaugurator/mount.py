from inaugurator import sh
from inaugurator import partitiontable
import contextlib
import logging


class Mount:
    ROOT_MOUNT_POINT = "/destRoot"
    _BOOT_MOUNT_POINT = "/destBoot"
    _EFI_MOUNT_POINT = "/destBoot/efi"

    def __init__(self):
        self._bootPartition = None
        self._swapPartition = "/dev/%s/swap" % partitiontable.PartitionTable.VOLUME_GROUP
        self._rootPartition = "/dev/%s/root" % partitiontable.PartitionTable.VOLUME_GROUP
        self._efiPartition = None

    def setEfiPartitionPath(self, partitionPath):
        self._efiPartition = partitionPath

    def rootPartition(self):
        return self._rootPartition

    def bootPartition(self):
        return self._bootPartition

    def setBootPartitionPath(self, partitionPath):
        self._bootPartition = partitionPath

    def swapPartition(self):
        return self._swapPartition

    @contextlib.contextmanager
    def mountRoot(self):
        self._correctEXT4Errors(self._rootPartition)
        sh.run("/usr/sbin/busybox mkdir -p %s" % self.ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -t ext4 -o noatime,data=writeback %s %s" % (
            self._rootPartition, self.ROOT_MOUNT_POINT))
        yield self.ROOT_MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s" % self.ROOT_MOUNT_POINT)

    @contextlib.contextmanager
    def mountBoot(self):
        self._correctEXT4Errors(self._bootPartition)
        sh.run("/usr/sbin/busybox mkdir -p %s" % self._BOOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -t ext4 %s %s" % (self._bootPartition, self._BOOT_MOUNT_POINT))
        if self._efiPartition:
            sh.run("/usr/sbin/busybox mkdir -p %s" % self._EFI_MOUNT_POINT)
        yield self._BOOT_MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s" % self._BOOT_MOUNT_POINT)

    @contextlib.contextmanager
    def mountBootInsideRoot(self):
        sh.run("/usr/sbin/busybox mount -t ext4 %s %s/boot" % (
            self._bootPartition, self.ROOT_MOUNT_POINT))
        if self._efiPartition:
            sh.run("/usr/sbin/busybox mv {0}/boot/efi/EFI {0}".format(self.ROOT_MOUNT_POINT))
            sh.run("/usr/sbin/busybox modprobe vfat")
            sh.run("/usr/sbin/busybox mount -t vfat %s %s/boot/efi" % (
                self._efiPartition, self.ROOT_MOUNT_POINT))
            sh.run("/usr/sbin/busybox mv {0}/EFI {0}/boot/efi".format(self.ROOT_MOUNT_POINT))
        sh.run("/usr/sbin/busybox cp -a /dev/* %s/dev/" % self.ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -t proc none %s/proc" % self.ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox mount -o rbind /sys %s/sys" % self.ROOT_MOUNT_POINT)
        yield self.ROOT_MOUNT_POINT
        sh.run("/usr/sbin/busybox umount %s/proc" % self.ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox umount %s/sys" % self.ROOT_MOUNT_POINT)
        if self._efiPartition:
            sh.run("/usr/sbin/busybox umount %s/boot/efi" % self.ROOT_MOUNT_POINT)
        sh.run("/usr/sbin/busybox umount %s/boot" % self.ROOT_MOUNT_POINT)

    def _correctEXT4Errors(self, device):
        try:
            sh.run("/usr/sbin/fsck.ext4 -y -f %s" % device)
        except:
            logging.exception(
                "fsck returned with errors, this most likely means it has corrected issues on disk."
                " attepting to continue"
            )
