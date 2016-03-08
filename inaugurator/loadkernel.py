import os
import logging
from inaugurator import grubconfparser
from inaugurator import sh


class LoadKernel:
    def fromBootPartitionGrubConfig(self, grubConfig, bootPath, rootPartition, append):
        parser = grubconfparser.GrubConfParser(grubConfig)
        sh.run("kexec --load %s --initrd=%s --append='root=%s %s %s'" % (
            os.path.join(bootPath, parser.defaultKernelImage()),
            os.path.join(bootPath, parser.defaultInitrd()),
            rootPartition,
            self._filterWhiteList(parser.defaultKernelCommandLine()),
            append))

    def execute(self):
        sh.run("kexec -e")

    def _filterWhiteList(self, commandLine):
        allowed = ("console", "ro")
        parts = commandLine.split(' ')
        filtered = [p for p in parts if [field for field in allowed if p.startswith(field + "=")
                                         or p == field]]
        result = " ".join(filtered)
        logging.info("Adding the following kernel arguments from the GRUB2 Configuration: %s" % (result))
        return result
