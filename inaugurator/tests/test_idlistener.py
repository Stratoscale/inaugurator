import os
import sys
import mock
import logging
import unittest
from inaugurator.server import idlistener
from inaugurator.tests.common import PikaChannelMock


class Test(unittest.TestCase):
    def setUp(self):
        self.consumeCallback = mock.Mock()
        self.channel = PikaChannelMock(self)
        self.expectedStatusExchange = idlistener.statusExchange("delta-foxtrot")
        self.tested = idlistener.IDListener("delta-foxtrot", self.consumeCallback, self.channel)

    def test_Listen(self):
        self.validateListenHappyFlow()

    def test_StopListening(self):
        queue = self.validateListenHappyFlow()
        self.tested.stopListening()
        self.validateOneStatusQueueIsAllocated(queue, allowOtherRequests=True)
        self.channel.answerQueueDelete(queue)
        self.validateNoStatusQueueIsAllocated()
        self.validateMessages(self.basicConsumeCallback, isArrivalExpected=False)

    def test_StopListeningBeforeExchangeDeclared(self):
        self.validateNoStatusQueueIsAllocated()
        self.tested.stopListening()
        self.validateNoStatusQueueIsAllocated()
        self.channel.answerExchangeDeclare(self.expectedStatusExchange)
        self.validateNoStatusQueueIsAllocated()

    def test_StopListeningBeforeQueueDeclared(self):
        self.validateListenFlowUntilStatusQueueDeclare()
        self.validateOneStatusQueueIsAllocating()
        self.tested.stopListening()
        self.validateOneStatusQueueIsAllocating()
        queue = self.channel.answerQueueDeclare()
        self.validateOneStatusQueueIsAllocated(queue, allowOtherRequests=True)
        self.channel.answerQueueDelete(queue)
        self.validateNoStatusQueueIsAllocated()

    def test_StopListeningBeforeQueueBinded(self):
        self.validateListenFlowUntilStatusQueueDeclare()
        queue = self.channel.answerQueueDeclare()
        self.validateOneStatusQueueIsAllocated(queue)
        self.tested.stopListening()
        self.validateOneStatusQueueIsAllocated(queue, allowOtherRequests=True)
        queueBindCallback = self.channel.getQueueBindCallback()
        queueBindCallback(queue)
        self.validateOneStatusQueueIsAllocated(queue, allowOtherRequests=True)
        self.channel.answerQueueDelete(queue)
        self.validateNoStatusQueueIsAllocated(allowOtherRequests=True)

    def test_StopListeningTwice(self):
        queue = self.validateListenHappyFlow()
        self.tested.stopListening()
        self.channel.answerQueueDelete(queue)
        self.validateNoStatusQueueIsAllocated()
        self.tested.stopListening()
        self.validateNoStatusQueueIsAllocated()

    def test_MoreThanOneInstance(self):
        for i in xrange(10):
            queue = self.validateListenHappyFlow()
            self.tested.stopListening()
            self.channel.answerQueueDelete(queue)
            self.validateNoStatusQueueIsAllocated()
            self.tested = idlistener.IDListener("delta-foxtrot", self.consumeCallback, self.channel)
        self.validateNoStatusQueueIsAllocated()

    def validateListenFlowUntilStatusQueueDeclare(self):
        self.validateNoStatusQueueIsAllocated()
        self.channel.answerExchangeDeclare(self.expectedStatusExchange)
        self.validateOneStatusQueueIsAllocating()

    def validateListenFlowAfterQueueDeclare(self, queue):
        queueBindCallback = self.channel.getQueueBindCallback()
        queueBindCallback(queue)
        self.basicConsumeCallback = self.channel.getBasicConsumeCallback()
        self.validateMessages(self.basicConsumeCallback)
        self.validateOneStatusQueueIsAllocated(queue)

    def validateListenHappyFlow(self):
        self.validateListenFlowUntilStatusQueueDeclare()
        queue = self.channel.answerQueueDeclare()
        self.validateListenFlowAfterQueueDeclare(queue)
        self.validateOneStatusQueueIsAllocated(queue)
        return queue

    def validateMessages(self, basicConsumeCallback, isArrivalExpected=True):
        message = 'I am a cool message.'
        basicConsumeCallback(message)
        self.assertEquals(self.consumeCallback.called, isArrivalExpected)
        self.consumeCallback.reset_mock()

    def validateOneStatusQueueIsAllocated(self, queue, allowOtherRequests=False):
        self.assertEquals(set([queue]), self.channel.declaredQueues)
        if not allowOtherRequests:
            self.assertFalse(self.channel.requests)

    def validateOneStatusQueueIsAllocating(self, allowDeleteRequests=False):
        self.assertEquals(len(self.channel.requests), 1)
        self.assertEquals(self.channel.requests[0][0], "declare")
        if not allowDeleteRequests:
            self.assertFalse(self.channel.declaredQueues)

    def validateNoStatusQueueIsAllocated(self, allowOtherRequests=False):
        self.assertFalse(self.channel.declaredQueues)
        if not allowOtherRequests:
            self.assertFalse(self.channel.requests)
            self.assertFalse(self.channel.queue_bind.called)
            self.assertFalse(self.channel.basic_consume.called)


if __name__ == '__main__':
    _logger = logging.getLogger("inaugurator.server")
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
    unittest.main()
