import re
import traceback
import time
from inaugurator import sh


class PartitionTable:
    _DEFAULT_SIZES_GB = dict(
        smallSwap=1,
        bigSwap=8,
        minimumRoot=14,
        createRoot=30)
    _BOOT_SIZE_MB = 256
    VOLUME_GROUP = "inaugurator"

    def __init__(self, device, sizesGB=dict()):
        self._sizesGB = dict(self._DEFAULT_SIZES_GB)
        self._sizesGB.update(sizesGB)
        self._device = device
        self._cachedDiskSize = None
        self._created = False

    def created(self):
        return self._created

    def clear(self):
        sh.run("busybox dd if=/dev/zero of=%s bs=1M count=512" % self._device)

    def _create(self):
        self.clear()
        script = "echo -ne '8,%s,83\\n,,8e\\n' | sfdisk --unit M %s --in-order --force" % (
            self._BOOT_SIZE_MB, self._device)
        print "creating new partition table:", script
        sh.run(script)
        sh.run("busybox mdev -s")
        sh.run("mkfs.ext4 %s1 -L BOOT" % self._device)
        sh.run("lvm pvcreate %s2" % self._device)
        sh.run("lvm vgcreate %s %s2" % (self.VOLUME_GROUP, self._device))
        if self._diskSizeMB() / 1024 >= self._sizesGB['createRoot'] + self._sizesGB['bigSwap']:
            swapSizeGB = 8
        else:
            swapSizeGB = 1
        sh.run("lvm lvcreate --zero n --name swap --size %dG %s" % (swapSizeGB, self.VOLUME_GROUP))
        if self._diskSizeMB() / 1024 > self._sizesGB['createRoot'] + swapSizeGB:
            rootSize = "--size %dG" % self._sizesGB['createRoot']
        else:
            rootSize = "--extents 100%FREE"
        sh.run("lvm lvcreate --zero n --name root %s %s" % (rootSize, self.VOLUME_GROUP))
        sh.run("lvm vgscan --mknodes")
        sh.run("mkswap /dev/%s/swap -L SWAP" % self.VOLUME_GROUP)
        sh.run("mkfs.ext4 /dev/%s/root -L ROOT" % self.VOLUME_GROUP)
        self._created = True

    def parsePartitionTable(self):
        LINE = re.compile(r"(/\S+) : start=\s*\d+, size=\s*(\d+), Id=\s*([0-9a-fA-F]+)")
        lines = LINE.findall(sh.run("sfdisk --dump %s" % self._device))
        return [
            dict(device=device, sizeMB=int(size) * 512 / 1024 / 1024, id=int(id, 16))
            for device, size, id in lines if int(size) > 0]

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
            self._cachedDiskSize = int(sh.run("sfdisk -s %s" % self._device).strip()) / 1024
        return self._cachedDiskSize

    def _sfdiskScript(self, table):
        lines = []
        offsetMB = '8'
        for partition in table:
            sizeMB = "" if partition['sizeMB'] == 'fill' else partition['sizeMB']
            line = r'%(offsetMB)s,%(sizeMB)s,%(id)d\n' % dict(
                partition, sizeMB=sizeMB, offsetMB=offsetMB)
            lines.append(line)
            offsetMB = ''
        return "".join(lines)

    def _findMismatchInPartitionTable(self):
        try:
            parsed = self.parsePartitionTable()
        except:
            print "Unable to parse partition table"
            traceback.print_exc()
            return "Unable to parse partition table"
        if len(parsed) != 2:
            return "Partition count is not 2"
        if parsed[0]['id'] != 0x83:
            return "Expected first partition to be ext4 (0x83)"
        if not self._approximatelyEquals(parsed[0]['sizeMB'], self._BOOT_SIZE_MB):
            return "Expected first partition to be around %sMB" % self._BOOT_SIZE_MB
        if parsed[1]['id'] != 0x8e:
            return "Expected second partition to be LVM (0x8e)"
        if not self._approximatelyEquals(parsed[1]['sizeMB'], self._diskSizeMB() - self._BOOT_SIZE_MB):
            return "Expected second partition to fill up disk"
        return None

    def _findMismatchInLVM(self):
        try:
            physical = self.parseLVMPhysicalVolume("%s2" % self._device)
        except:
            print "Unable to parse physical volume"
            traceback.print_exc()
            return "Unable to parse physical volume"
        if physical['name'] != self.VOLUME_GROUP:
            return "Physical volume name is '%s', and not '%s'" % (physical['name'], self.VOLUME_GROUP)
        if physical['sizeMB'] * 1.1 < self._diskSizeMB() - self._BOOT_SIZE_MB:
            return "Physical volume does not fill up most of the disk: %s < %s" % (
                physical['sizeMB'], self._diskSizeMB())

        try:
            swap = self.parseLVMLogicalVolume("swap")
            root = self.parseLVMLogicalVolume("root")
        except:
            print "Unable to parse logical volume/s"
            traceback.print_exc()
            return "Unable to parse physical volume/s"
        if root['sizeMB'] <= self._sizesGB['minimumRoot'] * 1024 * 0.9:
            return "Root partition is too small"
        if self._diskSizeMB() / 1024 >= self._sizesGB['createRoot'] + self._sizesGB['bigSwap']:
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

    def verify(self):
        if not self._findMismatch():
            print "Partition table already set up"
            sh.run("lvm pvscan --cache %s2" % self._device)
            sh.run("lvm vgchange --activate y %s" % self.VOLUME_GROUP)
            sh.run("lvm vgscan --mknodes")
            print "/dev/inaugurator:"
            try:
                print sh.run("busybox find /dev/inaugurator")
            except Exception as e:
                print "Unable: %s" % e
            return
        self._create()
        for retry in xrange(5):
            mismatch = self._findMismatch()
            if mismatch is None:
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
