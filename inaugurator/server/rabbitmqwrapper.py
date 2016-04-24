import subprocess
import os
import pika
import time
import signal
import threading
import logging
import atexit
from inaugurator.server import processtree
from inaugurator.server import config


class RabbitMQWrapper(threading.Thread):
    def __init__(self, filesPath):
        self._filesPath = filesPath
        self._exited = False
        if not os.path.isdir(self._filesPath):
            os.makedirs(self._filesPath)
            os.chmod(self._filesPath, 0777)
        configFile = os.path.join(self._filesPath, "rabbitmq.config")
        with open(configFile, "w") as f:
            f.write(_RABBIT_MQ_CONFIG)
        with open(os.path.join(self._filesPath, "log.txt"), "a") as log:
            self._popen = subprocess.Popen(["/usr/lib/rabbitmq/bin/rabbitmq-server"], env=dict(
                os.environ,
                HOME=self._filesPath,
                RABBITMQ_CONFIG_FILE=configFile[:-len(".config")],
                RABBITMQ_MNESIA_BASE=os.path.join(self._filesPath, "rabbit", "mnesia"),
                RABBITMQ_LOG_BASE=os.path.join(self._filesPath, "rabbit", "logs"),
                RABBITMQ_NODE_PORT=str(config.PORT)),
                stdout=log, stderr=log)
        atexit.register(self.cleanup)
        logging.info("Waiting for 15 seconds for the RabbitMQ Server to start...")
        time.sleep(15)
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def run(self):
        self._popen.wait()
        if self._exited:
            return
        logging.error("RabbitMQ exited prematurely, committing suicide")
        os.kill(os.getpid(), signal.SIGTERM)

    def cleanup(self):
        self._exited = True
        processtree.devourChildrenOf(self._popen.pid)
        try:
            self._popen.terminate()
        except OSError as e:
            logging.warning("Unable to terminate rabbitMQ process on cleanup: %(exception)s", dict(
                exception=e))

    @classmethod
    def connect(cls):
        return pika.BlockingConnection(pika.ConnectionParameters(host='localhost', port=config.PORT))


_RABBIT_MQ_CONFIG = """%% -*- mode: erlang -*-
[
 {rabbit,
  [
   {loopback_users, []}
  ]},

 {kernel,
  [
  ]},

 {rabbitmq_management,
  [
  ]},

 {rabbitmq_management_agent,
  [
  ]},

 {rabbitmq_shovel,
  [{shovels,
    [
    ]}
  ]},

 {rabbitmq_stomp,
  [
  ]},

 {rabbitmq_mqtt,
  [
  ]},

 {rabbitmq_amqp1_0,
  [
  ]},

 {rabbitmq_auth_backend_ldap,
  [
  ]}
].
"""
