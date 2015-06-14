import unittest
import shutil
import tempfile
import time
import subprocess
import os
import sys
assert 'usr' not in __file__.split(os.path.sep)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from inaugurator.server import server
from inaugurator.server import rabbitmqwrapper
from inaugurator.server import config
from inaugurator import talktoserver
config.PORT = 2018
config.AMQP_URL = "amqp://guest:guest@localhost:%d/%%2F" % config.PORT
import mock


class Test(unittest.TestCase):
    def setUp(self):
        output = subprocess.check_output(["ps", "-Af"])
        if 'beam.smp' in output:
            raise Exception("It seems a previous instance of rabbitMQ is already running. "
                            "Kill it to run this test")
        self.tempdir = tempfile.mkdtemp()
        self.rabbitMQWrapper = rabbitmqwrapper.RabbitMQWrapper(self.tempdir)
        self.checkInCallbackArguments = []
        self.doneCallbackArguments = []
        self.progressCallbackArguments = []

    def tearDown(self):
        self.rabbitMQWrapper.cleanup()
        with open(os.path.join(self.tempdir, "log.txt")) as f:
            log = f.read()
        print log
        shutil.rmtree(self.tempdir, ignore_errors=True)
        time.sleep(1)

    def checkInCallback(self, *args):
        self.checkInCallbackArguments.append(args)

    def doneCallback(self, *args):
        self.doneCallbackArguments.append(args)

    def progressCallback(self, *args):
        self.progressCallbackArguments.append(args)

    def sendCheckIn(self, id):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.checkIn()

    def assertEqualsWithinTimeout(self, callback, expected, interval=0.1, timeout=3):
        before = time.time()
        while time.time() < before + timeout:
            try:
                if callback() == expected:
                    return
            except:
                time.sleep(interval)
        self.assertEquals(callback(), expected)

    def test_CheckIn(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("eliran")
            self.sendCheckIn("eliran")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments), [("eliran",)])
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            tested.close()

    def test_StopListening(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments), [("yuvu",)])
            tested.stopListeningOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments), [("yuvu",)])
            tested.listenOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments), [("yuvu",), ("yuvu",)])
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            tested.close()

    def test_StopListeningDoesNotAffectAnotherServer(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("yuvu")
            tested.listenOnID("jakarta")
            self.sendCheckIn("yuvu")
            self.sendCheckIn("jakarta")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments),
                                           [("yuvu",), ("jakarta",)])
            tested.stopListeningOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.sendCheckIn("jakarta")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments),
                                           [("yuvu",), ("jakarta",), ("jakarta",)])
            tested.listenOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.sendCheckIn("jakarta")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments),
                                           [("yuvu",), ("jakarta",), ("jakarta",), ("yuvu",), ("jakarta",)])
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            self.assertTrue(tested.isAlive())
            tested.close()

    def test_SendCommand(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("eliran")
            talk = talktoserver.TalkToServer(config.AMQP_URL, "eliran")
            tested.provideLabel("eliran", "fake label")
            self.assertEquals(talk.label(), "fake label")
        finally:
            tested.close()

    def test_ExceptionInCallbackDoesNotCrashServer(self):
        raiseExceptionMock = mock.Mock()
        raiseExceptionMock.side_effect = Exception("I'm an exception")
        tested = server.Server(raiseExceptionMock, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments), [])
            self.assertTrue(tested.isAlive())
        finally:
            tested.close()


if __name__ == '__main__':
    unittest.main()
