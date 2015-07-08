import logging

_logger = logging.getLogger('inaugurator.server')


def statusExchange(id):
    return "inaugurator_status__%s" % id


class IDListener:
    def __init__(self, id, callback, channel):
        self._channel = channel
        self._id = id
        self._statusQueue = None
        self._callback = callback
        self._notListeningAnymore = False
        self._channel.exchange_declare(
            self._onExchangeDeclared, exchange=statusExchange(self._id), type='fanout')

    def stopListening(self):
        if self._notListeningAnymore:
            _logger.error("Tried to stop listening on an id %(id)s which is not listened to",
                          dict(id=self._id))
            return
        self._notListeningAnymore = True
        self._callback = None
        self._freeQueue()

    def _onExchangeDeclared(self, unusedFrame):
        if self._notListeningAnymore:
            return
        self._channel.queue_declare(self._onQueueDeclared, exclusive=True)

    def _onQueueBind(self, myQueue):
        if self._notListeningAnymore or self._statusQueue is None:
            return
        self._channel.basic_consume(self._sendDataToCallback, queue=self._statusQueue, no_ack=True)

    def _sendDataToCallback(self, *data):
        if self._notListeningAnymore:
            return
        try:
            assert self._callback is not None
            self._callback(*data)
        except:
            logging.exception("While handling data from status queue for id %(id)s", dict(id=self._id))

    def _onQueueDeclared(self, methodFrame):
        self._statusQueue = methodFrame.method.queue
        if self._notListeningAnymore:
            self._freeQueue()
            return
        self._channel.queue_bind(self._onQueueBind, exchange=statusExchange(self._id),
                                 queue=self._statusQueue)

    def _freeQueue(self):
        if self._statusQueue is None:
            return
        self._channel.queue_delete(None, queue=self._statusQueue)
