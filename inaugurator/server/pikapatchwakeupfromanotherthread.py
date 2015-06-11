import os
import Queue
import select
import logging
import signal
import select
from inaugurator.server import newpika_select_connection
import pika

pika.SelectConnection = newpika_select_connection.SelectConnection

_logger = logging.getLogger('inaugurator.server')


class PikaPatchWakeUpFromAnotherThread:
    def __init__(self, connection):
        self._queue = Queue.Queue()
        self._readFd, self._writeFd = os.pipe()
        self._patch(connection)

    def runInThread(self, callback, **kwargs):
        self._queue.put((callback, kwargs), block=True)
        os.write(self._writeFd, '1')

    def _patch(self, connection):
        assert self._patchOnlyOnce(connection)
        self._checkRightPikaRightPoller(connection)
        connection.ioloop.add_handler(self._readFd, self._processCommands, connection.READ)

    def _patchOnlyOnce(self, connection):
        PATCHED_JUST_ONCE_FLAG = '_INAUGURATOR_PATCH_ONCE'
        assert not hasattr(connection, PATCHED_JUST_ONCE_FLAG)
        setattr(connection, PATCHED_JUST_ONCE_FLAG, True)
        return True

    def _checkRightPikaRightPoller(self, connection):
        try:
            poller = connection.ioloop._poller._poll
        except AttributeError:
            _logger.error(
                "While hot-patching pika: pika version seems to be different than the one this "
                "hot-patch was created for, cannot proceed. This patch was created for pika 0.9.14")
            self._suicide()
        # There's no way of refering the builtin select.poll type object besides the `type` function,
        # since select.poll is a built-in function, in addition to being a hard-coded type.
        if str(type(poller)) != 'select.poll' and not isinstance(poller, select.epoll):
            _logger.error(
                "The current pika poller does not use poll or epoll; its type is %(pollerType)s. "
                "cannot patch pika.", dict(pollerType=str(type(poller))))
            self._suicide()

    def _processCommands(self, *args, **unused):
        kwargs = None
        try:
            ready = select.select([self._readFd], [], [], 0)[0]
            if len(ready) > 0:
                os.read(self._readFd, 1)
        except:
            _logger.exception("Unable to read from wake up pipe, ignoring")
        try:
            callback, kwargs = self._queue.get(block=False)
        except Queue.Empty:
            _logger.warn("Command queue is empty after the pipe indicated that a command exists.")
            return
        try:
            callback(**kwargs)
        except:
            _logger.error('Error while processing command %(command)s arguments %(kwargs)s', dict(
                command=command, kwargs=kwargs))

    def _suicide(self):
        os.kill(os.getpid(), signal.SIGTERM)
        raise RuntimeError("Unable to hot-patch pika")
