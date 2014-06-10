import socket
from inaugurator.server import config


class CheckInWithServer:
    def __init__(self, hostname):
        self._hostname = hostname
        self._label = self._fetchLabel()

    def label(self):
        return self._label

    def done(self):
        sock = socket.socket()
        try:
            sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
            sock.connect((self._hostname, config.PORT))
            sock.send("done")
        finally:
            sock.close()

    def _fetchLabel(self):
        sock = socket.socket()
        try:
            sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
            sock.connect((self._hostname, config.PORT))
            sock.send("checkin")
            return sock.recv(4096)
        finally:
            sock.close()
