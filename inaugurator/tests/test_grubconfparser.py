import unittest
from inaugurator.grubconfparser import GrubConfParser
from inaugurator.tests import samplegrubconfigs


class Test(unittest.TestCase):
    def test_AsGeneratedByASimpleFedora(self):
        tested = GrubConfParser(samplegrubconfigs.AS_GENERATED_BY_A_SIMPLE_FEDORA)
        self.assertEquals(tested.defaultKernelImage(), "vmlinuz-3.11.9-200.fc19.x86_64")
        self.assertEquals(
            tested.defaultKernelCommandLine(),
            "root=UUID=7281ba4c-2700-4e8c-b2e8-95f97f3dce7c ro")
        self.assertEquals(tested.defaultInitrd(), "initramfs-3.11.9-200.fc19.x86_64.img")


if __name__ == '__main__':
    unittest.main()
