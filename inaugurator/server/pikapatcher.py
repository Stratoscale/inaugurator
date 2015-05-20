import os
import Queue
import select
import logging

_logger = logging.getLogger('inaugurator.server')


class CommandPipePikaPatcher(object):
    PATCHED_JUST_ONCE_FLAG = 'isPatchedByUs'

    def __init__(self, connection, callback):
        self._callback = callback
        self._queue = Queue.Queue()
        self._patch(connection)

    def _patch(self, connection):
        assert not hasattr(connection, self.PATCHED_JUST_ONCE_FLAG)

        self._cmdPipeInFd, self._cmdPipeOutFd = os.pipe()
        _logger.info('Command signaling pipe created with fds: read: %(inFd)s, out: %(outFd)s' % dict(
                     inFd=self._cmdPipeInFd, outFd=self._cmdPipeOutFd))

        try:
            poller = connection.ioloop._poller._poll
        except AttributeError:
            raise RuntimeError("The code is not compatible with the currently installed pika package.")
        # There's no way of refering the builtin select.poll type object besides the `type` function,
        # since select.poll is a built-in function, in addition to being a hard-coded type.
        if not (str(type(poller)) == 'select.poll' or isinstance(poller, select.epoll)):
            msg = "The current pika poller does not use poll or epoll; its type is %(poller_type)s. " \
                "cannot patch pika." % dict(poller_type=str(type(poller)))
            raise RuntimeError(msg)

        connection.ioloop.add_handler(self._cmdPipeInFd, self._processCommands, connection.READ)
        setattr(connection, self.PATCHED_JUST_ONCE_FLAG, True)

    def _processCommands(self, *args, **kwargs):
        try:
            os.read(self._cmdPipeInFd, 1)
            command = self._queue.get(block=False)
            self._callback(command)
        except Queue.Empty:
            _logger.warn("Command queue is empty after the pipe indicated that a command exists.")
        except:
            _logger.error('Error while processing command %(command)s',
                          dict(command=command))
            raise

    def sendCommand(self, **kwargs):
        self._queue.put(kwargs, block=True)
        os.write(self._cmdPipeOutFd, '1')
