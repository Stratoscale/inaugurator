import os
import stat
import time
from inaugurator import sh


class TargetDevice:
    _found = None

    @classmethod
    def device(cls, candidates):
        if cls._found is None:
            cls._found = cls._find(candidates)
        return cls._found
        pass

    @classmethod
    def _find(cls, candidates):
        RETRIES = 5
        for retry in xrange(RETRIES):
            for device in candidates:
                if not os.path.exists(device):
                    print "Device does not exists"
                    continue
                if not stat.S_ISBLK(os.stat(device).st_mode):
                    print "something something"
                    continue
                try:
                    output = sh.run("dosfslabel", device + 1)
                    if output.strip() == "STRATODOK":
                        raise Exception(
                            "DOK was found on SDA. cannot continue: its likely the "
                            "the HD driver was not loaded correctly")
                except:
                    pass
                print "Found target device %s" % device
                return device
            print "didn't find target device, sleeping before retry %d" % retry
            time.sleep(1)
            os.system("/usr/sbin/busybox mdev -s")
        raise Exception("Failed finding target device")
