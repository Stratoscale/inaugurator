import re
import traceback
import time
import os
from inaugurator import sh


class PartitionTable:
    _DEFAULT_SIZES_GB = dict(
        smallSwap=1,
        bigSwap=8,
        smallOsmosisCache=5,
        bigOsmosisCache=30,
        minimumRoot=7,
        createRoot=10)
    VOLUME_GROUP = "inaugurator"
    LAYOUT_SCHEMES = dict(GPT=dict(partitions=dict(bios_boot=dict(sizeMB=2, flags="bios_grub"),
                                                   boot=dict(sizeMB=256, fs="ext4", flags="boot"),
                                                   lvm=dict(flags="lvm", sizeMB="fillUp")),
                                   order=("bios_boot", "boot", "lvm")),
                          MBR=dict(partitions=dict(boot=dict(sizeMB=256, fs="ext4", flags="boot"),
                                                   lvm=dict(flags="lvm", sizeMB="fillUp")),
                                   order=("boot", "lvm")))

    def __init__(self, device, sizesGB=dict(), layoutScheme="GPT"):
        self._sizesGB = dict(self._DEFAULT_SIZES_GB)
        self._sizesGB.update(sizesGB)
        self._device = device
        self._cachedDiskSize = None
        self._created = False
        if layoutScheme not in self.LAYOUT_SCHEMES:
            print "Invalid layout scheme. Possible values: '%s'" % "', '".join(self.LAYOUT_SCHEMES.keys())
            raise ValueError(layoutScheme)
        self._layoutScheme = layoutScheme
        self._physicalPartitions = self.LAYOUT_SCHEMES[layoutScheme]["partitions"]
        self._physicalPartitionsOrder = self.LAYOUT_SCHEMES[layoutScheme]["order"]

    def created(self):
        return self._created

    def clear(self, device=None, count=512):
        if device is None:
            device = self._device
        sh.run("busybox dd if=/dev/zero of=%(device)s bs=1M count=%(count)s" % dict(device=device,
                                                                                    count=count))

    def _create(self):
        self.clear()
        script = self._getPartitionCommand()
        print "creating new partition table of layout '%s': \n%s\n" % (self._layoutScheme, script)
        sh.run(script)
        self._setFlags()
        sh.run("busybox mdev -s")
        sh.run("mkfs.ext4 %s -L BOOT" % self._getPartitionPath("boot"))
        try:
            sh.run("lvm vgremove -f %s" % (self.VOLUME_GROUP, ))
        except:
            traceback.print_exc()
            print "'lvm vgremove' failed"
        lvmPartitionPath = self._getPartitionPath("lvm")
        sh.run("lvm pvcreate -y -ff %s" % (lvmPartitionPath,))
        sh.run("lvm vgcreate -y %s %s" % (self.VOLUME_GROUP, lvmPartitionPath))
        if self._diskSizeMB() / 1024 >= self._sizesGB['createRoot'] + self._sizesGB['bigSwap'] + \
                self._sizesGB["bigOsmosisCache"]:
            swapSizeGB = 8
        else:
            swapSizeGB = 1
        sh.run("lvm lvcreate --zero n --name swap --size %dG %s" % (swapSizeGB, self.VOLUME_GROUP))
        if self._diskSizeMB() / 1024 > self._sizesGB['createRoot'] + swapSizeGB + \
                self._sizesGB["bigOsmosisCache"]:
            osmosisCacheSizeGB = self._sizesGB["bigOsmosisCache"]
        else:
            osmosisCacheSizeGB = self._sizesGB["smallOsmosisCache"]
        sh.run("lvm lvcreate --zero n --name osmosis-cache --size %dG %s" %
               (osmosisCacheSizeGB, self.VOLUME_GROUP))

        rootSize = "--extents 100%FREE"

        sh.run("lvm lvcreate --zero n --name root %s %s" % (rootSize, self.VOLUME_GROUP))
        sh.run("lvm vgscan --mknodes")
        self._waitForFileToShowUp("/dev/%s/swap" % self.VOLUME_GROUP)
        sh.run("mkswap /dev/%s/swap -L SWAP" % self.VOLUME_GROUP)
        self._waitForFileToShowUp("/dev/%s/root" % self.VOLUME_GROUP)
        sh.run("mkfs.ext4 /dev/%s/root -L ROOT" % self.VOLUME_GROUP)
        self._waitForFileToShowUp("/dev/%s/osmosis-cache" % self.VOLUME_GROUP)
        sh.run("mkfs.ext4 /dev/%s/osmosis-cache" % self.VOLUME_GROUP)
        self._created = True

    def _getPartitionCommand(self):
        if self._layoutScheme == "MBR":
            bootSize = self._physicalPartitions["boot"]["sizeMB"]
            script = "echo -ne '8,%s,83\\n,,8e\\n' | sfdisk --unit M %s --in-order --force" % (
                bootSize, self._device)
        elif self._layoutScheme == "GPT":
            biosBootStart = 1
            biosBootEnd = biosBootStart + self._physicalPartitions["bios_boot"]["sizeMB"]
            bootStart = biosBootEnd
            bootEnd = bootStart + self._physicalPartitions["boot"]["sizeMB"]
            script = "parted -s %(device)s -- " \
                     "mklabel gpt mkpart primary ext4 %(biosBootStart)sMiB %(biosBootEnd)sMiB " \
                     "mkpart primary ext4 %(bootStart)sMiB %(bootEnd)sMiB " \
                     "mkpart primary ext4 %(lvmStart)sMiB -1" % \
                dict(device=self._device,
                     biosBootStart=biosBootStart,
                     biosBootEnd=biosBootEnd,
                     bootStart=bootStart,
                     bootEnd=bootEnd,
                     lvmStart=bootEnd)
        return script

    def _setFlags(self):
        for partitionIdx, partition in enumerate(self._physicalPartitionsOrder):
            partitionNr = partitionIdx + 1
            flag = self._physicalPartitions[partition]["flags"]
            print "Setting flag '%s' for partition #%d..." % (flag, partitionNr)
            sh.run("parted -s %s set %d %s on" % (self._device, partitionNr, flag))

    def parsePartitionTable(self):
        cmd = "parted -s -m %(device)s unit MB print" % dict(device=self._device)
        output = sh.run(cmd)
        print "Output of parted: %(output)s" % dict(output=output)
        lines = [line.strip() for line in output.split(";")]
        lines = [line for line in lines if line]
        partitionsLines = lines[2:]
        partitions = [dict(zip(("nr", "start", "end", "size", "fs", "name", "flags"),
                      partitionLine.split(":"))) for partitionLine in partitionsLines]
        return [dict(device="%(device)s%(nr)s" % dict(device=self._device, nr=partition["nr"]),
                     sizeMB=float(partition["size"].rstrip("MB")),
                     fs=partition["fs"],
                     flags=partition["flags"])
                for partition in partitions]

    @classmethod
    def _fieldsOfLastTableRow(self, output):
        return re.split(r"\s+", output.strip().split("\n")[-1].strip())

    @classmethod
    def parseLVMPhysicalVolume(cls, partition):
        sh.run("lvm pvscan --cache %s" % partition)
        fields = cls._fieldsOfLastTableRow(sh.run("lvm pvdisplay --units m --columns %s" % partition))
        assert fields[0] == partition, "Invalid columns output from pvdisplay: %s" % fields
        assert fields[4].endswith("m")
        return dict(name=fields[1], sizeMB=int(re.match(r"\d+", fields[4]).group(0)))

    @classmethod
    def parseLVMLogicalVolume(cls, label):
        fields = cls._fieldsOfLastTableRow(sh.run("lvm lvdisplay --units m --columns /dev/%s/%s" % (
            cls.VOLUME_GROUP, label)))
        assert fields[0] == label, "Invalid columns output from lvdisplay: %s" % fields
        assert fields[3].endswith("m")
        return dict(volumeGroup=fields[1], sizeMB=int(re.match(r"\d+", fields[3]).group(0)))

    def _diskSizeMB(self):
        if self._cachedDiskSize is None:
            with open(os.path.join("/sys/block/", self._device.split("/dev/")[1], "size"), "r") as f:
                contents = f.read()
            contents = contents.strip()
            nrBlocks = int(contents)
            BLOCK_SIZE = 512
            NR_BYTES_IN_MB = 1024 ** 2
            sizeMB = nrBlocks * BLOCK_SIZE / NR_BYTES_IN_MB
            self._cachedDiskSize = sizeMB
        return self._cachedDiskSize

    def _findMismatchInPartitionTable(self):
        try:
            parsed = self.parsePartitionTable()
        except:
            print "Unable to parse partition table"
            traceback.print_exc()
            return "Unable to parse partition table"
        if len(parsed) != len(self._physicalPartitions):
            return "Partition count is not %(nrPartitions)s" % \
                dict(nrPartitions=len(self._physicalPartitions))
        for partitionPurpose, actualPartition in zip(self._physicalPartitionsOrder, parsed):
            expectedPartition = self._physicalPartitions[partitionPurpose]
            for attrName in ("fs", "flags"):
                if attrName not in expectedPartition:
                    continue
                actual = actualPartition[attrName]
                expected = expectedPartition[attrName]
                if expected != actual:
                    return "Expected attribute %(attrName)s of %(partitionPurpose)s partition to be " \
                           "'%(expected)s', not '%(actual)s'" % \
                           dict(attrName=attrName,
                                partitionPurpose=partitionPurpose,
                                expected=expected,
                                actual=actual)

            expectedSize = expectedPartition["sizeMB"]
            if expectedPartition["sizeMB"] == "fillUp":
                sizeOfOthers = self._combinedSizeOfAllOtherPartitions(partitionPurpose)
                expectedSize = self._diskSizeMB() - sizeOfOthers
            if not self._approximatelyEquals(expectedSize, actualPartition["sizeMB"]):
                return "Expected partition %(partitionPurpose)s to be approximately %(expectedSize)sMB" % \
                    dict(partitionPurpose=partitionPurpose, expectedSize=expectedSize)
        return None

    def _combinedSizeOfAllOtherPartitions(self, partitionPurpose):
        return sum([attrs["sizeMB"] for purpose, attrs in
                    self._physicalPartitions.iteritems() if purpose != partitionPurpose])

    def _findMismatchInLVM(self):
        lvmPartitionPath = self._getPartitionPath("lvm")
        try:
            physical = self.parseLVMPhysicalVolume(lvmPartitionPath)
        except:
            print "Unable to parse physical volume"
            traceback.print_exc()
            return "Unable to parse physical volume"
        if physical['name'] != self.VOLUME_GROUP:
            return "Physical volume name is '%s', and not '%s'" % (physical['name'], self.VOLUME_GROUP)
        if physical['sizeMB'] * 1.1 < self._combinedSizeOfAllOtherPartitions("lvm"):
            return "Physical volume does not fill up most of the disk: %s < %s" % (
                physical['sizeMB'], self._diskSizeMB())

        try:
            swap = self.parseLVMLogicalVolume("swap")
            root = self.parseLVMLogicalVolume("root")
            osmosis = self.parseLVMLogicalVolume("osmosis-cache")
        except:
            print "Unable to parse logical volume/s"
            traceback.print_exc()
            return "Unable to parse physical volume/s"
        if root['sizeMB'] <= self._sizesGB['minimumRoot'] * 1024 * 0.9:
            return "Root partition is too small"
        if self._diskSizeMB() / 1024 >= self._sizesGB['createRoot'] + self._sizesGB['bigSwap'] + \
                self._sizesGB["bigOsmosisCache"]:
            minimumSwapSizeGB = self._sizesGB['bigSwap']
        else:
            minimumSwapSizeGB = self._sizesGB['smallSwap']
        if swap['sizeMB'] <= minimumSwapSizeGB * 1024 * 0.9:
            return "Swap partition is too small"
        if self._diskSizeMB() / 1024 >= self._sizesGB['createRoot'] + minimumSwapSizeGB + \
                self._sizesGB["bigOsmosisCache"]:
            minimumOsmosisCacheSizeGB = self._sizesGB['bigOsmosisCache']
        else:
            minimumOsmosisCacheSizeGB = self._sizesGB['smallOsmosisCache']
        if osmosis['sizeMB'] <= minimumOsmosisCacheSizeGB * 1024 * 0.9:
            return "Osmosis cache partition is too small (%(sizeMB)sG)" % dict(sizeMB=osmosis["sizeMB"])

        return None

    def _findMismatch(self):
        mismatch = self._findMismatchInPartitionTable()
        if mismatch is not None:
            return mismatch
        return self._findMismatchInLVM()

    def _approximatelyEquals(self, first, second):
        return first > second * 0.9 and first < second * 1.1

    def _parseVGs(self):
        pvscanOutput = sh.run("lvm pvscan")
        print "`pvscan` output:\n %(pvscanOutput)s" % dict(pvscanOutput=pvscanOutput)
        vgs = dict()
        if "No matching physical volumes found" in pvscanOutput:
            return vgs
        pvscanOutput = [line.strip() for line in pvscanOutput.splitlines()]
        pvscanOutput = [line for line in pvscanOutput if not line.startswith("Total:")]
        for line in pvscanOutput:
            parts = line.split(" ")
            parts = [part for part in parts if part]
            if len(parts) > 4 and parts[0] == "PV" and parts[2] == "VG":
                device = parts[1]
                name = parts[3]
                assert device not in vgs
                vgs[device] = name
        return vgs

    def _getNumberAtEndOfDevicePath(self, device):
        numbersAtEndOfExpressionFinder = re.compile("[\/\D]+(\d+)$")
        numbers = numbersAtEndOfExpressionFinder.findall(device)
        return numbers

    def _getPhysicalDeviceOfPartition(self, partition):
        numbers = self._getNumberAtEndOfDevicePath(partition)
        assert numbers
        number = numbers[0]
        return partition[:-len(number)]

    def _isPartitionOfPhysicalDevice(self, device):
        numbers = self._getPhysicalDeviceOfPartition(device)
        return bool(numbers)

    def _wipeOtherPartitionsWithSameVolumeGroup(self):
        print "Validating that volume group %(vg)s is bound only to one device..." % \
              dict(vg=self.VOLUME_GROUP)
        vgs = self._parseVGs()
        if not vgs:
            raise Exception("No volume group was found after configuration of LVM.")
        targetPhysicalVolumeForVolumeGroup = self._getPartitionPath("lvm")
        for physicalVolume, volumeGroup in vgs.iteritems():
            if physicalVolume != targetPhysicalVolumeForVolumeGroup and volumeGroup == self.VOLUME_GROUP:
                print "Wiping '%(physicalVolume)s' since it contains another copy of the volume group..." \
                      % dict(physicalVolume=physicalVolume)
                self.clear(device=physicalVolume, count=1)
                if self._isPartitionOfPhysicalDevice(physicalVolume):
                    physicalDevice = self._getPhysicalDeviceOfPartition(physicalVolume)
                    if physicalDevice == self._device:
                        print "Skipping wipe of the physical device that contained the volume group since" \
                              " it's the target divice."
                        continue
                    print "Wiping the physical device '%(physicalDevice)s' which contained the volume " \
                          "group..." % dict(physicalDevice=physicalDevice)
                    self.clear(device=physicalDevice, count=1)

    def _getDevicesLabeledAsBoot(self):
        output = sh.run("blkid")
        print "blkid output:\n"
        print output
        for line in output.splitlines():
            line = line.strip()
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            device, data = parts
            if " LABEL=\"BOOT\"" in data:
                device = device.strip()
                yield device

    def _wipeOtherPartitionsWithBootLabel(self):
        print "Validating that device %(device)s is the only one with BOOT label..." % \
              dict(device=self._getPartitionPath("boot"))
        for device in self._getDevicesLabeledAsBoot():
            if device != self._getPartitionPath("boot") and device != self._device:
                print "Wiping '%(device)s' since it is labeled as BOOT (probably leftovers from previous " \
                      "inaugurations)..." % (dict(device=device))
                self.clear(device=device, count=1)

    def verify(self):
        if not self._findMismatch():
            print "Partition table already set up"
            lvmPartitionPath = self._getPartitionPath("lvm")
            sh.run("lvm pvscan --cache %s" % lvmPartitionPath)
            sh.run("lvm vgchange --activate y %s" % self.VOLUME_GROUP)
            sh.run("lvm vgscan --mknodes")
            print "/dev/inaugurator:"
            try:
                print sh.run("busybox find /dev/inaugurator")
            except Exception as e:
                print "Unable: %s" % e
            self._wipeOtherPartitionsWithSameVolumeGroup()
            self._wipeOtherPartitionsWithBootLabel()
            return
        self._create()
        for retry in xrange(5):
            mismatch = self._findMismatch()
            if mismatch is None:
                self._wipeOtherPartitionsWithSameVolumeGroup()
                self._wipeOtherPartitionsWithBootLabel()
                return
            else:
                print "Partition table not correct even after %d retries: '%s'" % (
                    retry, mismatch)
                time.sleep(0.2)
        print "Found Partition Table:", self.parsePartitionTable()
        try:
            print "Found LVM physical:", self.parseLVMPhysicalVolume()
        except:
            print "Can't get physical LVM"
        try:
            print "Found LVM logical:", self.parseLVMLogicalVolume()
        except:
            print "Can't get logical LVM"
        print "Mismatch:", self._findMismatch()
        raise Exception("Created partition table isn't as expected")

    def _waitForFileToShowUp(self, path):
        before = time.time()
        while not os.path.exists(path):
            if time.time() - before > 2:
                raise Exception("Timeout waiting for '%s' to show up" % path)
            time.sleep(0.02)

    def _getPartitionPath(self, partitionPurpose):
        partitionIdx = self._physicalPartitionsOrder.index(partitionPurpose)
        partitionNr = partitionIdx + 1
        return "%(device)s%(partitionNr)s" % dict(device=self._device, partitionNr=partitionNr)

    def getBootPartitionPath(self):
        return self._getPartitionPath("boot")
