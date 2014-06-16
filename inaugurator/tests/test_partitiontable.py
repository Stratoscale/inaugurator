import unittest
from inaugurator.partitiontable import PartitionTable
from inaugurator import sh


class Test(unittest.TestCase):
    def setUp(self):
        self.expectedCommands = []
        sh.run = self.runShell

    def runShell(self, command):
        found = [x for x in self.expectedCommands if x[0] == command][0]
        self.expectedCommands.remove(found)
        output = found[1]
        return output

    def test_Simple(self):
        example = "\n".join([
            "# partition table of /dev/sda",
            "unit: sectors",
            "",
            "/dev/sda1 : start=     2048, size= 16023552, Id=82",
            "/dev/sda2 : start= 16025600, size=484091904, Id=83, bootable",
            "/dev/sda3 : start=        0, size=        0, Id= 0",
            "/dev/sda4 : start=        0, size=        0, Id= 0",
            ""])
        self.expectedCommands.append(('/usr/sbin/sfdisk --dump /dev/sda', example))
        tested = PartitionTable("/dev/sda")
        parsed = tested._parse()
        self.assertEquals(len(parsed), 2)
        self.assertEquals(parsed[0]['device'], '/dev/sda1')
        self.assertEquals(parsed[0]['sizeMB'], 16023552 / 2 / 1024)
        self.assertEquals(parsed[0]['id'], 82)
        self.assertEquals(parsed[1]['device'], '/dev/sda2')
        self.assertEquals(parsed[1]['sizeMB'], 484091904 / 2 / 1024)
        self.assertEquals(parsed[1]['id'], 83)


if __name__ == '__main__':
    unittest.main()
