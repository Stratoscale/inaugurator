import subprocess


lastFailureOutput = None


def run(* args, ** kwargs):
    try:
        return subprocess.check_output(
            * args, stderr=subprocess.STDOUT, close_fds=True, shell=True, ** kwargs)
    except subprocess.CalledProcessError as e:
        print "Command '%s' failed: %d\n%s" % (args, e.returncode, e.output)
        global lastFailureOutput
        lastFailureOutput = e.output
        raise
