from inaugurator.server import config
import threading
import logging
import pika
import time
import json


class Server(threading.Thread):
    _RECONNECT_INTERVAL = 1

    def __init__(self, checkInCallback, doneCallback, progressCallback, listeningIDs):
        self._checkInCallback = checkInCallback
        self._doneCallback = doneCallback
        self._progressCallback = progressCallback
        self._listeningIDs = listeningIDs
        self._connect()
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def provideLabel(self, id, label):
        assert id in self._listeningIDs
        self._channel.queue_purge(queue=self._labelQueue(id))
        self._channel.basic_publish(exchange='', routing_key=self._labelQueue(id), body=label)

    def _setUpID(self, id):
        self._channel.queue_declare(self._labelQueue(id))
        self._channel.exchange_declare(exchange=self._statusExchange(id), type='fanout')
        myQueue = self._channel.queue_declare(exclusive=True).method.queue
        self._channel.queue_bind(exchange=self._statusExchange(id), queue=myQueue)
        self._channel.basic_consume(self._handleStatus, queue=myQueue, no_ack=True)

    def _statusExchange(self, id):
        return "inaugurator_status__%s" % id

    def _labelQueue(self, id):
        return "inaugurator_label__%s" % id

    def _connect(self):
        logging.info("Inaugurator server connects to rabbit MQ %(url)s", dict(url=config.AMQP_URL))
        parameters = pika.URLParameters(config.AMQP_URL)
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()

    def run(self):
        first = True
        while True:
            if first:
                first = False
            else:
                try:
                    self._connect()
                except:
                    logging.exception("Unable to reconnect")
                    time.sleep(self._RECONNECT_INTERVAL)
                    continue
            try:
                for id in self._listeningIDs:
                    self._setUpID(id)
                self._channel.start_consuming()
            except:
                logging.exception("While handling messages")
            finally:
                try:
                    self._channel.stop_consuming()
                except:
                    logging.exception("Unable to stop consuming, ignoring")
            time.sleep(self._RECONNECT_INTERVAL)

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
            raise
