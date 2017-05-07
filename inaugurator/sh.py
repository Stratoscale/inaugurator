import subprocess
import logging


def run(* args, ** kwargs):
    commandRepr = " ".join(args)
    message = "\n\nExecuting Command: %s\n\n" % (commandRepr,)
    logging.info(message)
    cmdPipe = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, shell=True, ** kwargs)
    output, _ = cmdPipe.communicate()
    logging.info("Command's output:\n%s" % output)
    if cmdPipe.returncode != 0:
        ex = subprocess.CalledProcessError(cmdPipe.returncode, commandRepr, output)
        logging.error("Command '%s' failed: %d\n%s" % (args, cmdPipe.returncode, output))
        raise ex
    return output
