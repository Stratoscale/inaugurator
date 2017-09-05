import mock


class MethodFrameMock:
    class Method(object):
        def __init__(self, **kwargs):
            for key, value in kwargs.iteritems():
                setattr(self, key, value)

    def __init__(self, **kwargs):
        self.method = self.Method(**kwargs)


class PikaChannelMock:
    MOCK_SUPPORTS_NAMED_QUEUE = False

    def __init__(self, test):
        self.declaredQueues = set()
        self.declaredQueuesCallbacks = dict()
        self.queue_bind = mock.Mock()
        self.exchange_declare = mock.Mock()
        self.basic_consume = mock.Mock()
        self.requests = list()
        self.test = test
        self.tempQueueCounter = 0

    def queue_declare(self, callback, **kwargs):
        self.test.assertNotIn("queue", kwargs)
        if not self.MOCK_SUPPORTS_NAMED_QUEUE:
            assert "queue" not in kwargs
        self.requests.append(("declare", callback))

    def queue_delete(self, callback, queue):
        self.test.assertIn(queue, self.declaredQueues)
        self.requests.append(("delete", queue, callback))

    def getBasicConsumeCallback(self):
        return self._getCallback(self.basic_consume)

    def getQueueBindCallback(self):
        return self._getCallback(self.queue_bind)

    def answerQueueDeclare(self):
        self._handleOneQueueDeclarationRequest()
        queue = next(iter(self.declaredQueues))
        queueDeclaredCallback = self.declaredQueuesCallbacks[queue]
        queueDeclaredCallback(MethodFrameMock(queue=queue))
        return queue

    def answerQueueDelete(self, expectedDeletedQueue):
        deletedQueue, queueDeletedCallback = self._handleOneQueueDeletionRequest()
        self.test.assertEquals(deletedQueue, expectedDeletedQueue)
        if queueDeletedCallback is not None:
            queueDeletedCallback()

    def answerExchangeDeclare(self, expectedStatusExchange):

        def Any(cls):
            class Any(cls):
                def __eq__(self, other):
                    return True
            return Any()

        self.exchange_declare.assert_called_with(Any(int), exchange=expectedStatusExchange, exchange_type='fanout')
        statusExchangeDeclaredCallback = self._getCallback(self.exchange_declare)
        statusExchangeDeclaredCallback(MethodFrameMock())

    def _popFromRequestsQueue(self, expectedRequestType):
        request = self.requests.pop(0)
        self.test.assertEquals(request[0], expectedRequestType)
        return request[1:]

    def _handleOneQueueDeclarationRequest(self):
        (queueDeclaredCallback,) = self._popFromRequestsQueue(expectedRequestType="declare")
        queue = 'some-status-queue_%(tempQueueCounter)s' % (dict(tempQueueCounter=self.tempQueueCounter))
        assert queue not in self.declaredQueues
        self.tempQueueCounter += 1
        self.test.assertNotIn(queue, self.declaredQueuesCallbacks)
        self.declaredQueues.add(queue)
        self.declaredQueuesCallbacks[queue] = queueDeclaredCallback

    def _handleOneQueueDeletionRequest(self):
        queue, callback = self._popFromRequestsQueue(expectedRequestType="delete")
        self.declaredQueues.remove(queue)
        return queue, callback

    def _getCallback(self, mockObj):
        self.test.assertTrue(mockObj.called)
        callback = mockObj.call_args[0][0]
        self.test.assertIsNotNone(callback)
        mockObj.reset_mock()
        return callback
