import unittest
import os
import StringIO
from inaugurator.grub import modifyingGrubConf


EXISTING_CONFIGURATION = \
"""GRUB_DEFAULT=0
GRUB_HIDDEN_TIMEOUT=0
GRUB_HIDDEN_TIMEOUT_QUIET=true
GRUB_TIMEOUT=10
GRUB_DISTRIBUTOR=`lsb_release -i -s 2> /dev/null || echo Debian`
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUB_CMDLINE_LINUX=""
GRUB_DISABLE_OS_PROBER=true
"""

class Test(unittest.TestCase):
    def setUp(self):
        self.existing_conf_pairs = dict(item.split("=", 1) for item in EXISTING_CONFIGURATION.splitlines())
        self.output = StringIO.StringIO()

    def _verify_not_linux_cmdline_equals(self):
        self.modified_conf_pairs = dict(item.split("=", 1) for item in self.output.getvalue().splitlines())
        [self.assertEqual(self.existing_conf_pairs[k], self.modified_conf_pairs[k])
            for k in self.existing_conf_pairs.keys() if not k.startswith('')]

    def test_console_and_passthrough_valid_values(self):
        modifyingGrubConf(self.output, EXISTING_CONFIGURATION,
                          ["ttyS1,115200n8"], "memmap=16G!64G")
        self._verify_not_linux_cmdline_equals()
        self.assertEqual(self.modified_conf_pairs['GRUB_CMDLINE_LINUX'], '" console=ttyS1,115200n8 memmap=16G!64G"')

    def test_console_and_multipe_passthrough_valid_values(self):
        modifyingGrubConf(self.output, EXISTING_CONFIGURATION,
                          ["ttyS1,115200n8"], "memmap=16G!64G,memmap=16G!80G")
        self._verify_not_linux_cmdline_equals()
        self.assertEqual(self.modified_conf_pairs['GRUB_CMDLINE_LINUX'], '" console=ttyS1,115200n8 memmap=16G!64G memmap=16G!80G"')


    def _test_console_and_passthrough_non_values(self, console, passthrough):
        modifyingGrubConf(self.output, EXISTING_CONFIGURATION, console, passthrough)
        self._verify_not_linux_cmdline_equals()
        self.assertEqual(self.modified_conf_pairs['GRUB_CMDLINE_LINUX'], '"  "')

    def test_console_and_passthrough_empty_values(self):
        self._test_console_and_passthrough_non_values([], "")

    def test_none_values(self):
        self._test_console_and_passthrough_non_values(None, None)

if __name__ == '__main__':
    unittest.main()
