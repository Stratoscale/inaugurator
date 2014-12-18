import subprocess
import os
import logging


class Osmose:
    def __init__(self, destination, objectStores, withLocalObjectStore):
        logging.info("Osmosing parameters: withLocalObjectStore: %(withLocalObjectStore)s", dict(
            withLocalObjectStore=withLocalObjectStore))
        if withLocalObjectStore:
            localObjectStore = os.path.join(destination, "var", "lib", "osmosis", "objectstore")
            objectStores = localObjectStore + "+" + objectStores
            extra = ['--ignore', localObjectStore]
        else:
            extra = []
        cmd = [
            "/usr/bin/osmosis", "checkout", destination, '+', '--MD5', '--putIfMissing',
            '--removeUnknownFiles', '--objectStores', objectStores] + extra
        print "Running osmosis:\n%s" % " ".join(cmd)
        self._popen = subprocess.Popen(cmd, close_fds=True, stdin=subprocess.PIPE)

    def tellLabel(self, label):
        self._popen.stdin.write(label + "\n")
        self._popen.stdin.close()

    def wait(self):
        result = self._popen.wait()
        if result != 0:
            raise Exception("Osmosis failed")
