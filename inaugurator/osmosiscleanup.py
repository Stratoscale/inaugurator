import os
from osmosis import objectstore
from osmosis.policy import cleanupremovelabelsuntildiskusage
from osmosis.policy import disk
from inaugurator import sh
import logging


class OsmosisCleanup:
    ALLOWED_DISK_USAGE_PERCENT = 50

    def __init__(self, mountPoint, usageUpperThreshold=ALLOWED_DISK_USAGE_PERCENT):
        self._usageUpperThreshold = usageUpperThreshold
        objectStorePath = os.path.join(mountPoint, "var", "lib", "osmosis", "objectstore")
        self._objectStore = objectstore.ObjectStore(objectStorePath)
        before = disk.dfPercent(mountPoint)
        if self._objectStoreExists():
            self._attemptObjectStoreCleanup()
        logging.info("Disk usage: before cleanup: %(before)s%%, after: %(after)s%%", dict(
            before=before, after=disk.dfPercent(mountPoint)))
        if disk.dfPercent(mountPoint) > self._usageUpperThreshold:
            logging.info("Erasing disk - osmosis cleanup did not help")
            self._eraseEverything(mountPoint)

    def _objectStoreExists(self):
        try:
            self._objectStore.labels()
            return True
        except OSError:
            return False

    def _attemptObjectStoreCleanup(self):
        try:
            cleanupremovelabelsuntildiskusage.CleanupRemoveLabelsUntilDiskUsage(
                self._objectStore, allowedDiskUsagePercent=self._usageUpperThreshold).go()
        except cleanupremovelabelsuntildiskusage.ObjectStoreEmptyException:
            pass

    def _eraseEverything(self, mountPoint):
        sh.run("busybox rm -fr %s/*" % mountPoint)
