import unittest
import shutil
import tempfile
import time
import subprocess
import os
import sys
import functools
import threading
assert 'usr' not in __file__.split(os.path.sep)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from inaugurator.server import server
from inaugurator.server import rabbitmqwrapper
from inaugurator.server import config
from inaugurator import talktoserver
config.PORT = 2018
config.AMQP_URL = "amqp://guest:guest@localhost:%d/%%2F" % config.PORT


class Test(unittest.TestCase):
    UNREPORTED_PROGRESS_MESSAGE = "unreportedProgressMessage"

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
        self.progressWaitEvents = dict()
        self.unreportedProgressMessageEvent = None

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
        message = args[1]
        if message == self.UNREPORTED_PROGRESS_MESSAGE:
            self.unreportedProgressMessageEvent.set()
            return
        self.progressCallbackArguments.append(args)

    def sendCheckIn(self, id):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.checkIn()

    def sendProgress(self, id, message):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.progress(message)

    def assertEqualsWithinTimeout(self, callback, expected, interval=0.1, timeout=3):
        before = time.time()
        while time.time() < before + timeout:
            try:
                if callback() == expected:
                    return
            except:
                time.sleep(interval)
        self.assertEquals(callback(), expected)

    def assertEqualsDuringPeriod(self, callback, expected, interval=0.1, period=1):
        before = time.time()
        while time.time() < before + period:
            self.assertEquals(callback(), expected)
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
            self.validateCheckIn(tested, "yuvu")
            self.invokeStopListeningAndWaitTillDone(tested, "yuvu")
            self.validateCheckInDoesNotWork(tested, "yuvu")
            tested.listenOnID("yuvu")
            self.validateCheckIn(tested, "yuvu")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            tested.close()

    def test_StopListeningDoesNotAffectAnotherServer(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("jakarta")
            tested.listenOnID("yuvu")
            self.sendCheckIn("yuvu")
            self.validateCheckIn(tested, "yuvu")
            self.validateCheckIn(tested, "jakarta")
            self.invokeStopListeningAndWaitTillDone(tested, "yuvu")
            self.validateCheckIn(tested, "jakarta")
            self.validateCheckInDoesNotWork(tested, "yuvu")
            tested.listenOnID("yuvu")
            self.validateCheckIn(tested, "yuvu")
            self.validateCheckIn(tested, "jakarta")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            tested.close()

    def test_StopListeningOnAnIDWhichIsNotListenedTo(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            self.invokeStopListeningAndWaitTillDone(tested, "yuvu")
            self.validateCheckInDoesNotWork(tested, "yuvu")
        finally:
            tested.close()

    def test_ListenTwiceOnSameID(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("yuvu")
            self.validateCheckIn(tested, "yuvu")
            tested.listenOnID("yuvu")
            self.validateCheckIn(tested, "yuvu")
            self.invokeStopListeningAndWaitTillDone(tested, "yuvu")
            self.validateCheckInDoesNotWork(tested, "yuvu")
        finally:
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

    def checkInAndCheckIfMessageArrived(self, id):
        self.sendCheckIn(id)
        return (id,) in self.checkInCallbackArguments

    def validateCheckIn(self, tested, id):
        self.assertEqualsWithinTimeout(functools.partial(self.checkInAndCheckIfMessageArrived, id), True)
        self.waitTillStatusQueueIsCleanByAbusingProgressCallbacks(id, tested)
        self.checkInCallbackArguments = []

    def validateCheckInDoesNotWork(self, tested, id):
        self.assertEqualsDuringPeriod(functools.partial(self.checkInAndCheckIfMessageArrived, id), False)

    def waitTillStatusQueueIsCleanByAbusingProgressCallbacks(self, idWhichIsListenedTo, tested):
        self.unreportedProgressMessageEvent = threading.Event()
        self.sendProgress(idWhichIsListenedTo, self.UNREPORTED_PROGRESS_MESSAGE)
        if not self.unreportedProgressMessageEvent.wait(timeout=1):
            raise AssertionError("Progress callback was not invoked at time")

    def waitTillAllCommandsWereExecutedByTheServer(self, tested):
        self.auxIDCounter = 0
        auxID = "IDWhichIsUsedToValidateThatTheServerHasFinishedAllPendingCommands_%(counter)s" % \
            dict(counter=self.auxIDCounter)
        self.auxIDCounter += 1
        tested.listenOnID(auxID)
        self.validateCheckIn(tested, auxID)

    def invokeStopListeningAndWaitTillDone(self, tested, id):
        tested.stopListeningOnID(id)
        self.waitTillAllCommandsWereExecutedByTheServer(tested)


if __name__ == '__main__':
    unittest.main()
