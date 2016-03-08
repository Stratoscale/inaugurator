import os
import re
import unittest
import StringIO
import inaugurator
from inaugurator.partitiontable import PartitionTable
from inaugurator import sh


class Test(unittest.TestCase):
    BIOS_BOOT_PARTITION_SIZE = 2
    BOOT_PARTITION_SIZE = 256
    LVM_PARTITION_NR = None
    LVM_PARTITION = None
    _NR_MBS_IN_GB = 1024
    _BLOCK_SIZE = 512
    _NR_BYTES_IN_GB = None

    @classmethod
    def setUpClass(cls):
        cls.LVM_PARTITION_NR = 3
        cls.LVM_PARTITION = "/dev/sda%d" % (cls.LVM_PARTITION_NR,)
        NR_BYTES_IN_MB = 1024 ** 2
        cls._NR_BYTES_IN_GB = cls._NR_MBS_IN_GB * NR_BYTES_IN_MB

    def setUp(self):
        self.expectedCommands = []
        sh.run = self.runShell
        inaugurator.partitiontable.os.path.exists = self.fakeOSExists
        self.diskSizeGB = 128
        self.fakeExistingPaths = set()
        inaugurator.partitiontable.open = self._readSizeMock

    def _readSizeMock(self, name, *args, **kwargs):
        sizeInBlocks = int(float(self.diskSizeGB) * self._NR_BYTES_IN_GB / self._BLOCK_SIZE)

        class FileLikeObject:
            @staticmethod
            def read():
                return str(sizeInBlocks)

            def __enter__(self, *args, **kwargs):
                return FileLikeObject()

            def __exit__(self, *args, **kwargs):
                pass

        return FileLikeObject()

    def runShell(self, command):
        foundList = [x for x in self.expectedCommands if x[0] == command]
        if len(foundList) == 0:
            msg = "Command '%s' is not in expected commands." % command
            if self.expectedCommands:
                msg += " Expected Command: %s" % (self.expectedCommands[0][0],)
            raise Exception(msg)
        found = foundList[0]
        self.expectedCommands.remove(found)
        result = found[1]
        if isinstance(result, str):
            print "Expected command run:", found
            output = result
        else:
            output = result()
        return output

    def test_ParsePartitionTable(self):
        self.expectedCommands.append(('parted -s -m /dev/sda unit MB print',
                                      self._getPartitionTableInMachineFormat(diskSizeGB=self.diskSizeGB)))
        tested = PartitionTable("/dev/sda")
        parsed = tested.parsePartitionTable()
        self.assertEquals(len(parsed), 3)
        self.assertEquals(parsed[0]['device'], '/dev/sda1')
        self.assertEquals(parsed[0]['sizeMB'], 2)
        self.assertEquals(parsed[0]['fs'], "")
        self.assertEquals(parsed[0]['flags'], "bios_grub")
        self.assertEquals(parsed[1]['device'], '/dev/sda2')
        self.assertEquals(parsed[1]['sizeMB'], self.BOOT_PARTITION_SIZE)
        self.assertEquals(parsed[1]['fs'], "ext4")
        self.assertEquals(parsed[1]['flags'], "boot")
        self.assertEquals(parsed[2]['device'], self.LVM_PARTITION)
        self.assertEquals(parsed[2]['sizeMB'],
                          self.diskSizeGB * self._NR_MBS_IN_GB -
                          (self.BIOS_BOOT_PARTITION_SIZE + self.BOOT_PARTITION_SIZE))
        self.assertEquals(parsed[2]['fs'], "")
        self.assertEquals(parsed[2]['flags'], "lvm")
        self.assertEquals(len(self.expectedCommands), 0)

    def test_ParseLVM(self):
        example = "\n".join([
            "  PV        VG    Fmt  Attr PSize  PFree ",
            "  %(lvmPartition)s dummy lvm2 a--  60.00m 60.00m"
            ""]) % dict(lvmPartition=self.LVM_PARTITION)
        self.expectedCommands.append(('lvm pvscan --cache %(lvmPartition)s' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        self.expectedCommands.append(('lvm pvdisplay --units m --columns %(lvmPartition)s' %
                                      dict(lvmPartition=self.LVM_PARTITION),
                                      example))
        parsed = PartitionTable.parseLVMPhysicalVolume(self.LVM_PARTITION)
        self.assertEquals(parsed['name'], 'dummy')
        self.assertEquals(parsed['sizeMB'], 60)

        example = "\n".join([
            "  LV   VG    Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  crap dummy -wi-a---- 20.00m",
            ""])
        self.expectedCommands.append(('lvm lvdisplay --units m --columns /dev/inaugurator/crap', example))
        parsed = PartitionTable.parseLVMLogicalVolume("crap")
        self.assertEquals(parsed['volumeGroup'], 'dummy')
        self.assertEquals(parsed['sizeMB'], 20)

    def test_CreatePartitionTable_OnA16GBDisk(self):
        self.diskSizeGB = 16
        self.expectedCommands.append(('parted -s -m /dev/sda unit MB print', ""))
        self.expectedCommands.append(('''busybox dd if=/dev/zero of=/dev/sda bs=1M count=512''', ""))
        self.expectedCommands.append(('''parted -s /dev/sda -- mklabel gpt mkpart primary ext4 1MiB '''
                                      '''3MiB mkpart primary ext4 3MiB 259MiB mkpart primary ext4 '''
                                      '''259MiB -1''',
                                      ""))
        self.expectedCommands.append(('''parted -s /dev/sda set 1 bios_grub on''', ""))
        self.expectedCommands.append(('''parted -s /dev/sda set 2 boot on''', ""))
        self.expectedCommands.append(('''parted -s /dev/sda set 3 lvm on''', ""))
        self.expectedCommands.append(('''busybox mdev -s''', ""))
        self.expectedCommands.append(('''mkfs.ext4 /dev/sda2 -L BOOT''', ""))
        self.expectedCommands.append(('''lvm pvcreate -ff %(lvmPartition)s''' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        self.expectedCommands.append(('''lvm vgcreate inaugurator %(lvmPartition)s''' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        self.expectedCommands.append(('''lvm lvcreate --zero n --name swap --size 1G inaugurator''', ""))
        self.expectedCommands.append((
            '''lvm lvcreate --zero n --name osmosis-cache --size 5G inaugurator''', ""))
        self.expectedCommands.append((
            '''lvm lvcreate --zero n --name root --extents 100%FREE inaugurator''', ""))
        self.validateVolumesCreation()
        self.expectedCommands.append(('''mkfs.ext4 /dev/inaugurator/root -L ROOT''', ""))
        self.expectedCommands.append(('''mkfs.ext4 /dev/inaugurator/osmosis-cache''', ""))
        goodPartitionTable = self._getPartitionTableInMachineFormat(diskSizeGB=self.diskSizeGB)
        self.expectedCommands.append(('parted -s -m /dev/sda unit MB print', goodPartitionTable))
        self.expectedCommands.append(('lvm pvscan --cache %(lvmPartition)s' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        goodPhysicalVolume = "\n".join([
            "  PV        VG          Fmt  Attr PSize     PFree ",
            "  %(lvmPartition)s inaugurator lvm2 a--  16128.00m 16128.00m"
            "" % dict(lvmPartition=self.LVM_PARTITION)])
        self.expectedCommands.append(('lvm pvdisplay --units m --columns %(lvmPartition)s' %
                                      dict(lvmPartition=self.LVM_PARTITION), goodPhysicalVolume))
        correctSwap = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  swap inaugurator -wi-a---- 1024.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/swap', correctSwap))
        correctOsmosisCache = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  osmosis-cache inaugurator -wi-a---- 5120.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/osmosis-cache', correctOsmosisCache))
        correctRoot = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  root inaugurator -wi-a---- 15104.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/root', correctRoot))
        self.expectedCommands.append(("lvm pvscan",
                                      "PV %(lvmPartition)s   VG inaugurator   lvm2 [irrelevant size data]"
                                      % dict(lvmPartition=self.LVM_PARTITION),
                                      "Total: 1 more irrelevant data"))
        self.expectedCommands.append(("blkid", ""))
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def test_CreatePartitionTable_OnA128GBDisk(self):
        self._prepareExpectedCommandsFor128GBDisk()
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def test_WipeOtherPhysicalVolumesWithAVolumeGroupByTheSameName(self):
        self._prepareExpectedCommandsFor128GBDisk(extraVolumeGroup="inaugurator",
                                                  physicalVolumeOfExtraVolumeGroup="/dev/sdb2")
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def test_DontWipeTheWholePhysicalDeviceIfOneOfThePartitionsContainsAVolumeGroupByTheSameName(self):
        self._prepareExpectedCommandsFor128GBDisk(extraVolumeGroup="inaugurator",
                                                  physicalVolumeOfExtraVolumeGroup="/dev/sda4")
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def test_DontWipeTargetDeviceInCaseOfOtherPhysicalVolumesWithAVolumeGroupByTheSameName(self):
        self._prepareExpectedCommandsFor128GBDisk(extraVolumeGroup="non-inaugurator",
                                                  physicalVolumeOfExtraVolumeGroup="/dev/sdb2")
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def test_WipeOtherPhysicalVolumesLabeledAsBoot(self):
        self._prepareExpectedCommandsFor128GBDisk(blkidResult={"/dev/sdb1": "BOOT",
                                                               "/dev/sda1": "BOOT",
                                                               "/dev/bla": "NOTBOOT"})
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def _prepareExpectedCommandsFor128GBDisk(self,
                                             extraVolumeGroup=None,
                                             physicalVolumeOfExtraVolumeGroup=None,
                                             blkidResult=None):
        self.expectedCommands.append(('parted -s -m /dev/sda unit MB print', ""))
        self.expectedCommands.append(('''busybox dd if=/dev/zero of=/dev/sda bs=1M count=512''', ""))
        self.expectedCommands.append(('''parted -s /dev/sda -- mklabel gpt mkpart primary ext4 1MiB '''
                                      '''3MiB mkpart primary ext4 3MiB 259MiB mkpart primary ext4 '''
                                      '''259MiB -1''',
                                      ""))
        self.expectedCommands.append(('''parted -s /dev/sda set 1 bios_grub on''', ""))
        self.expectedCommands.append(('''parted -s /dev/sda set 2 boot on''', ""))
        self.expectedCommands.append(('''parted -s /dev/sda set 3 lvm on''', ""))
        self.expectedCommands.append(('''busybox mdev -s''', ""))
        self.expectedCommands.append(('''mkfs.ext4 /dev/sda2 -L BOOT''', ""))
        self.expectedCommands.append(('''lvm pvcreate -ff %(lvmPartition)s''' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        self.expectedCommands.append(('''lvm vgcreate inaugurator %(lvmPartition)s''' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        self.expectedCommands.append(('''lvm lvcreate --zero n --name swap --size 8G inaugurator''', ""))
        self.expectedCommands.append(
            ('''lvm lvcreate --zero n --name osmosis-cache --size 15G inaugurator''', ""))
        self.expectedCommands.append(('''lvm lvcreate --zero n --name root --size 10G inaugurator''', ""))
        self.validateVolumesCreation()
        self.expectedCommands.append(('''mkfs.ext4 /dev/inaugurator/root -L ROOT''', ""))
        self.expectedCommands.append(('''mkfs.ext4 /dev/inaugurator/osmosis-cache''', ""))
        self.expectedCommands.append(('parted -s -m /dev/sda unit MB print',
                                      self._getPartitionTableInMachineFormat(diskSizeGB=self.diskSizeGB)))
        self.expectedCommands.append(('lvm pvscan --cache %(lvmPartition)s' %
                                      dict(lvmPartition=self.LVM_PARTITION), ""))
        goodPhysicalVolume = "\n".join([
            "  PV        VG          Fmt  Attr PSize     PFree ",
            "  %(lvmPartition)s inaugurator lvm2 a--  130816.00m 130816.00m"
            "" % dict(lvmPartition=self.LVM_PARTITION)])
        self.expectedCommands.append(('lvm pvdisplay --units m --columns %(lvmPartition)s' %
                                      dict(lvmPartition=self.LVM_PARTITION), goodPhysicalVolume))
        correctSwap = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  swap inaugurator -wi-a---- 8192.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/swap', correctSwap))
        correctOsmosis = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  osmosis-cache inaugurator -wi-a---- 15360.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/osmosis-cache', correctOsmosis))
        correctRoot = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  root inaugurator -wi-a---- 30720.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/root', correctRoot))
        nrGroups = 1
        pvscanResult = ["PV %(lvmPartition)s   VG inaugurator   lvm2 [irrelevant size data]" %
                        dict(lvmPartition=self.LVM_PARTITION)]
        if extraVolumeGroup is not None:
            pvscanResult.append("PV %(physicalVolumeOfExtraVolumeGroup)s VG %(extraVolumeGroup)s "
                                "[irrelevent size data]" %
                                dict(extraVolumeGroup=extraVolumeGroup,
                                     physicalVolumeOfExtraVolumeGroup=physicalVolumeOfExtraVolumeGroup))
            nrGroups += 1
        pvscanResult.append("Total: %(nrGroups)s more irrelevant data" % dict(nrGroups=nrGroups))
        pvscanResult = "\n".join(pvscanResult)
        self.expectedCommands.append(("lvm pvscan", pvscanResult))
        if extraVolumeGroup == "inaugurator":
            cmd = '''busybox dd if=/dev/zero of=%(physicalVolume)s bs=1M count=1''' % \
                dict(physicalVolume=physicalVolumeOfExtraVolumeGroup)
            self.expectedCommands.append((cmd, ""))
            deviceNumberList = self._getNumberAtEndOfDevicePath(physicalVolumeOfExtraVolumeGroup)
            isPhysicalVolumeAPartitionOfAPhysicalDevice = bool(deviceNumberList)
            if isPhysicalVolumeAPartitionOfAPhysicalDevice:
                partitionNumber = deviceNumberList[0]
                physicalDevice = physicalVolumeOfExtraVolumeGroup[:-len(partitionNumber)]
                if physicalDevice != "/dev/sda":
                    cmd = '''busybox dd if=/dev/zero of=%(physicalDevice)s bs=1M count=1''' % \
                        dict(physicalDevice=physicalDevice)
                    self.expectedCommands.append((cmd, ""))
        if blkidResult is None:
            blkidOutput = ""
            devicesThatShouldNotBeLabeledAsBoot = list()
        else:
            devicesThatShouldNotBeLabeledAsBoot = \
                [device for device, label in blkidResult.iteritems() if label == "BOOT" and
                 device not in ("/dev/sda2", "/dev/sda")]
            blkidOutput = "\n".join(["%(device)s: SOME_ATTRIBUTE=some_value LABEL=\"%(label)s\"" %
                                    dict(device=device, label=label)
                                    for device, label in blkidResult.iteritems()])
        self.expectedCommands.append(("blkid", blkidOutput))
        for device in devicesThatShouldNotBeLabeledAsBoot:
            cmd = '''busybox dd if=/dev/zero of=%(device)s bs=1M count=1''' % dict(device=device)
            self.expectedCommands.append((cmd, ""))

    def _getNumberAtEndOfDevicePath(self, device):
        numbersAtEndOfExpressionFinder = re.compile("[\/\D]+(\d+)$")
        numbers = numbersAtEndOfExpressionFinder.findall(device)
        return numbers

    def generateCreatePathsCallback(self, *paths):
        def callback():
            self.fakeExistingPaths = self.fakeExistingPaths.union(paths)
        return callback

    def fakeOSExists(self, path):
        return path in self.fakeExistingPaths

    def validateVolumesCreation(self):
        devPath = os.path.join("/dev", "inaugurator")
        swapPath = os.path.join(devPath, "swap")
        osmosisPath = os.path.join(devPath, "osmosis-cache")
        createPathCallback = self.generateCreatePathsCallback(swapPath, osmosisPath)
        self.expectedCommands.append(('''lvm vgscan --mknodes''', createPathCallback))
        rootPath = os.path.join(devPath, "root")
        createPathCallback = self.generateCreatePathsCallback(rootPath)
        self.expectedCommands.append(('''mkswap %(path)s -L SWAP''' % dict(path=swapPath),
                                     createPathCallback))

    @classmethod
    def _getPartitionTableInMachineFormat(cls, diskSizeGB):
        BIOS_BOOT_PARTITION_START = 1.05
        BIOS_BOOT_PARTITION_END = BIOS_BOOT_PARTITION_START + cls.BIOS_BOOT_PARTITION_SIZE
        BOOT_PARTITION_START = BIOS_BOOT_PARTITION_END
        BOOT_PARTITION_END = BOOT_PARTITION_START + cls.BOOT_PARTITION_SIZE
        LVM_PARTITION_START = BOOT_PARTITION_END
        out = ["BYT;",
               "/dev/sda:240057MB:scsi:512:512:gpt:ATA SAMSUNG MZ7WD240:;",
               "1:%(biosBootPartitionStart).2fMB:%(biosBootPartitionEnd).2fMB:"
               "%(biosBootPartitionSizeMB).2fMB::primary:bios_grub;",
               "2:%(bootPartitionStart)sMB:%(bootPartitionEnd).2fMB:"
               "%(bootPartitionSizeMB).2fMB:ext4:primary:boot;",
               "3:%(lvmPartitionStart)sMB:%(lvmPartitionEnd)sMB:%(lvmPartitionSizeMB)sMB::primary:lvm;",
               ""]
        diskSizeMB = diskSizeGB * 1024
        out = "\n".join(out) % dict(biosBootPartitionStart=BIOS_BOOT_PARTITION_START,
                                    biosBootPartitionEnd=BIOS_BOOT_PARTITION_END,
                                    biosBootPartitionSizeMB=cls.BIOS_BOOT_PARTITION_SIZE,
                                    bootPartitionStart=BOOT_PARTITION_START,
                                    bootPartitionEnd=BOOT_PARTITION_END,
                                    bootPartitionSizeMB=cls.BOOT_PARTITION_SIZE,
                                    lvmPartitionStart=LVM_PARTITION_START,
                                    lvmPartitionEnd=LVM_PARTITION_START + diskSizeMB,
                                    lvmPartitionSizeMB=diskSizeMB - (cls.BIOS_BOOT_PARTITION_SIZE +
                                                                     cls.BOOT_PARTITION_SIZE))
        return out


if __name__ == '__main__':
    unittest.main()
