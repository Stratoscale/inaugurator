import unittest
from inaugurator.partitiontable import PartitionTable
from inaugurator import sh


class Test(unittest.TestCase):
    def setUp(self):
        self.expectedCommands = []
        sh.run = self.runShell

    def runShell(self, command):
        foundList = [x for x in self.expectedCommands if x[0] == command]
        if len(foundList) == 0:
            raise Exception("Command '%s' is not in expected commands" % command)
        found = foundList[0]
        self.expectedCommands.remove(found)
        output = found[1]
        print "Expected command run:", found
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
        self.expectedCommands.append(('''lvm vgscan --mknodes''', ""))
        self.expectedCommands.append(('''mkswap /dev/inaugurator/swap -L SWAP''', ""))
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
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)

    def test_CreatePartitionTable_OnA128GBDisk(self):
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
        self.expectedCommands.append(('''lvm vgscan --mknodes''', ""))
        self.expectedCommands.append(('''mkswap /dev/inaugurator/swap -L SWAP''', ""))
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
        tested = PartitionTable("/dev/sda")
        tested.verify()
        self.assertEquals(len(self.expectedCommands), 0)


if __name__ == '__main__':
    unittest.main()
