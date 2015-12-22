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
        self._logger = logging.getLogger()
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
        self.doServerCallbackCauseErrors = False
        self.talkToServerInstances = set()
        self.tested = server.Server(self.checkInCallback, self.doneCallback, self.progressCallback,
                                    self.purgeCallback)

    def tearDown(self):
        for talkToServer in self.talkToServerInstances:
            try:
                talkToServer.done()
            except:
                pass
        self.tested.close()
        self.rabbitMQWrapper.cleanup()
        with open(os.path.join(self.tempdir, "log.txt")) as f:
            log = f.read()
        self._logger.info("RabbitMQ log:\n")
        self._logger.info(log)
        shutil.rmtree(self.tempdir, ignore_errors=True)
        time.sleep(1)

    def test_CheckIn(self):
        self.tested.listenOnID("eliran")
        self.validateCheckIn("eliran")
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.progressCallbackArguments, [])

    def test_StopListening(self):
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.invokeStopListeningAndWaitTillDone("yuvu")
        self.validateCheckInDoesNotWork("yuvu")
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.progressCallbackArguments, [])

    def test_StopListeningDoesNotAffectAnotherServer(self):
        self.tested.listenOnID("jakarta")
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.validateCheckIn("jakarta")
        self.invokeStopListeningAndWaitTillDone("yuvu")
        self.validateCheckIn("jakarta")
        self.validateCheckInDoesNotWork("yuvu")
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.validateCheckIn("jakarta")
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.progressCallbackArguments, [])

    def test_StopListeningOnAnIDWhichIsNotListenedTo(self):
        self.invokeStopListeningAndWaitTillDone("yuvu")
        self.validateCheckInDoesNotWork("yuvu")

    def test_ListenTwiceOnSameID(self):
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.invokeStopListeningAndWaitTillDone("yuvu")
        self.validateCheckInDoesNotWork("yuvu")

    def test_Progress(self):
        self.tested.listenOnID("eliran")
        self.validateProgress("eliran", "awesome-progress-message")
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.checkInCallbackArguments, [])

    def test_Done(self):
        self.tested.listenOnID("eliran")
        self.validateDone("eliran")
        self.assertEquals(self.progressCallbackArguments, [])
        self.assertEquals(self.checkInCallbackArguments, [])

    def test_ExceptionInCallbackDoesNotCrashServer(self):
        self.doServerCallbackCauseErrors = True
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        self.validateProgress("yuvu", "awesome-progress-message")
        self.validateDone("yuvu")
        self.assertTrue(self.tested.isAlive())

    def test_ProvideLabel(self):
        self.tested.listenOnID("yuvu")
        self.validateCheckIn("yuvu")
        talk = self.generateTalkToServer("yuvu")
        self.tested.provideLabel("yuvu", "thecoolestlabel")
        self.assertEqual(talk.label(), "thecoolestlabel")

    def test_AllConsumersOfLabelQueueGetTheLabel(self):
        self.tested.listenOnID("yuvu")
        nrConsumers = 10
        consumers = list()

        def checkLabel(consumer, idx):
            self._logger.info('Waiting for label in consumer %(idx)s', dict(idx=idx))
            consumer['receivedLabel'] = consumer['talk'].label()
            self._logger.info('Consumer %(idx)s has received a label.', dict(idx=idx))
            consumer['finishedEvent'].set()

        for idx in xrange(nrConsumers):
            consumer = dict(talk=self.generateTalkToServer("yuvu"),
                            receivedLabel=None,
                            finishedEvent=threading.Event())
            consumer["thread"] = threading.Thread(target=checkLabel, args=(consumer, idx))
            consumer["thread"].start()
            consumers.append(consumer)
        self.tested.provideLabel("yuvu", "onelabeltorulethemall")
        for idx, consumer in enumerate(consumers):
            consumer["finishedEvent"].wait()
        for idx, consumer in enumerate(consumers):
            self.assertEquals(consumer['receivedLabel'], "onelabeltorulethemall")

    def test_DifferentLabelsAreNotInterspersed(self):
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
            self.tested.listenOnID(id)
            consumer = dict(talk=self.generateTalkToServer(id),
                            receivedLabel=None,
                            finishedEvent=threading.Event())
            consumer["thread"] = threading.Thread(target=checkLabel, args=(consumer, id))
            consumer["thread"].start()
            consumers[id] = consumer
        for id, label in idsToLabels.iteritems():
            self.tested.provideLabel(id, label)
        for id, consumer in consumers.iteritems():
            consumer["finishedEvent"].wait()
            self.assertEquals(consumer['receivedLabel'], idsToLabels[id])

    def test_ProvideLabelToAnIdWhichIsNotListenedToDoesNotCrashServer(self):
        self.tested.provideLabel("whatIsThisID", "someLabel")
        self.tested.listenOnID("yuvu")
        self.tested.provideLabel("whatIsThisID", "someLabel")
        self.validateCheckIn("yuvu")
        talk = self.generateTalkToServer("yuvu")
        self.tested.provideLabel("whatIsThisID", "someLabel")
        self.validateCheckIn("yuvu")
        self.tested.provideLabel("yuvu", "theCoolestLabel")
        self.assertEqual(talk.label(), "theCoolestLabel")
        self.validateCheckIn("yuvu")

    def test_CannotReuseTalkToServerAfterDone(self):
        self.tested.listenOnID("yuvu")
        talk = self.generateTalkToServer("yuvu")
        self.tested.provideLabel("yuvu", "theCoolestLabel")
        self.assertEqual(talk.label(), "theCoolestLabel")
        talk.done()
        self.assertRaises(talktoserver.CannotReuseTalkToServerAfterDone, talk.label)

    def test_FailureDuringTalkToServerCleanUpDoesNotCauseCrash(self):
        origQueueDelete = pika.channel.Channel.queue_delete
        origConnectionClose = pika.adapters.blocking_connection.BlockingConnection.close
        try:
            self.tested.listenOnID("yuvu")
            pika.channel.Channel.queue_delete = mock.Mock(side_effect=Exception("ignore me"))
            talk = self.generateTalkToServer("yuvu")
            self.tested.provideLabel("yuvu", "theCoolestLabel")
            self.assertEqual(talk.label(), "theCoolestLabel")
            pika.adapters.blocking_connection.BlockingConnection.close = \
                mock.Mock(side_effect=Exception("ignore me too"))
            talk = self.generateTalkToServer("yuvu")
            self.tested.provideLabel("yuvu", "yetAnotherCoolLabel")
            self.assertEqual(talk.label(), "yetAnotherCoolLabel")
            talk.done()
            self.assertRaises(talktoserver.CannotReuseTalkToServerAfterDone, talk.label)
        finally:
            pika.channel.Channel.queue_delete = origQueueDelete
            pika.adapters.blocking_connection.BlockingConnection.close = origConnectionClose

    def test_SendPurge(self):
        self.tested.listenOnID("yuvu")
        self.validatePurge("yuvu")
        self.validateCheckIn("yuvu")
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.progressCallbackArguments, [])

    def test_SendCheckInAfterPurge(self):
        self.tested.listenOnID("eliran")
        self.validatePurge("eliran")
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.progressCallbackArguments, [])

    def sendOneStatusMessageAndCheckArrival(self, sendMethod, callbackArguments, id, extraArgs):
        if extraArgs is None:
            extraArgs = tuple()
        sendMethod(id, *extraArgs)
        hasMessageArrived = (id,) + extraArgs in callbackArguments
        return hasMessageArrived

    def validateStatusMessageArrival(self, statusMessageType, id, extraArgs=None,
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
            self.waitTillStatusQueueIsCleanByAbusingProgressCallbacks(id)
            while callbackArguments:
                callbackArguments.pop()
        else:
            self.assertEqualsDuringPeriod(validateMethod, False)

    def validateCheckInDoesNotWork(self, id):
        self.validateStatusMessageArrival("checkin", id, isArrivalExpected=False)

    def validateCheckIn(self, id):
        self.validateStatusMessageArrival("checkin", id)

    def validateProgress(self, id, message):
        self.validateStatusMessageArrival("progress", id, extraArgs=(message,))

    def validateDone(self, id):
        self.validateStatusMessageArrival("done", id)

    def validatePurge(self, id):
        self.validateStatusMessageArrival("purge", id)

    def waitTillStatusQueueIsCleanByAbusingProgressCallbacks(self, idWhichIsListenedTo):
        self.unreportedProgressMessageEvent = threading.Event()
        self.sendProgress(idWhichIsListenedTo, self.UNREPORTED_PROGRESS_MESSAGE)
        if not self.unreportedProgressMessageEvent.wait(timeout=1):
            raise AssertionError("Progress callback was not invoked at time")

    def waitTillAllCommandsWereExecutedByTheServer(self):
        auxID = "IDWhichIsUsedToValidateThatTheServerHasFinishedAllPendingCommands_%(counter)s" % \
            dict(counter=self.auxLabelIDCounter)
        self.auxLabelIDCounter += 1
        self.tested.listenOnID(auxID)
        self.validateStatusMessageArrival("checkin", auxID)

    def invokeStopListeningAndWaitTillDone(self, id):
        self.tested.stopListeningOnID(id)
        self.waitTillAllCommandsWereExecutedByTheServer()

    def checkInCallback(self, *args):
        self.checkInCallbackArguments.append(args)
        if self.doServerCallbackCauseErrors:
            raise Exception("Ignore me")

    def doneCallback(self, *args):
        self.doneCallbackArguments.append(args)
        if self.doServerCallbackCauseErrors:
            raise Exception("Ignore me")

    def progressCallback(self, *args):
        message = args[1]
        if message == self.UNREPORTED_PROGRESS_MESSAGE:
            self.unreportedProgressMessageEvent.set()
            return
        self.progressCallbackArguments.append(args)
        if self.doServerCallbackCauseErrors:
            raise Exception("Ignore me")

    def purgeCallback(self, *args):
        self.purgeCallbackArguments.append(args)
        if self.doServerCallbackCauseErrors:
            raise Exception("Ignore me")

    def sendCheckIn(self, id):
        talk = self.generateTalkToServer(id)
        talk.checkIn()

    def sendProgress(self, id, message):
        talk = self.generateTalkToServer(id)
        talk.progress(message)

    def sendDone(self, id):
        talk = self.generateTalkToServer(id)
        talk.done()

    def sendPurge(self, id):
        talk = self.generateTalkToServer(id)
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

    def generateTalkToServer(self, id):
        talkToServer = talktoserver.TalkToServer(config.AMQP_URL, id)
        self.talkToServerInstances.add(talkToServer)
        return talkToServer

if __name__ == '__main__':
    logLevels = {0: {"": logging.CRITICAL, "inaugurator.server": logging.CRITICAL, "pika": logging.ERROR},
                 1: {"": logging.CRITICAL, "inaugurator.server": logging.CRITICAL, "pika": logging.ERROR},
                 2: {"": logging.CRITICAL, "inaugurator.server": logging.CRITICAL, "pika": logging.ERROR},
                 3: {"": logging.ERROR, "inaugurator.server": logging.ERROR, "pika": logging.ERROR},
                 4: {"": logging.INFO, "inaugurator.server": logging.INFO, "pika": logging.ERROR},
                 5: {"": logging.DEBUG, "inaugurator.server": logging.DEBUG, "pika": logging.INFO},
                 6: {"": logging.DEBUG, "inaugurator.server": logging.DEBUG, "pika": logging.DEBUG}}
    maxVerbosity = max(logLevels.keys())
    print "Note: For different verbosity levels, run with VERBOSITY=(number from 1 to %(maxVerbosity)s)." \
          % dict(maxVerbosity=maxVerbosity)
    verbosity = int(os.getenv("VERBOSITY", 0))
    loggerNames = logLevels[0].keys()
    logLevels = logLevels[verbosity]
    for loggerName in loggerNames:
        logger = logging.getLogger(loggerName)
        logLevel = logLevels[loggerName]
        logger.setLevel(logLevel)
        for handler in logger.handlers:
            handler.setLevel(logLevel)
    # Increment verbosity so that test names will be presented on verbosity of 1
    unittest.main(verbosity=verbosity)
