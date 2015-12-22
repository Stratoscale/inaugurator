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
import logging
import pika
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
        self._logger = logging.getLogger("inaugurator.server")
        output = subprocess.check_output(["ps", "-Af"])
        if 'beam.smp' in output:
            raise Exception("It seems a previous instance of rabbitMQ is already running. "
                            "Kill it to run this test")
        self.tempdir = tempfile.mkdtemp()
        self.rabbitMQWrapper = rabbitmqwrapper.RabbitMQWrapper(self.tempdir)
        self.checkInCallbackArguments = []
        self.doneCallbackArguments = []
        self.progressCallbackArguments = []
        self.purgeCallbackArguments = []
        self.progressWaitEvents = dict()
        self.unreportedProgressMessageEvent = None
        self.auxLabelIDCounter = 0

    def tearDown(self):
        self.rabbitMQWrapper.cleanup()
        with open(os.path.join(self.tempdir, "log.txt")) as f:
            log = f.read()
        self._logger.info(log)
        shutil.rmtree(self.tempdir, ignore_errors=True)
        time.sleep(1)

    def test_CheckIn(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("eliran")
            self.validateCheckIn(tested, "eliran")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            tested.close()

    def test_StopListening(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
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
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
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
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            self.invokeStopListeningAndWaitTillDone(tested, "yuvu")
            self.validateCheckInDoesNotWork(tested, "yuvu")
        finally:
            tested.close()

    def test_ListenTwiceOnSameID(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
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
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("eliran")
            self.validateProgress(tested, "eliran", "awesome-progress-message")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.checkInCallbackArguments, [])
        finally:
            tested.close()

    def test_Done(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("eliran")
            self.validateDone(tested, "eliran")
            self.assertEquals(self.progressCallbackArguments, [])
            self.assertEquals(self.checkInCallbackArguments, [])
        finally:
            tested.close()

    def test_ExceptionInCallbackDoesNotCrashServer(self):
        badCheckInCallback = mock.Mock(side_effect=Exception("Exception during checkin, ignore me"))
        badProgressCallback = mock.Mock(side_effect=Exception("Exception during progress, ignore me"))
        badDoneCallback = mock.Mock(side_effect=Exception("Exception during done, ignore me"))
        badPurgeCallback = mock.Mock(side_effect=Exception("Exception during purge, ignore me"))
        tested = server.Server(badCheckInCallback, badDoneCallback, badProgressCallback,
                               badPurgeCallback)
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
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("yuvu")
            self.validateCheckIn(tested, "yuvu")
            talk = talktoserver.TalkToServer(config.AMQP_URL, "yuvu")
            tested.provideLabel("yuvu", "thecoolestlabel")
            self.assertEqual(talk.label(), "thecoolestlabel")
        finally:
            tested.close()

    def test_AllConsumersOfLabelQueueGetTheLabel(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("yuvu")
            nrConsumers = 10
            consumers = list()

            def checkLabel(consumer, idx):
                self._logger.info('Waiting for label in consumer %(idx)s', dict(idx=idx))
                consumer['receivedLabel'] = consumer['talk'].label()
                self._logger.info('Consumer %(idx)s has received a label.', dict(idx=idx))
                consumer['finishedEvent'].set()

            for idx in xrange(nrConsumers):
                consumer = dict(talk=talktoserver.TalkToServer(config.AMQP_URL, "yuvu"),
                                receivedLabel=None,
                                finishedEvent=threading.Event())
                consumer["thread"] = threading.Thread(target=checkLabel, args=(consumer, idx))
                consumer["thread"].start()
                consumers.append(consumer)
            tested.provideLabel("yuvu", "onelabeltorulethemall")
            for idx, consumer in enumerate(consumers):
                consumer["finishedEvent"].wait()
            for idx, consumer in enumerate(consumers):
                self.assertEquals(consumer['receivedLabel'], "onelabeltorulethemall")
        finally:
            tested.close()

    def test_DifferentLabelsAreNotInterspersed(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            idsToLabels = dict(alpha="india",
                               bravo="india",
                               charlie="juliet",
                               delta="juliet",
                               echo="kilo",
                               foxtrot="kilo",
                               golf="lima",
                               hotel="lima")

            def checkLabel(consumer, id):
                self._logger.info('Waiting for label in consumer %(id)s', dict(id=id))
                consumer["receivedLabel"] = consumer['talk'].label()
                self._logger.info('Consumer %(id)s has received a label.', dict(id=id))
                consumer["finishedEvent"].set()

            consumers = dict()
            for id in idsToLabels:
                tested.listenOnID(id)
                consumer = dict(talk=talktoserver.TalkToServer(config.AMQP_URL, id),
                                receivedLabel=None,
                                finishedEvent=threading.Event())
                consumer["thread"] = threading.Thread(target=checkLabel, args=(consumer, id))
                consumer["thread"].start()
                consumers[id] = consumer
            for id, label in idsToLabels.iteritems():
                tested.provideLabel(id, label)
            for id, consumer in consumers.iteritems():
                consumer["finishedEvent"].wait()
                self.assertEquals(consumer['receivedLabel'], idsToLabels[id])
        finally:
            tested.close()

    def test_ProvideLabelToAnIdWhichIsNotListenedToDoesNotCrashServer(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.provideLabel("whatIsThisID", "someLabel")
            tested.listenOnID("yuvu")
            tested.provideLabel("whatIsThisID", "someLabel")
            self.validateCheckIn(tested, "yuvu")
            talk = talktoserver.TalkToServer(config.AMQP_URL, "yuvu")
            tested.provideLabel("whatIsThisID", "someLabel")
            self.validateCheckIn(tested, "yuvu")
            tested.provideLabel("yuvu", "theCoolestLabel")
            self.assertEqual(talk.label(), "theCoolestLabel")
            self.validateCheckIn(tested, "yuvu")
        finally:
            tested.close()

    def test_CannotReuseTalkToServerAfterDone(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("yuvu")
            talk = talktoserver.TalkToServer(config.AMQP_URL, "yuvu")
            tested.provideLabel("yuvu", "theCoolestLabel")
            self.assertEqual(talk.label(), "theCoolestLabel")
            talk.done()
            self.assertRaises(talktoserver.CannotReuseTalkToServerAfterDone, talk.label)
        finally:
            tested.close()

    def test_FailureDuringTalkToServerCleanUpDoesNotCauseCrash(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        origQueueDelete = pika.channel.Channel.queue_delete
        origConnectionClose = pika.adapters.blocking_connection.BlockingConnection.close
        try:
            tested.listenOnID("yuvu")
            pika.channel.Channel.queue_delete = mock.Mock(side_effect=Exception("ignore me"))
            talk = talktoserver.TalkToServer(config.AMQP_URL, "yuvu")
            tested.provideLabel("yuvu", "theCoolestLabel")
            self.assertEqual(talk.label(), "theCoolestLabel")
            pika.adapters.blocking_connection.BlockingConnection.close = \
                mock.Mock(side_effect=Exception("ignore me too"))
            talk = talktoserver.TalkToServer(config.AMQP_URL, "yuvu")
            tested.provideLabel("yuvu", "yetAnotherCoolLabel")
            self.assertEqual(talk.label(), "yetAnotherCoolLabel")
            talk.done()
            self.assertRaises(talktoserver.CannotReuseTalkToServerAfterDone, talk.label)
        finally:
            pika.channel.Channel.queue_delete = origQueueDelete
            pika.adapters.blocking_connection.BlockingConnection.close = origConnectionClose
            tested.close()

    def test_SendPurge(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("yuvu")
            self.validatePurge(tested, "yuvu")
            self.validateCheckIn(tested, "yuvu")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
        finally:
            tested.close()

    def test_SendCheckInAfterPurge(self):
        tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                               self.purgeCallback)
        try:
            tested.listenOnID("eliran")
            self.validatePurge(tested, "eliran")
            self.assertEquals(self.doneCallbackArguments, [])
            self.assertEquals(self.progressCallbackArguments, [])
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
                                  done=(self.sendDone, self.doneCallbackArguments),
                                  purge=(self.sendPurge, self.purgeCallbackArguments))
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

    def validatePurge(self, tested, id):
        self.validateStatusMessageArrival(tested, "purge", id)

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

    def purgeCallback(self, *args):
        self.purgeCallbackArguments.append(args)

    def sendCheckIn(self, id):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.checkIn()

    def sendProgress(self, id, message):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.progress(message)

    def sendDone(self, id):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.done()

    def sendPurge(self, id):
        talk = talktoserver.TalkToServer(config.AMQP_URL, id)
        talk.purge()

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

if __name__ == '__main__':
    _logger = logging.getLogger("inaugurator.server")
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
    unittest.main()
