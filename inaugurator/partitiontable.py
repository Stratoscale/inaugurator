import re
from inaugurator import sh


class PartitionTable:
    def __init__(self, device):
        self._device = device

    def clear(self):
        sh.run("/usr/sbin/busybox dd if=/dev/zero of=%s bs=1M count=1024" % self._device)

    def _create(self):
        print "creating new partition table"
        sh.run(
            ("/usr/sbin/parted %s --script mklabel msdos mkpart "
                "p 1M 525M mkpart p 525M 100%%") % self._device)
        sh.run("/usr/sbin/busybox mdev -s")
        print "creating /boot file-system"
        sh.run("/usr/sbin/mkfs.ext4 -L boot %s1" % self._device)
        print "creating /root file-system"
        sh.run("/usr/sbin/mkfs.ext4 -L root %s2" % self._device)

    def _check(self):
        EXPECTED_PARTITION_TABLE_REGEX = re.compile(
            r"1\s+1049kB\s+525MB\s+524MB\s+primary\s+ext4\s+2\s+"
            "525MB\s+\d+(?:\.\d+)?GB\s+\d+(?:\.\d+)?GB\s+primary\s+ext4")
        try:
            partedPrintOutput = sh.run("/usr/sbin/parted %s --script print" % (self._device,))
            if "Partition Table: msdos" not in partedPrintOutput:
                return False
            if EXPECTED_PARTITION_TABLE_REGEX.search(partedPrintOutput) is None:
                return False
            return True
        except:
            return False

    def verify(self):
        if self._check():
            print "Partition table already set up"
            return
        self._create()
        if not self._check():
            raise Exception("Created partition table isn't as expected")
