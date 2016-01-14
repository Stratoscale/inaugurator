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
                try:
                    logging.info('command: \"{}\"'.format(cmd))
                    logging.info(sh.run(cmd))
                except:
                    traceback.print_exc(file=sys.stdout)
