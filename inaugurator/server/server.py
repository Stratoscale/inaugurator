from inaugurator.server import config
import threading
import logging
import pika
import simplejson
import json
import os
import signal
import pikapatchwakeupfromanotherthread

_logger = logging.getLogger('inaugurator.server')


class Server(threading.Thread):
    def __init__(self, checkInCallback, doneCallback, progressCallback):
        self._checkInCallback = checkInCallback
        self._doneCallback = doneCallback
        self._progressCallback = progressCallback
        self._readyEvent = threading.Event()
        self._closed = False
        threading.Thread.__init__(self)
        self.daemon = True
        self._wakeUpFromAnotherThread = None
        threading.Thread.start(self)
        _logger.info('Inaugurator server waiting for RabbitMQ connection to be open...')
        self._readyEvent.wait()
        _logger.info('Inaugurator server is ready.')

    def provideLabel(self, id, label):
        self._wakeUpFromAnotherThread.runInThread(self._provideLabel, id=id, label=label)

    def listenOnID(self, id):
        self._wakeUpFromAnotherThread.runInThread(self._listenOnID, id=id)

    def stopListeningOnID(self, id):
        self._wakeUpFromAnotherThread.runInThread(self._stopListeningOnID, id=id)

    def _provideLabel(self, id, label):

        def onPurged(*args):
            self._channel.basic_publish(exchange='', routing_key=self._labelQueue(id), body=label)

        self._channel.queue_purge(onPurged, queue=self._labelQueue(id))

    def _listenOnID(self, id):
        self._channel.queue_declare(lambda *a: None, queue=self._labelQueue(id))

        def onQueueBind(myQueue):
            self._channel.basic_consume(self._handleStatus, queue=myQueue, no_ack=True)

        def onQueueDeclared(methodFrame):
            myQueue = methodFrame.method.queue
            self._channel.queue_bind(
                lambda *a: onQueueBind(myQueue), exchange=self.statusExchange(id), queue=myQueue)

        def onExchangeDecalred(*args):
            self._channel.queue_declare(onQueueDeclared, exclusive=True)

        self._channel.exchange_declare(onExchangeDecalred, exchange=self.statusExchange(id), type='fanout')

    def _stopListeningOnID(self, id):
        self._channel.exchange_delete(exchange=self.statusExchange(id))

    @classmethod
    def statusExchange(cls, id):
        return "inaugurator_status__%s" % id

    def _labelQueue(self, id):
        return "inaugurator_label__%s" % id

    def close(self):
        self._closed = True
        self._connection.close()

    def run(self):
        _logger.info('Connecting to %(amqpURL)s', dict(amqpURL=config.AMQP_URL))
        self._connection = pika.SelectConnection(
            pika.URLParameters(config.AMQP_URL),
            self._onConnectionOpen,
            stop_ioloop_on_close=False)
        self._wakeUpFromAnotherThread = pikapatchwakeupfromanotherthread.PikaPatchWakeUpFromAnotherThread(
            self._connection)
        self._connection.ioloop.start()

    def _onConnectionOpen(self, unused_connection):
        _logger.info('Connection opened')
        self._connection.add_on_close_callback(self._onConnectionClosed)
        self._connection.channel(on_open_callback=self._onChannelOpen)

    def _onConnectionClosed(self, connection, reply_code, reply_text):
        self._channel = None
        if self._closed:
            self._connection.ioloop.stop()
        else:
            _logger.error("Connection closed, committing suicide: %(replyCode)s %(replyText)s", dict(
                replyCode=reply_code, replyText=reply_text))
            os.kill(os.getpid(), signal.SIGTERM)

    def _onChannelOpen(self, channel):
        self._channel = channel
        self._channel.add_on_close_callback(self._onChannelClosed)
        self._readyEvent.set()

    def _onChannelClosed(self, channel, reply_code, reply_text):
        _logger.error('Channel %(channel)i was closed: (%(replyCode)s) %(replyText)s', dict(
            channel=channel, replyCode=reply_code, replyText=reply_text))
        self._connection.close()

    def _handleStatus(self, channel, method, properties, body):
        try:
            message = json.loads(body)
            id = message[u'id']
            if message[u'status'] == "checkin":
                self._checkInCallback(id)
            elif message[u'status'] == "done":
                self._doneCallback(id)
            elif message[u'status'] == "progress":
                self._progressCallback(id, message[u'progress'])
            else:
                raise Exception("Unknown status report: %s" % message)
        except:
            logging.exception("While handling message '%(body)s'", dict(body=body))
