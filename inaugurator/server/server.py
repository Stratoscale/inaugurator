from inaugurator.server import config
import threading
import logging
import pika
import simplejson
import json
import os
import signal
import pikapatchwakeupfromanotherthread
import idlistener

_logger = logging.getLogger('inaugurator.server')


class Server(threading.Thread):
    def __init__(self, checkInCallback, doneCallback, progressCallback):
        self._checkInCallback = checkInCallback
        self._doneCallback = doneCallback
        self._progressCallback = progressCallback
        self._readyEvent = threading.Event()
        self._closed = False
        self._listeners = {}
        self._idsWithLabelExchanges = set()
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
        if id not in self._idsWithLabelExchanges:
            _logger.error("Tried to provide a label to ID %(id)s which is not listened to.", dict(id=id))
            return
        self._channel.basic_publish(exchange=self._labelExchange(id), routing_key='', body=label)

    def _listenOnID(self, id):
        if id in self._listeners:
            _logger.error("Tried to listen twice on the same host %(id)s.", dict(id=id))
            return
        self._listeners[id] = idlistener.IDListener(id, self._handleStatus, self._channel)

        labelExchange = self._labelExchange(id)

        def onLabelExchangeDeclared(unused):
            self._idsWithLabelExchanges.add(id)
            _logger.info("Label exchange '%(exchange)s' declared", dict(exchange=labelExchange))

        self._channel.exchange_declare(onLabelExchangeDeclared, type='fanout', exchange=labelExchange)

    def _stopListeningOnID(self, id):
        if id not in self._listeners:
            _logger.error("Tried to stop listening on a non existent %(id)s.", dict(id=id))
            return
        self._listeners[id].stopListening()
        del self._listeners[id]

    def _labelExchange(self, id):
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
