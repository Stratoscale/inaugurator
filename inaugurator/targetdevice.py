import os
import stat
import time


class TargetDevice:
    _found = None

    @classmethod
    def device(cls):
        if cls._found is None:
            cls._found = cls._find()
        return cls._found
        pass

    @classmethod
    def _find(cls):
        CANDIDATES = ['/dev/vda', '/dev/sda']
        RETRIES = 5
        for retry in xrange(RETRIES):
            for device in CANDIDATES:
                if os.path.exists(device) and stat.S_ISBLK(os.stat(device).st_mode):
                    print "Found target device %s" % device
                    return device
            print "didn't find target device, sleeping before retry %d" % retry
            time.sleep(1)
            os.system("/usr/sbin/busybox mdev -s")
        raise Exception("Failed finding target device")
