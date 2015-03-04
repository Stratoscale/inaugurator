import pika
import json
import logging


class TalkToServer:
    def __init__(self, amqpURL, myID):
        self._myID = myID
        self._statusExchange = "inaugurator_status__%s" % myID
        self._labelQueue = "inaugurator_label__%s" % myID
        parameters = pika.URLParameters(amqpURL)
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._channel.exchange_declare(exchange=self._statusExchange, type='fanout')
        self._channel.queue_declare(self._labelQueue)

    def checkIn(self):
        logging.info("talking to server: checkin")
        self._publishStatus(dict(status="checkin"))

    def progress(self, progress):
        self._publishStatus(dict(status="progress", progress=progress))

    def done(self):
        logging.info("talking to server: done")
        self._publishStatus(dict(status="done"))

    def label(self):
        self._channel.basic_consume(self._labelCallback, queue=self._labelQueue, no_ack=True)
        self._channel.start_consuming()
        return self._receivedLabel

    def _labelCallback(self, channel, method, properties, body):
        self._receivedLabel = body
        self._channel.stop_consuming()

    def _publishStatus(self, status):
        body = json.dumps(dict(status, id=self._myID))
        self._channel.basic_publish(exchange=self._statusExchange, routing_key='', body=body)
