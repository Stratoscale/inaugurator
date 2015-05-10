from inaugurator.server import config
import threading
import logging
import pika
import simplejson
import json
import os
import signal
import Queue

_logger = logging.getLogger('inaugurator.server')


class Server(threading.Thread):
    def __init__(self, checkInCallback, doneCallback, progressCallback):
        self._checkInCallback = checkInCallback
        self._doneCallback = doneCallback
        self._progressCallback = progressCallback
        self._readyEvent = threading.Event()
        self._closed = False
        self._queue = Queue.Queue()
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)
        _logger.info('Waiting for RabbitMQ connection to be open...')
        self._readyEvent.wait()
        _logger.info('Inaugurator server is ready.')

    def provideLabel(self, id, label):
        self._queue.put(dict(cmd='provideLabel', id=id, label=label))

    def listenOnID(self, id):
        self._queue.put(dict(cmd='listenRequest', id=id))

    def _provideLabel(self, id, label):

        def onPurged(*args):
            self._channel.basic_publish(exchange='', routing_key=self._labelQueue(id), body=label)

        self._channel.queue_purge(onPurged, queue=self._labelQueue(id))

    def _listenToServer(self, id):
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

    @classmethod
    def statusExchange(cls, id):
        return "inaugurator_status__%s" % id

    def _labelQueue(self, id):
        return "inaugurator_label__%s" % id

    def run(self):
        _logger.info('Connecting to %(amqpURL)s', dict(amqpURL=config.AMQP_URL))
        self._connection = pika.SelectConnection(
            pika.URLParameters(config.AMQP_URL),
            self._onConnectionOpen,
            stop_ioloop_on_close=False)
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
        self._connection.add_timeout(1, self._process_commands)
        self._readyEvent.set()

    def _onChannelClosed(self, channel, reply_code, reply_text):
        _logger.error('Channel %(channel)i was closed: (%(replyCode)s) %(replyText)s', dict(
            channel=channel, replyCode=reply_code, replyText=reply_text))
        self._connection.close()

    def _handleCommand(self, command):
        _logger.info('Handling command: %(command)s', dict(command=command))
        id = command[u'id']
        cmd = command[u'cmd']
        if cmd == "listenRequest":
            self._listenToServer(id)
        elif cmd == "provideLabel":
            self._provideLabel(id, command['label'])
        else:
            raise Exception('Unknown command: %(body)', dict(body=command))

    def _handleStatus(self, channel, method, properties, body):
        try:
            message = json.loads(body)
        except:
            logging.exception("While parsing JSON message '%(body)s'", dict(body=body))
            raise
        try:
            id = message[u'id']
            status = message[u'status']
            if status == "checkin":
                self._checkInCallback(id)
            elif status == "done":
                self._doneCallback(id)
            elif status == "progress":
                self._progressCallback(id, message[u'progress'])
            else:
                raise Exception("Unknown status report: %s" % message)
        except:
            logging.exception("While handling message '%(body)s'", dict(body=body))
            raise

    def _process_commands(self):
        try:
            while True:
                command = self._queue.get(block=False)
                self._handleCommand(command)
        except Queue.Empty:
            pass
        except:
            _logger.error('Error while processing command %(command)s',
                          dict(command=command))
            raise
        finally:
            self._connection.add_timeout(1, self._process_commands)
