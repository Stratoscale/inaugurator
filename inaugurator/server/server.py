import threading
import socket
import logging
from inaugurator.server import config


class Server(threading.Thread):
    def __init__(self, bindHostname, checkInCallback, doneCallback):
        self._checkInCallback = checkInCallback
        self._doneCallback = doneCallback
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((bindHostname, config.PORT))
        self._sock.listen(100)
        self._connections = {}
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def provideLabel(self, ipAddress, label):
        connection = self._connections[ipAddress]
        try:
            del self._connections[ipAddress]
            connection.send(label)
            connection.shutdown(socket.SHUT_WR)
        finally:
            connection.close()

    def run(self):
        while True:
            try:
                self._work()
            except:
                logging.exception("Unable to serve inaugurator request")

    def _work(self):
        connection, peer = self._sock.accept()
        ip = peer[0]
        keepConnectionOpen = False
        try:
            connection.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
            command = connection.recv(16)
            if command == "checkin":
                self._safeHangup(ip)
                self._connections[ip] = connection
                self._checkInCallback(ipAddress=ip)
                keepConnectionOpen = True
            elif command == "done":
                self._doneCallback(ipAddress=ip)
            else:
                raise Exception("Unknown command '%s'" % command)
        except:
            self._safeHangup(ip)
            raise
        finally:
            if not keepConnectionOpen:
                connection.close()

    def _safeHangup(self, ipAddress):
        if ipAddress in self._connections:
            connection = self._connections[ipAddress]
            del self._connections[ipAddress]
            try:
                connection.close()
            except:
                pass
