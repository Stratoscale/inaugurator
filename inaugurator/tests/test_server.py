import os
import sys
import mock
import signal
import logging
import unittest
import pika
assert 'usr' not in __file__.split(os.path.sep)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from inaugurator.server import server


class Test(unittest.TestCase):
    def setUp(self):
        server.pika = mock.Mock()
        self.fakeKill = mock.Mock()
        os.kill = self.fakeKill

    def checkInCallback(self):
        pass

    def doneInCallback(self):
        pass

    def checkInCallback(self):
        pass

    def progressInCallback(self):
        pass

    def failedCallback(self):
        pass

    def test_KillSelfInCasePikaConnectionCreationFailed(self):
        originalSelectConnection = server.pika.SelectConnection
        server.pika.SelectConnection = mock.Mock(side_effect=Exception("Catch me"))

        server.threading.Thread.__init__ = mock.Mock()
        server.threading.Thread.start = mock.Mock()
        server.threading.Thread.daemon = mock.Mock()
        server.threading.Event = mock.Mock()
        self.tested = server.Server(self.checkInCallback, self.doneInCallback, self.progressInCallback,
                                    self.failedCallback)
        with self.assertRaises(Exception):
            self.tested.run()
        self.fakeKill.assert_called_once_with(os.getpid(), signal.SIGTERM)

if __name__ == '__main__':
    _logger = logging.getLogger("inaugurator.server")
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
    unittest.main()
