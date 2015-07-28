import unittest
import shutil
import tempfile
import time
import subprocess
import os
import functools
import threading
import mock
import patchsyspath
from inaugurator.server import server
from inaugurator.server import rabbitmqwrapper
from inaugurator.server import config
from inaugurator import talktoserver

patchsyspath.validatePaths()
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
        self.auxLabelIDCounter = 0

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
        talk.close()

    def sendProgress(self, id, message):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.progress(message)
        talk.close()

    def sendDone(self, id):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.done()
        talk.close()

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
            self.validateCheckIn(tested, "eliran")
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

    def test_Progress(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("eliran")
            self.validateProgress(tested, "eliran", "awesome-progress-message")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.checkInCallbackArguments, [])
        finally:
            tested.close()

    def test_Done(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("eliran")
            self.validateDone(tested, "eliran")
            self.assertEquals(self.progressCallbackArguments, [])
            self.assertEquals(self.checkInCallbackArguments, [])
        finally:
            tested.close()

    def sendOneStatusMessageAndCheckArrival(self, sendMethod, callbackArguments, id, extraArgs):
        if extraArgs is None:
            extraArgs = tuple()
        sendMethod(id, *extraArgs)
        hasMessageArrived = (id,) + extraArgs in callbackArguments
        return hasMessageArrived

    def validateStatusMessageArrival(self, tested, statusMessageType, id, extraArgs=None,
                                     isArrivalExpected=True):
        statusMessageTypes = dict(checkin=(self.sendCheckIn, self.checkInCallbackArguments),
                                  progress=(self.sendProgress, self.progressCallbackArguments),
                                  done=(self.sendDone, self.doneCallbackArguments))
        sendMethod, callbackArguments = statusMessageTypes[statusMessageType]
        validateMethod = functools.partial(self.sendOneStatusMessageAndCheckArrival, sendMethod,
                                           callbackArguments, id, extraArgs)
        if isArrivalExpected:
            self.assertEqualsWithinTimeout(validateMethod, True)
            self.waitTillStatusQueueIsCleanByAbusingProgressCallbacks(id, tested)
            while callbackArguments:
                callbackArguments.pop()
        else:
            self.assertEqualsDuringPeriod(validateMethod, False)

    def validateCheckInDoesNotWork(self, tested, id):
        self.validateStatusMessageArrival(tested, "checkin", id, isArrivalExpected=False)

    def validateCheckIn(self, tested, id):
        self.validateStatusMessageArrival(tested, "checkin", id)

    def validateProgress(self, tested, id, message):
        self.validateStatusMessageArrival(tested, "progress", id, extraArgs=(message,))

    def validateDone(self, tested, id):
        self.validateStatusMessageArrival(tested, "done", id)

    def waitTillStatusQueueIsCleanByAbusingProgressCallbacks(self, idWhichIsListenedTo, tested):
        self.unreportedProgressMessageEvent = threading.Event()
        self.sendProgress(idWhichIsListenedTo, self.UNREPORTED_PROGRESS_MESSAGE)
        if not self.unreportedProgressMessageEvent.wait(timeout=1):
            raise AssertionError("Progress callback was not invoked at time")

    def waitTillAllCommandsWereExecutedByTheServer(self, tested):
        auxID = "IDWhichIsUsedToValidateThatTheServerHasFinishedAllPendingCommands_%(counter)s" % \
            dict(counter=self.auxLabelIDCounter)
        self.auxLabelIDCounter += 1
        tested.listenOnID(auxID)
        self.validateStatusMessageArrival(tested, "checkin", auxID)

    def invokeStopListeningAndWaitTillDone(self, tested, id):
        tested.stopListeningOnID(id)
        self.waitTillAllCommandsWereExecutedByTheServer(tested)

    def test_ExceptionInCallbackDoesNotCrashServer(self):
        badCheckInCallback = mock.Mock(side_effect=Exception("Exception during checkin, ignore me"))
        badProgressCallback = mock.Mock(side_effect=Exception("Exception during progress, ignore me"))
        badDoneCallback = mock.Mock(side_effect=Exception("Exception during done, ignore me"))
        tested = server.Server(badCheckInCallback, badDoneCallback, badProgressCallback)
        try:
            tested.listenOnID("yuvu")
            self.validateCheckInDoesNotWork(tested, "yuvu")
            self.assertGreater(badCheckInCallback.call_count, 0)
            checkInAttemptsArgs = set([arg[0] for arg in badCheckInCallback.call_args_list])
            self.assertEquals(checkInAttemptsArgs, set([("yuvu",)]))
            self.validateStatusMessageArrival(tested, "progress", "yuvu", isArrivalExpected=False,
                                              extraArgs=("fake progress message",))
            progressAttemptArgs = set([arg[0] for arg in badProgressCallback.call_args_list])
            self.assertEquals(set([("yuvu", "fake progress message")]), progressAttemptArgs)
            self.validateStatusMessageArrival(tested, "done", "yuvu", isArrivalExpected=False)
            doneAttemptArgs = set([arg[0] for arg in badDoneCallback.call_args_list])
            self.assertEquals(set([("yuvu",)]), doneAttemptArgs)
            self.assertTrue(tested.isAlive())
        finally:
            tested.close()

    def test_ProvideLabel(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback)
        try:
            tested.listenOnID("yuvu")
            self.validateCheckIn(tested, "yuvu")
            talk = talktoserver.TalkToServer(config.AMQP_URL, "yuvu")
            tested.provideLabel("yuvu", "thecoolestlabel")
            self.assertEqual(talk.label(), "thecoolestlabel")
        finally:
            talk.close()
            tested.close()

if __name__ == '__main__':
    unittest.main()
