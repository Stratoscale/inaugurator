import re


class GrubConfParser:
    def __init__(self, contents):
        self._contents = contents

    @classmethod
    def fromFile(cls, path):
        with open(path) as f:
            return cls(f.read())

    def defaultKernelImage(self):
        return self._entryKernelImage(self._entries()[self._defaultIndex()])

    def defaultKernelCommandLine(self):
        return self._entryKernelCommandLine(self._entries()[self._defaultIndex()])

    def defaultInitrd(self):
        return self._entryInitrd(self._entries()[self._defaultIndex()])

    def _entries(self):
        return re.findall(r'menuentry.*?\{([\000-\377]*?)\}', self._contents)

    def _defaultIndex(self):
        match = re.search(r'set default="(\d+)"', self._contents)
        if match is None:
            return 0
        return int(match.group(1))

    def _entryKernelImage(self, entry):
        return re.search(r'\n\s*linux\s+/boot/(\S+)\s', entry).group(1)

    def _entryKernelCommandLine(self, entry):
        return re.search(r'\n\s*linux\s+/boot/\S+\s+(.*)', entry).group(1)

    def _entryInitrd(self, entry):
        return re.search(r'\n\s*initrd\s+/boot/(\S+)', entry).group(1)
