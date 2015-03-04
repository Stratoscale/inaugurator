import threading
import os
import json


class ReportThread(threading.Thread):
    FIFO = "/reportFifo"

    def __init__(self, talkToServer):
        self._talkToServer = talkToServer
        os.mkfifo(self.FIFO)
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def run(self):
        while True:
            with open(self.FIFO) as f:
                report = json.load(f)
            self._talkToServer.progress(report)
