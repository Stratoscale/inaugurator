import os
import time
import logging
import subprocess
import errno


def run(command, cwd=None):
    try:
        return subprocess.check_output(
            command, cwd=cwd, stderr=subprocess.STDOUT,
            stdin=open("/dev/null"), close_fds=True)
    except subprocess.CalledProcessError as e:
        logging.error("Failed command '%s' in '%s' output:\n%s" % (command, cwd, e.output))
        raise


def parentMap():
    result = {}
    for filename in os.listdir("/proc"):
        try:
            pid = int(filename)
        except:
            continue
        try:
            with open(os.path.join("/proc", filename, 'stat')) as f:
                parentPid = int(f.read().split(' ')[3])
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
        result[pid] = parentPid
    return result


def childrenMap():
    result = {}
    for pid, parent in parentMap().iteritems():
        result.setdefault(parent, []).append(pid)
    return result


def children(pid):
    map = childrenMap()
    children = set(map.get(pid, []))
    before = 0
    while before != len(children):
        before = len(children)
        for child in list(children):
            children |= set(map.get(child, []))
    return children


def pidLive(pid):
    if not os.path.exists(os.path.join("/proc", str(pid))):
        return False
    with open(os.path.join("/proc", str(pid), "status")) as f:
        return 'State:\tZ' not in f.read()


def devourMyChildren():
    devourChildrenOf(os.getpid())


def devourChildrenOf(pid):
    pids = children(pid)
    INTERVAL = 0.2
    NORMAL_KILLS = 15
    BRUTE_KILLS = 3
    for i in xrange(NORMAL_KILLS):
        if len(pids) > 0:
            if i > 0:
                logging.warning("Children tree not dead, killing SIGTERM these processes: %(procs)s", dict(
                    procs=pids))
            for pid in pids:
                try:
                    run(['kill', '-TERM', str(pid)])
                except:
                    pass
            time.sleep(INTERVAL)
            pids = [p for p in pids if pidLive(p)]
    for i in xrange(BRUTE_KILLS):
        if len(pids) > 0:
            logging.warning("Children tree not dead, killing SIGKILL these processes: %(procs)s", dict(
                procs=pids))
            for pid in pids:
                try:
                    run(['kill', '-KILL', str(pid)])
                except:
                    pass
            time.sleep(INTERVAL)
            pids = [p for p in pids if pidLive(p)]
    if pids:
        logging.warning("Children left behind: %(procs)s", dict(procs=pids))


if __name__ == "__main__":
    import sys
    print children(int(sys.argv[1]))
