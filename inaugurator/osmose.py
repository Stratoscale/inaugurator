import subprocess
import os
import logging
from inaugurator import reportthread


class Osmose:
    def __init__(self, destination, objectStores, withLocalObjectStore, ignoreDirs, talkToServer,
                 localObjectStore=None):
        absoluteIgnoreDirs = [os.path.join(destination, ignoreDir) for ignoreDir in ignoreDirs]
        logging.info("Osmosing parameters: withLocalObjectStore: %(withLocalObjectStore)s", dict(
            withLocalObjectStore=withLocalObjectStore))
        if withLocalObjectStore:
            assert localObjectStore is not None, "Must provide local object store path when osmosing " \
                                                 "from the local object store"
            osmosisDir = os.path.join(destination, "var", "lib", "osmosis")
            if os.path.islink(osmosisDir):
                logging.info("It appears that the osmosis directory is a symbolic link. Removing it...")
                os.unlink(osmosisDir)
                logging.info("Sybmolic link removed.")
            localObjectStore = os.path.join(osmosisDir, "objectstore")
            absoluteIgnoreDirs.append(localObjectStore)
        elif localObjectStore is not None:
            localObjectStore = os.path.join(localObjectStore, "objectstore")

        if localObjectStore is not None:
            objectStores = localObjectStore + ("+" + objectStores if objectStores else "")

        extra = []
        if absoluteIgnoreDirs:
            extra += ['--ignore', ":".join(absoluteIgnoreDirs)]
        if talkToServer is not None:
            reportthread.ReportThread(talkToServer)
            extra += ['--reportFile', reportthread.ReportThread.FIFO]
        cmd = [
            "/usr/bin/osmosis", "checkout", destination, '+', '--MD5', '--putIfMissing',
            '--removeUnknownFiles', '--objectStores', objectStores] + extra
        print "Running osmosis:\n%s" % " ".join(cmd)
        self._popen = subprocess.Popen(cmd, close_fds=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def tellLabel(self, label):
        self._popen.stdin.write(label + "\n")
        self._popen.stdin.close()

    def wait(self):
        osmosis_output = []
        for line in iter(self._popen.stdout.readline, b''):
            print "Osmosis:>>> %s" % line.rstrip()
            osmosis_output.append(line)
        self._popen.stdout.close()
        result = self._popen.wait()
        if result != 0:
            raise Exception("Osmosis failed: return code %d output %s" % (result, '\n'.join(osmosis_output)))
