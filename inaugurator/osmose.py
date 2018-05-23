import subprocess
import os
import logging
from inaugurator import reportthread


class CorruptedObjectStore(Exception):
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)


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

    def wait(self, inspect_erros=False):
        osmosis_output = []
        error_counter = 0
        TOO_MANY_OBJECT_STORE_ERRORS = 20
        '''
        osmosis - can identify bad hash and fix them.
        the problem is that if he thinks that all the hashs are corrupted then this process will take a lot of time.
        '''
        for line in iter(self._popen.stdout.readline, b''):
            print "Osmosis:>>> %s" % line.rstrip()
            osmosis_output.append(line)
            if inspect_erros:
                if "ERROR" in line:
                    error_counter += 1
                if error_counter > TOO_MANY_OBJECT_STORE_ERRORS:
                    raise CorruptedObjectStore
        self._popen.stdout.close()
        result = self._popen.wait()
        if result != 0:
            if inspect_erros:
                raise CorruptedObjectStore
            raise Exception("Osmosis failed: return code %d output %s" % (result, '\n'.join(osmosis_output)))
