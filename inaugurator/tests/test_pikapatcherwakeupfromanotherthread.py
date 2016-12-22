import os
import sys
import pika
import mock
import select
import logging
import unittest
import collections
assert 'usr' not in __file__.split(os.path.sep)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from inaugurator.server import pikapatchwakeupfromanotherthread


class Poller:
    def __init__(self):
        self._poll = select.epoll()

    def register(self, fd, events):
        self._poll.register(fd, events)

    def poll(self):
        events = self._poll.poll(timeout=0)
        return events


class IOLoop:
    def __init__(self):
        self._poller = Poller()
        self.handlers = dict()
        self.flags = dict()

    def add_handler(self, fd, handler, flags):
        self.handlers[fd] = handler
        self.flags[fd] = handler
        self._poller.register(fd, select.EPOLLIN)

    def start(self):
        while True:
            events = self._poller.poll()
            if not events:
                break
            for fd, flags in events:
                self.handlers[fd]()


class ConnectionMock:
    READ = 'SomeValue'

    def __init__(self):
        self.ioloop = IOLoop()


class InvalidConnectionMock:
    def __init__(self):
        pass


class UnitHasKilledItself(Exception):
    pass


class Test(unittest.TestCase):
    def setUp(self):
        self.killMock = mock.Mock(side_effect=UnitHasKilledItself())
        self.origKill = os.kill
        self.connectionMock = ConnectionMock()
        try:
            os.kill = self.killMock
            self.tested = pikapatchwakeupfromanotherthread.PikaPatchWakeUpFromAnotherThread(
                self.connectionMock)
        finally:
            os.kill = self.origKill

    def test_InvalidConnection(self):
        invalidConnectionMock = InvalidConnectionMock()
        try:
            os.kill = self.killMock
            self.assertRaises(UnitHasKilledItself,
                              pikapatchwakeupfromanotherthread.PikaPatchWakeUpFromAnotherThread,
                              invalidConnectionMock)
        finally:
            os.kill = self.origKill

    def test_PatchValues(self):
        self.assertEquals(len(self.connectionMock.ioloop.handlers), 1)
        self.assertEquals(len(self.connectionMock.ioloop.flags), 1)
        self.assertEquals(self.connectionMock.ioloop.handlers.keys(),
                          self.connectionMock.ioloop.flags.keys())
        self.connectionMock.ioloop.flags.values()[0] == ConnectionMock.READ

    def test_RunInThread(self):
        someCommand = mock.Mock()
        kwargs = dict(a=1, b=1)
        self.tested.runInThread(someCommand, **kwargs)
        self.connectionMock.ioloop.start()
        someCommand.assert_called_once_with(**kwargs)

    def test_RunInThreadWithExceptionInCallbackDoesNotCrash(self):
        someCommand = mock.Mock()
        someCommandWithException = mock.Mock(side_effect=Exception("Ignore me."))
        kwargs = dict(a=1, b=1)
        self.tested.runInThread(someCommandWithException, **kwargs)
        self.tested.runInThread(someCommand, **kwargs)
        self.connectionMock.ioloop.start()
        someCommand.assert_called_once_with(**kwargs)
        someCommandWithException.assert_called_once_with(**kwargs)

if __name__ == "__main__":
    _logger = logging.getLogger("inaugurator.server")
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
    unittest.main()
