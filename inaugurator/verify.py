import hashlib
import os
import logging
import pprint
import time
import re
import threading


class Verify:
    def __init__(self, mountPoint, label, talkToServer, objectStore):
        self._mountPoint = mountPoint
        self._hashes = self._readLabel(label)
        self._talkToServer = talkToServer
        self._objectStore = objectStore

    @classmethod
    def dropCaches(cls):
        with open('/proc/sys/vm/drop_caches', "w") as f:
            f.write("3\n")

    def go(self):
        logging.info("Starting Verification")
        queue = list(self._hashes.iteritems())
        dontMatch = []
        lastReport = 0
        threads = []
        for i in xrange(self._numberOfCPUs()):
            threads.append(_VerifyThread(queue, dontMatch, self._mountPoint))
        while len(queue) > 0:
            time.sleep(0.1)
            for thread in threads:
                if thread.exception is not None:
                    raise Exception("A digestion thread died of an exception, verification failed")
            if time.time() > lastReport + 10:
                self._report(len(self._hashes) - len(queue), len(self._hashes))
                lastReport = time.time()
        for thread in threads:
            if thread.exception is not None:
                raise Exception("A digestion thread died of an exception, verification failed")
        self._report(len(self._hashes), len(self._hashes))
        if len(dontMatch) > 0:
            logging.error("VERIFICATION OF DEPLOYED ROOTFS LABEL FAILED")
            logging.error("%s", pprint.pformat(dontMatch))
            raise Exception("Verification of deployed rootfs label failed")
        logging.info("Verification completed successfully")

    def _readLabel(self, label):
        with open(os.path.join(self._objectStore, "labels", label)) as f:
            labelHash = f.read().strip()
        labelFile = os.path.join(objectStore, labelHash[:2], labelHash[2:4], labelHash[4:])
        return self._parseLabelFile(labelFile)

    def _parseLabelFile(self, filename):
        BLACKLIST = set(['/etc/lvm/cache/.cache', '/etc/shadow'])
        result = {}
        with open(filename) as f:
            for line in f.readlines():
                parts = line.strip().split("\t")
                if parts[2] == "nohash":
                    continue
                path = '/' + parts[0].strip('"')
                if path in BLACKLIST:
                    continue
                result[path] = parts[2]
        return result

    def _report(self, done, total):
        percent = 100 * done / total
        progress = dict(state='verifying', percent=percent, done=done, total=total)
        logging.info("Verification progress: %s", (progress, ))
        if self._talkToServer is not None:
            self._talkToServer.progress(progress)

    def _numberOfCPUs(self):
        with open("/proc/cpuinfo") as f:
            content = f.read()
        result = len(re.findall(r"\nvendor_id\s", content))
        assert result > 0
        return result


class _VerifyThread(threading.Thread):
    def __init__(self, queue, dontMatch, mountPoint):
        self._queue = queue
        self._dontMatch = dontMatch
        self._mountPoint = mountPoint
        self.exception = None
        threading.Thread.__init__(self)
        self.daemon = True
        threading.Thread.start(self)

    def run(self):
        try:
            while True:
                try:
                    path, digest = self._queue.pop()
                except:
                    return
                result = self._verify(path, digest)
                if result is not None:
                    self._dontMatch.append(result)
        except Exception as e:
            self.exception = e
            logging.exception("Verification thread died of exception")

    def _verify(self, path, digest):
        absolute = os.path.join(self._mountPoint, path.lstrip("/"))
        if not os.path.isfile(absolute):
            return path, "notfound"
        with open(absolute, "rb") as f:
            content = f.read()
        computed = hashlib.md5(content).hexdigest()
        if computed != digest:
            return path, "digest"
        return None
