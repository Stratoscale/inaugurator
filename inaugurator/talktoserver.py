import pika
import json
import Queue
import logging
import threading


class TalkToServerSpooler(threading.Thread):
    def __init__(self, amqpURL, statusExchange, labelExchange):
        super(TalkToServerSpooler, self).__init__()
        self.daemon = True
        self._statusExchange = statusExchange
        self._labelExchange = labelExchange
        self._labelQueue = None
        self._queue = Queue.Queue()
        self._connect(amqpURL)
        threading.Thread.start(self)

    def publishStatus(self, **status):
        self._executeCommandInConnectionThread(self._publishStatus, **status)

    def getLabel(self):
        return self._executeCommandInConnectionThread(self._getLabel)

    def run(self):
        logging.info("Inaugurator TalkToServer Spooler is waiting for commands...")
        while True:
            try:
                finishedEvent, command, kwargs, returnValue = self._queue.get(block=True, timeout=10)
            except Queue.Empty:
                self._connection.process_data_events()
                continue
            try:
                returnValue.data = command(**kwargs)
                self._connection.process_data_events()
            except Exception as e:
                returnValue.exception = e
            finally:
                finishedEvent.set()

    def _connect(self, amqpURL):
        logging.info("Inaugurator Publish Spooler connects to rabbit MQ %(url)s...", dict(url=amqpURL))
        parameters = pika.URLParameters(amqpURL)
        self._connection = pika.BlockingConnection(parameters)
        logging.info("Creating a pika channel...")
        self._channel = self._connection.channel()
        logging.info("Declaring a RabbitMQ exchange %(exchange)s...", dict(exchange=self._statusExchange))
        self._channel.exchange_declare(exchange=self._statusExchange, type='fanout')
        logging.info("Declaring a RabbitMQ exchange %(exchange)s...", dict(exchange=self._labelExchange))
        self._channel.exchange_declare(exchange=self._labelExchange, type='fanout')
        logging.info("Declaring an exclusive RabbitMQ label queue...")
        frame = self._channel.queue_declare(exclusive=True)
        self._labelQueue = frame.method.queue
        logging.info("Binding label queue %(queue)s with labels exchange...", dict(queue=self._labelQueue))
        self._channel.queue_bind(queue=self._labelQueue, exchange=self._labelExchange)
        logging.info("Inaugurator Publish Spooler is connected to the RabbitMQ broker.")

    def _publishStatus(self, **status):
        body = json.dumps(status)
        self._channel.basic_publish(exchange=self._statusExchange, routing_key='', body=body)

    def _labelCallback(self, channel, method, properties, body):
        self._receivedLabel = body
        self._channel.stop_consuming()

    def _getLabel(self, **kwargs):
        self._channel.basic_consume(self._labelCallback, queue=self._labelQueue, no_ack=True)
        self._channel.start_consuming()
        return self._receivedLabel

    def _executeCommandInConnectionThread(self, function, **kwargs):
        class ReturnValue(object):
            def __init__(self):
                self.data = None
                self.exception = None

        finishedEvent = threading.Event()
        returnValue = ReturnValue()
        self._queue.put((finishedEvent, function, kwargs, returnValue), block=True)
        finishedEvent.wait()
        if returnValue.exception is not None:
            raise returnValue.exception
        return returnValue.data


class TalkToServer:
    def __init__(self, amqpURL, myID):
        statusExchange = "inaugurator_status__%s" % myID
        labelExchange = "inaugurator_label__%s" % myID
        self._myID = myID
        self._spooler = TalkToServerSpooler(amqpURL, statusExchange, labelExchange)

    def checkIn(self):
        logging.info("talking to server: checkin")
        self._spooler.publishStatus(status="checkin", id=self._myID)

    def progress(self, progress):
        self._spooler.publishStatus(status="progress", progress=progress, id=self._myID)

    def done(self):
        logging.info("talking to server: done")
        self._spooler.publishStatus(status="done", id=self._myID)

    def label(self):
        return self._spooler.getLabel()
