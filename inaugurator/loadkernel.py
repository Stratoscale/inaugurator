import os
from inaugurator import grubconfparser
from inaugurator import sh


class LoadKernel:
    def fromBootPartitionGrubConfig(self, bootPath, rootPartition, append):
        parser = grubconfparser.GrubConfParser.fromFile(os.path.join(bootPath, "grub2", "grub.cfg"))
        sh.run("kexec --load %s --initrd=%s --append='root=%s %s %s'" % (
            os.path.join(bootPath, parser.defaultKernelImage()),
            os.path.join(bootPath, parser.defaultInitrd()),
            rootPartition,
            self._filterOutRootArgument(parser.defaultKernelCommandLine()),
            append))

    def execute(self):
        sh.run("kexec -e")

    def _filterOutRootArgument(self, commandLine):
        parts = commandLine.split(' ')
        filtered = [p for p in parts if not p.startswith("root=")]
        return " ".join(filtered)
