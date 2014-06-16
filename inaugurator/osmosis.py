import subprocess


class Osmosis:
    def __init__(self, destination, objectStores):
        self._popen = subprocess.Popen([
            "/usr/bin/osmosis", "checkout", destination, '+', '--MD5',
            '--removeUnknownFiles', '--objectStores', objectStores],
            close_fds=True,
            stdin=subprocess.PIPE)

    def tellLabel(self, label):
        self._popen.stdin.write(label + "\n")
        self._popen.stdin.close()

    def wait(self):
        result = self._popen.wait()
        if result != 0:
            raise Exception("Osmosis failed")
