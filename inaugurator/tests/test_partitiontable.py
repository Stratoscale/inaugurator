import os
import re
import unittest
import inaugurator
from inaugurator.partitiontable import PartitionTable
from inaugurator import sh


class Test(unittest.TestCase):
    def setUp(self):
        self.expectedCommands = []
        sh.run = self.runShell
        inaugurator.partitiontable.os.path.exists = self.fakeOSExists
        self.fakeExistingPaths = set()

    def runShell(self, command):
        foundList = [x for x in self.expectedCommands if x[0] == command]
        if len(foundList) == 0:
            raise Exception("Command '%s' is not in expected commands" % command)
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
        example = "\n".join([
            "# partition table of /dev/sda",
            "unit: sectors",
            "",
            "/dev/sda1 : start=     2048, size= 16023552, Id=82",
            "/dev/sda2 : start= 16025600, size=484091904, Id=83, bootable",
            "/dev/sda3 : start=        0, size=        0, Id= 0",
            "/dev/sda4 : start=        0, size=        0, Id= 0",
            ""])
        self.expectedCommands.append(('sfdisk --dump /dev/sda', example))
        tested = PartitionTable("/dev/sda")
        parsed = tested.parsePartitionTable()
        self.assertEquals(len(parsed), 2)
        self.assertEquals(parsed[0]['device'], '/dev/sda1')
        self.assertEquals(parsed[0]['sizeMB'], 16023552 / 2 / 1024)
        self.assertEquals(parsed[0]['id'], 0x82)
        self.assertEquals(parsed[1]['device'], '/dev/sda2')
        self.assertEquals(parsed[1]['sizeMB'], 484091904 / 2 / 1024)
        self.assertEquals(parsed[1]['id'], 0x83)
        self.assertEquals(len(self.expectedCommands), 0)

    def test_ParseLVM(self):
        example = "\n".join([
            "  PV        VG    Fmt  Attr PSize  PFree ",
            "  /dev/sda2 dummy lvm2 a--  60.00m 60.00m"
            ""])
        self.expectedCommands.append(('lvm pvscan --cache /dev/sda2', ""))
        self.expectedCommands.append(('lvm pvdisplay --units m --columns /dev/sda2', example))
        parsed = PartitionTable.parseLVMPhysicalVolume("/dev/sda2")
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
        self.expectedCommands.append(('sfdisk --dump /dev/sda', ""))
        self.expectedCommands.append(('''busybox dd if=/dev/zero of=/dev/sda bs=1M count=512''', ""))
        self.expectedCommands.append((
            '''echo -ne '8,256,83\\n,,8e\\n' | sfdisk --unit M /dev/sda --in-order --force''', ""))
        self.expectedCommands.append(('''busybox mdev -s''', ""))
        self.expectedCommands.append(('''sfdisk -s /dev/sda''', '%d\n' % (16 * 1024 * 1024)))
        self.expectedCommands.append(('''mkfs.ext4 /dev/sda1 -L BOOT''', ""))
        self.expectedCommands.append(('''lvm pvcreate /dev/sda2''', ""))
        self.expectedCommands.append(('''lvm vgcreate inaugurator /dev/sda2''', ""))
        self.expectedCommands.append(('''lvm lvcreate --zero n --name swap --size 1G inaugurator''', ""))
        self.expectedCommands.append((
            '''lvm lvcreate --zero n --name root --extents 100%FREE inaugurator''', ""))
        self.validateVolumesCreation()
        self.expectedCommands.append(('''mkfs.ext4 /dev/inaugurator/root -L ROOT''', ""))
        goodPartitionTable = "\n".join([
            "# partition table of /dev/sda",
            "unit: sectors",
            "",
            "/dev/sda1 : start=     2048, size=   512000, Id=83",
            "/dev/sda2 : start=   516000, size= 31000000, Id=8e",
            "/dev/sda3 : start=        0, size=        0, Id= 0",
            "/dev/sda4 : start=        0, size=        0, Id= 0",
            ""])
        self.expectedCommands.append(('sfdisk --dump /dev/sda', goodPartitionTable))
        self.expectedCommands.append(('lvm pvscan --cache /dev/sda2', ""))
        goodPhysicalVolume = "\n".join([
            "  PV        VG          Fmt  Attr PSize     PFree ",
            "  /dev/sda2 inaugurator lvm2 a--  16128.00m 16128.00m"
            ""])
        self.expectedCommands.append(('lvm pvdisplay --units m --columns /dev/sda2', goodPhysicalVolume))
        correctSwap = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  swap inaugurator -wi-a---- 1024.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/swap', correctSwap))
        correctRoot = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  root inaugurator -wi-a---- 15104.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/root', correctRoot))
        self.expectedCommands.append(("lvm pvscan",
                                      "PV /dev/sda2   VG inaugurator   lvm2 [irrelevant size data]",
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
                                                  physicalVolumeOfExtraVolumeGroup="/dev/sda3")
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
        self.expectedCommands.append(('sfdisk --dump /dev/sda', ""))
        self.expectedCommands.append(('''busybox dd if=/dev/zero of=/dev/sda bs=1M count=512''', ""))
        self.expectedCommands.append((
            '''echo -ne '8,256,83\\n,,8e\\n' | sfdisk --unit M /dev/sda --in-order --force''', ""))
        self.expectedCommands.append(('''busybox mdev -s''', ""))
        self.expectedCommands.append(('''sfdisk -s /dev/sda''', '%d\n' % (128 * 1024 * 1024)))
        self.expectedCommands.append(('''mkfs.ext4 /dev/sda1 -L BOOT''', ""))
        self.expectedCommands.append(('''lvm pvcreate /dev/sda2''', ""))
        self.expectedCommands.append(('''lvm vgcreate inaugurator /dev/sda2''', ""))
        self.expectedCommands.append(('''lvm lvcreate --zero n --name swap --size 8G inaugurator''', ""))
        self.expectedCommands.append(('''lvm lvcreate --zero n --name root --size 30G inaugurator''', ""))
        self.validateVolumesCreation()
        self.expectedCommands.append(('''mkfs.ext4 /dev/inaugurator/root -L ROOT''', ""))
        goodPartitionTable = "\n".join([
            "# partition table of /dev/sda",
            "unit: sectors",
            "",
            "/dev/sda1 : start=     2048, size=   512000, Id=83",
            "/dev/sda2 : start=   516000, size=267911168, Id=8e",
            "/dev/sda3 : start=        0, size=        0, Id= 0",
            "/dev/sda4 : start=        0, size=        0, Id= 0",
            ""])
        self.expectedCommands.append(('sfdisk --dump /dev/sda', goodPartitionTable))
        self.expectedCommands.append(('lvm pvscan --cache /dev/sda2', ""))
        goodPhysicalVolume = "\n".join([
            "  PV        VG          Fmt  Attr PSize     PFree ",
            "  /dev/sda2 inaugurator lvm2 a--  130816.00m 130816.00m"
            ""])
        self.expectedCommands.append(('lvm pvdisplay --units m --columns /dev/sda2', goodPhysicalVolume))
        correctSwap = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  swap inaugurator -wi-a---- 8192.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/swap', correctSwap))
        correctRoot = "\n".join([
            "  LV   VG          Attr      LSize  Pool Origin Data%  Move Log Copy%  Convert",
            "  root inaugurator -wi-a---- 30720.00m",
            ""])
        self.expectedCommands.append((
            'lvm lvdisplay --units m --columns /dev/inaugurator/root', correctRoot))
        nrGroups = 1
        pvscanResult = ["PV /dev/sda2   VG inaugurator   lvm2 [irrelevant size data]"]
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
                 device not in ("/dev/sda1", "/dev/sda")]
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

    def generateCreatePathCallback(self, path, output=""):
        def callback():
            self.fakeExistingPaths.add(path)
            return output
        return callback

    def fakeOSExists(self, path):
        return path in self.fakeExistingPaths

    def validateVolumesCreation(self):
        devPath = os.path.join("/dev", "inaugurator")
        swapPath = os.path.join(devPath, "swap")
        createPathCallback = self.generateCreatePathCallback(swapPath)
        self.expectedCommands.append(('''lvm vgscan --mknodes''', createPathCallback))
        rootPath = os.path.join(devPath, "root")
        createPathCallback = self.generateCreatePathCallback(rootPath)
        self.expectedCommands.append(('''mkswap %(path)s -L SWAP''' % dict(path=swapPath),
                                     createPathCallback))


if __name__ == '__main__':
    unittest.main()
