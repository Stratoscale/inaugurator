import re
import traceback
import time
from inaugurator import sh


class PartitionTable:
    def __init__(self, device):
        self._device = device
        self._cachedDiskSize = None
        self._created = False

    def created(self):
        return self._created

    def clear(self):
        sh.run("/usr/sbin/busybox dd if=/dev/zero of=%s bs=1M count=512" % self._device)

    def _create(self):
        self.clear()
        table = self._expected()
        script = "echo -ne '%s' | sfdisk --unit M %s --in-order --force" % (
            self._sfdiskScript(table), self._device)
        print "creating new partition table:", script
        sh.run(script)
        sh.run("/usr/sbin/busybox mdev -s")
        for partition in table:
            if partition['id'] == 82:
                print "creating swapspace on %s" % partition['device']
                sh.run("/usr/sbin/mkswap %s" % partition['device'])
            elif partition['id'] == 83:
                print "creating ext4 filesystem on %s" % partition['device']
                sh.run("/usr/sbin/mkfs.ext4 %s" % partition['device'])
            else:
                assert False, "Unrecognized partition id: %d" % partition['id']
        self._created = True

    def parse(self):
        LINE = re.compile(r"(/\S+) : start=\s*\d+, size=\s*(\d+), Id=\s*(\d+)")
        lines = LINE.findall(sh.run("/usr/sbin/sfdisk --dump %s" % self._device))
        return [
            dict(device=device, sizeMB=int(size) * 512 / 1024 / 1024, id=int(id))
            for device, size, id in lines if int(size) > 0]

    def _diskSizeMB(self):
        if self._cachedDiskSize is None:
            self._cachedDiskSize = int(sh.run("/usr/sbin/sfdisk -s %s" % self._device).strip()) / 1024
        return self._cachedDiskSize

    def _expected(self):
        swapSizeMB = 1024 if self._diskSizeMB() <= 32 * 1024 else 8 * 1024
        return [
            dict(device="%s1" % self._device, sizeMB=256, id=83),
            dict(device="%s2" % self._device, sizeMB=swapSizeMB, id=82),
            dict(device="%s3" % self._device, sizeMB='fill', id=83)]

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

    def _findMismatch(self):
        try:
            parsed = self.parse()
        except:
            print "Unable to parse partition table"
            traceback.print_exc()
            return "Unable to parse partition table"
        expected = self._expected()
        if len(parsed) != len(expected):
            return "Partition count not as expected"
        if parsed[2]['sizeMB'] < self._diskSizeMB() * 3 / 4:
            return "Partition 2 does not take up 3/4 of the disk"
        for i in xrange(len(parsed)):
            if parsed[i]['id'] != expected[i]['id']:
                return "Expected id of partition %d" % i
            if expected[i]['sizeMB'] != 'fill' and (
                    parsed[i]['sizeMB'] < expected[i]['sizeMB'] * 0.9 or
                    parsed[i]['sizeMB'] > expected[i]['sizeMB'] * 1.1):
                return "Expected size of partition %d" % i
        return None

    def verify(self):
        if not self._findMismatch():
            print "Partition table already set up"
            return
        self._create()
        for retry in xrange(5):
            mismatch = self._findMismatch()
            if mismatch is None:
                return
            else:
                print "Partition table not correct even after %d retries" % retry
                time.sleep(0.2)
        print "Expected:", self._expected()
        print "Found:", self.parse()
        print "Mismatch:", self._findMismatch()
        raise Exception("Created partition table isn't as expected")
