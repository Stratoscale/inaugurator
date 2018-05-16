import os
from osmosis import objectstore
from osmosis.policy import cleanupremovelabelsuntildiskusage
from osmosis.policy import disk
from inaugurator import sh
import logging


class OsmosisCleanup:
    ALLOWED_DISK_USAGE_PERCENT = 80

    def __init__(self, mountPoint, objectStorePath):
        self._objectStore = objectstore.ObjectStore(objectStorePath)
        before = disk.dfPercent(objectStorePath)
        if self._objectStoreExists():
            self._attemptObjectStoreCleanup()
        logging.info("Disk usage: before cleanup: %(before)s%%, after: %(after)s%%", dict(
            before=before, after=disk.dfPercent(objectStorePath)))
        if disk.dfPercent(objectStorePath) > self.ALLOWED_DISK_USAGE_PERCENT:
            logging.info("Erasing disk - osmosis cleanup did not help")
            self.eraseEverything()

    def _objectStoreExists(self):
        try:
            self._objectStore.labels()
            return True
        except OSError:
            return False

    def _attemptObjectStoreCleanup(self):
        try:
            cleanupremovelabelsuntildiskusage.CleanupRemoveLabelsUntilDiskUsage(
                self._objectStore, allowedDiskUsagePercent=self.ALLOWED_DISK_USAGE_PERCENT).go()
        except cleanupremovelabelsuntildiskusage.ObjectStoreEmptyException:
            pass

    def eraseEverything(self):
        try:
            sh.run("busybox rm -fr %s/*" % self._objectStore.root())
        except Exception as e:
            try:
                sh.run("busybox rm -fr %s/*" % self._objectStore.root())  # because - http://lists.busybox.net/pipermail/busybox/2015-August/083233.html
            except:
                pass
            raise e

