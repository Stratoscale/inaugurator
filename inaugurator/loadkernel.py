import os
import logging
from inaugurator import grubconfparser
from inaugurator import sh


class LoadKernel:
    def fromBootPartitionGrubConfig(self, grubConfig, bootPath, rootPartition):
        parser = grubconfparser.GrubConfParser(grubConfig)
        sh.run("kexec --load %s --initrd=%s --append='root=%s %s'" % (
            os.path.join(bootPath, parser.defaultKernelImage()),
            os.path.join(bootPath, parser.defaultInitrd()),
            rootPartition,
            self._filterOutRootArgument(parser.defaultKernelCommandLine())))

    def execute(self):
        sh.run("kexec -e")

    def _filterOutRootArgument(self, commandLine):
        parts = commandLine.split(' ')
        filtered = [p for p in parts if not p.startswith("root=")]
        result = " ".join(filtered)
        logging.info("Adding the following kernel arguments from the GRUB2 Configuration: '%s'." % (result))
        return result
