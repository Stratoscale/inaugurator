import re
import traceback
import time
import os
import logging
from inaugurator import sh


class PartitionTable:
    _DEFAULT_SIZES_GB = dict(
        smallSwap=1,
        bigSwap=8,
        minimumRoot=14)
    VOLUME_GROUP = "inaugurator"

    def __init__(self, device, sizesGB=dict(), layoutScheme="GPT", rootPartitionSizeGB=20,
                 bootPartitionSizeMB=512, wipeOldInstallations=False):
        self._sizesGB = dict(self._DEFAULT_SIZES_GB)
        self._sizesGB.update(sizesGB)
        self._buildLayoutSchemes(bootPartitionSizeMB)
        self._device = device
        self._cachedDiskSize = None
        self._created = False
        if layoutScheme not in self._layoutSchemes:
            logging.error("Invalid layout scheme. Possible values: '%s'",
                          "', '".join(self._layoutSchemes.keys()))
            raise ValueError(layoutScheme)
        self._layoutScheme = layoutScheme
        self._physicalPartitions = self._layoutSchemes[layoutScheme]["partitions"]
        self._physicalPartitionsOrder = self._layoutSchemes[layoutScheme]["order"]
        self._requestedRootSizeGB = rootPartitionSizeGB
        self._wipeOldInstallations = wipeOldInstallations

    def created(self):
        return self._created

    def clear(self, device=None, count=512):
        if device is None:
            device = self._device
        sh.run("busybox dd if=/dev/zero of=%(device)s bs=1M count=%(count)s" % dict(device=device,
                                                                                    count=count))

    def _buildLayoutSchemes(self, bootPartitionSizeMB):
        self._layoutSchemes = dict(GPT=dict(partitions=dict(bios_boot=dict(sizeMB=2, flags="bios_grub"),
                                            boot=dict(sizeMB=bootPartitionSizeMB, fs="ext4", flags="boot"),
                                            lvm=dict(flags="lvm", sizeMB="fillUp")),
                                            order=("bios_boot", "boot", "lvm")),
                                   MBR=dict(partitions=dict(boot=dict(sizeMB=bootPartitionSizeMB,
                                                                      fs="ext4", flags="boot"),
                                            lvm=dict(flags="lvm", sizeMB="fillUp")), order=("boot", "lvm")))

    def _create(self):
        self.clear()
        script = self._getPartitionCommand()
        logging.info("creating new partition table of layout '%s': \n%s\n" % (self._layoutScheme, script))
        sh.run(script)
        self._setFlags()
        sh.run("busybox mdev -s")
        sh.run("mkfs.ext4 %s -L BOOT" % self._getPartitionPath("boot"))
        try:
            sh.run("lvm vgremove -f %s" % (self.VOLUME_GROUP, ))
        except:
            traceback.print_exc()
            logging.info("'lvm vgremove' failed")
        lvmPartitionPath = self._getPartitionPath("lvm")
        sh.run("lvm pvcreate -y -ff %s" % (lvmPartitionPath,))
        sh.run("lvm vgcreate -y %s %s" % (self.VOLUME_GROUP, lvmPartitionPath))
        if self._diskSizeMB() / 1024 >= self._requestedRootSizeGB + self._sizesGB['bigSwap']:
            swapSizeGB = 8
        else:
            swapSizeGB = 1
        sh.run("lvm lvcreate --zero n --name swap --size %dG %s" % (swapSizeGB, self.VOLUME_GROUP))
        if self._diskSizeMB() / 1024 > self._requestedRootSizeGB + swapSizeGB:
            rootSize = "--size %dG" % self._requestedRootSizeGB
        else:
            rootSize = "--extents 100%FREE"
        sh.run("lvm lvcreate --zero n --name root %s %s" % (rootSize, self.VOLUME_GROUP))
        sh.run("lvm vgscan --mknodes")
        self._waitForFileToShowUp("/dev/%s/swap" % self.VOLUME_GROUP)
        sh.run("mkswap /dev/%s/swap -L SWAP" % self.VOLUME_GROUP)
        self._waitForFileToShowUp("/dev/%s/root" % self.VOLUME_GROUP)
        sh.run("mkfs.ext4 /dev/%s/root -L ROOT" % self.VOLUME_GROUP)
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
            logging.info("Setting flag '%s' for partition #%d..." % (flag, partitionNr))
            sh.run("parted -s %s set %d %s on" % (self._device, partitionNr, flag))

    def parsePartitionTable(self):
        cmd = "parted -s -m %(device)s unit MB print" % dict(device=self._device)
        output = sh.run(cmd)
        logging.info("Output of parted: %(output)s" % dict(output=output))
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
            logging.info("Parsed partition table is:\n%s", parsed)
        except:
            logging.info("Unable to parse partition table")
            traceback.print_exc()
            return "Unable to parse partition table"
        if len(parsed) != len(self._physicalPartitions):
            return "Partition count is not %(nrPartitions)s" % \
                dict(nrPartitions=len(self._physicalPartitions))
        for partitionPurpose, actualPartition in zip(self._physicalPartitionsOrder, parsed):
            expectedPartition = self._physicalPartitions[partitionPurpose]
            logging.info("Expected Partition properties are:\n%s", expectedPartition)
            for attrName in ("fs", "flags"):
                if attrName not in expectedPartition:
                    continue
                actual = actualPartition[attrName]
                logging.info("Actual partition name is: %s", actual)
                expected = expectedPartition[attrName]
                logging.info("Expected partition name is: %s", expected)
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
                logging.info("Size of all other partitions is: %s", sizeOfOthers)
                expectedSize = self._diskSizeMB() - sizeOfOthers
                logging.info("Expected  partition size is: %s", expectedSize)
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
            logging.info("Unable to parse physical volume")
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
        except:
            logging.info("Unable to parse logical volume/s")
            traceback.print_exc()
            return "Unable to parse physical volume/s"
        if root['sizeMB'] <= self._sizesGB['minimumRoot'] * 1024 * 0.9:
            return "Root partition is too small"
        if root['sizeMB'] >= self._requestedRootSizeGB * 1024 * 1.2:
            logging.info("Root partition is too big")
            return "Root partition is too big"
        if self._diskSizeMB() / 1024 >= self._requestedRootSizeGB + self._sizesGB['bigSwap']:
            minimumSwapSizeGB = self._sizesGB['bigSwap']
        else:
            minimumSwapSizeGB = self._sizesGB['smallSwap']
        if swap['sizeMB'] <= minimumSwapSizeGB * 1024 * 0.9:
            return "Swap partition is too small"

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
        logging.info("`pvscan` output:\n %(pvscanOutput)s" % dict(pvscanOutput=pvscanOutput))
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

    @classmethod
    def getDevicesWithLabel(self, label):
        os.system("/usr/sbin/busybox mdev -s")
        time.sleep(1)
        output = sh.run("blkid")
        logging.info("blkid output:\n")
        logging.info(output)
        for line in output.splitlines():
            line = line.strip()
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            device, data = parts
            if " LABEL=\"%s\"" % label in data:
                device = device.strip()
                yield device

    @classmethod
    def getOriginDevices(self, devices):
        return [os.path.join("/dev", sh.run("lsblk -no pkname %s" % dev).strip()) for dev in devices]

    def _wipeOldInstallationsIfAllowed(self):
        if self._wipeOldInstallations:
            logging.info("Checking (and possibly deleting) old Inaugurator installations...")
            self._wipeOtherPartitionsWithSameVolumeGroup()
            self._wipeOtherPartitionsWithBootLabel()

    def _wipeOtherPartitionsWithBootLabel(self):
        logging.info("Validating that device %(device)s is the only one with BOOT label...",
                     dict(device=self._getPartitionPath("boot")))
        for device in self.getDevicesWithLabel("BOOT"):
            if device != self._getPartitionPath("boot") and device != self._device:
                logging.info("Wiping '%(device)s' since it is labeled as BOOT (probably leftovers from "
                             "previous inaugurations)...", dict(device=device))
                self.clear(device=device, count=1)

    def _wipeOtherPartitionsWithSameVolumeGroup(self):
        logging.info("Validating that volume group %(vg)s is bound only to one device...",
                     dict(vg=self.VOLUME_GROUP))
        vgs = self._parseVGs()
        if not vgs:
            raise Exception("No volume group was found after configuration of LVM.")
        targetPhysicalVolumeForVolumeGroup = self._getPartitionPath("lvm")
        for physicalVolume, volumeGroup in vgs.iteritems():
            if physicalVolume != targetPhysicalVolumeForVolumeGroup and volumeGroup == self.VOLUME_GROUP:
                logging.info("Wiping '%(physicalVolume)s' since it contains another copy of the volume "
                             "group...",
                             dict(physicalVolume=physicalVolume))
                self.clear(device=physicalVolume, count=1)
                if self._isPartitionOfPhysicalDevice(physicalVolume):
                    physicalDevice = self._getPhysicalDeviceOfPartition(physicalVolume)
                    if physicalDevice == self._device:
                        logging.info("Skipping wipe of the physical device that contained the volume "
                                     "group since it's the target device.")
                        continue
                    logging.info("Wiping the physical device '%(physicalDevice)s' which contained the "
                                 "volume group...", dict(physicalDevice=physicalDevice))
                    self.clear(device=physicalDevice, count=1)

    def verify(self):
        mismatch = self._findMismatch()
        if not mismatch:
            logging.info("Partition table already set up")
            lvmPartitionPath = self._getPartitionPath("lvm")
            sh.run("lvm pvscan --cache %s" % lvmPartitionPath)
            for lv in ["root", "swap"]:
                lv = "%s/%s" % (self.VOLUME_GROUP, lv)
                logging.info("Activating %s" % (lv,))
                sh.run("lvm lvchange --activate y %s" % lv)
            sh.run("lvm vgscan --mknodes")
            logging.info("/dev/inaugurator:")
            try:
                logging.info(sh.run("busybox find /dev/inaugurator"))
            except Exception as e:
                logging.info("Unable: %s" % e)
            self._wipeOldInstallationsIfAllowed()
            return
        logging.warning("Found mismatch in partition layout - %s", mismatch)
        if not self._wipeOldInstallations:
            raise Exception("Found mismatch in partition layout. we cannot continue without wiping data")
        self._create()
        for retry in xrange(5):
            mismatch = self._findMismatch()
            if mismatch is None:
                self._wipeOldInstallationsIfAllowed()
                return
            else:
                logging.info("Partition table not correct even after %d retries: '%s'" % (retry, mismatch))
                time.sleep(0.2)
        logging.info("Found Partition Table: %s", self.parsePartitionTable())
        try:
            logging.info("Found LVM physical: %s", self.parseLVMPhysicalVolume())
        except:
            logging.info("Can't get physical LVM")
        try:
            logging.info("Found LVM logical: %s", self.parseLVMLogicalVolume())
        except:
            logging.info("Can't get logical LVM")
        logging.info("Mismatch: %s", self._findMismatch())
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
