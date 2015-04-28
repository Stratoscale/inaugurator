import pika
PORT = pika.ConnectionParameters.DEFAULT_PORT
AMQP_URL = "amqp://guest:guest@localhost:%d/%%2F" % PORT
