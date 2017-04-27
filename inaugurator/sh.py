import subprocess


logFilepath = None


def run(* args, ** kwargs):
    commandRepr = " ".join(args)
    message = "\n\nExecuting Command: %s\n\n" % (commandRepr,)
    if logFilepath is None:
        print message
    cmdPipe = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, shell=True, ** kwargs)
    output, _ = cmdPipe.communicate()
    if logFilepath is not None:
        try:
            with open(logFilepath, "a+") as f:
                f.write(message)
                if output is not None:
                    f.write(output)
                    f.flush()
        except Exception as ex:
            print "Cannot write to log file: %s" % (str(ex.args),)
    if cmdPipe.returncode != 0:
        ex = subprocess.CalledProcessError(cmdPipe.returncode, commandRepr, output)
        print "Command '%s' failed: %d\n%s" % (args, cmdPipe.returncode, output)
        raise ex
    return output
