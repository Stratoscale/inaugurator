import socket
from inaugurator import server
import inaugurator.server.config


class CheckInWithServer:
    def __init__(self, hostname):
        self._hostname = hostname
        self._label = self._fetchLabel(hostname)

    def label(self):
        return self._label

    def _fetchLabel(self, hostname):
        sock = socket.socket()
        try:
            sock.connect((hostname, server.config.PORT))
            return sock.recv(4096)
        finally:
            sock.close()
