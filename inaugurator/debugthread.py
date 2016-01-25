import sys
import time
import socket
import logging
import traceback
import threading
from inaugurator import sh


PORT = 8888


class DebugThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self._wasRebootCalled = False
        self.start()

    def run(self):
        HOST = ''
        s = socket.socket()
        try:
            s.bind((HOST, PORT))
        except socket.error as msg:
            logging.info('Failed binding debug port. Error Code : %(code)s. Message: %(message)s',
                         dict(code=msg[0], message=msg[1]))
            raise
        while True:
            logging.info('Debug socket now listening on port %(port)s', dict(port=PORT))
            s.listen(10)
            conn, addr = s.accept()
            time.sleep(1)
            logging.info('Connected with %(addr)s:%(port)s.', dict(addr=addr[0], port=addr[1]))
            while True:
                time.sleep(1)
                try:
                    logging.info('waiting for a command...')
                    cmd = conn.recv(1000)
                except:
                    traceback.print_exc(file=sys.stdout)
                    break
                if not cmd:
                    logging.info('Got disconnected.')
                    break
                if cmd == "REBOOT":
                    self._wasRebootCalled = True
                    logging.info("Killing osmosis...")
                    try:
                        sh.run("pkill -9 osmosis")
                    except:
                        logging.error("Failed killing osmosis")
                    logging.info("Flushing FS...")
                    try:
                        sh.run("sync")
                    except:
                        logging.error("Failed running sync.")
                    logging.info("Rebooting...")
                    # Sleep so that there will be enough time for the log to be printed
                    time.sleep(1)
                    logging.info(sh.run("reboot -f"))
                try:
                    logging.info('command: \"{}\"'.format(cmd))
                    logging.info(sh.run(cmd))
                except:
                    traceback.print_exc(file=sys.stdout)

    def wasRebootCalled(self):
        return self._wasRebootCalled
