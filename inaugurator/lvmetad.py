import subprocess
import threading
import logging


class Lvmetad(threading.Thread):
    def __init__(self):
        self._popen = subprocess.Popen(["/usr/sbin/lvmetad", "-f"])
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def run(self):
        self._popen.wait()
        logging.error("lvmetad halted")
