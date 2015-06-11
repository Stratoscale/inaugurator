import unittest
import shutil
import tempfile
import time
from inaugurator.server import server
from inaugurator.server import rabbitmqwrapper
from inaugurator.server import config
from inaugurator import talktoserver
config.PORT = 2018
config.AMQP_URL = "amqp://guest:guest@localhost:%d/%%2F" % config.PORT


class Test(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.rabbitMQWrapper = rabbitmqwrapper.RabbitMQWrapper(self.tempdir)
        self.checkInCallbackArguments = []
        self.doneCallbackArguments = []
        self.progressCallbackArguments = []

    def tearDown(self):
        self.rabbitMQWrapper.cleanup()
        shutil.rmtree(self.tempdir, ignore_errors=True)

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
        tested.listenOnID("eliran")
        self.sendCheckIn("eliran")
        self.assertEqualsWithinTimeout((lambda: self.checkInCallbackArguments), [("eliran",)])
        self.assertEquals(self.doneCallbackArguments, [])
        self.assertEquals(self.progressCallbackArguments, [])


if __name__ == '__main__':
    unittest.main()
