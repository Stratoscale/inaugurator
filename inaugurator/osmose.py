import subprocess
import os


class Osmose:
    def __init__(self, destination, objectStores, withLocalObjectStore):
        if withLocalObjectStore:
            localObjectStore = os.path.join(destination, "var", "lib", "osmosis", "objectstore")
            objectStores = localObjectStore + "+" + objectStores
            extra = ['--ignore', localObjectStore]
        else:
            extra = []
        self._popen = subprocess.Popen([
            "/usr/bin/osmosis", "checkout", destination, '+', '--MD5', '--putIfMissing',
            '--removeUnknownFiles', '--objectStores', objectStores] + extra,
            close_fds=True,
            stdin=subprocess.PIPE)

    def tellLabel(self, label):
        self._popen.stdin.write(label + "\n")
        self._popen.stdin.close()

    def wait(self):
        result = self._popen.wait()
        if result != 0:
            raise Exception("Osmosis failed")
