import os
from osmosis import objectstore
from osmosis.policy import cleanupremovelabelsuntildiskusage
from osmosis.policy import disk
from inaugurator import sh


class OsmosisCleanup:
    ALLOWED_DISK_USAGE_PERCENT = 50

    def __init__(self, mountPoint):
        objectStorePath = os.path.join(mountPoint, "var", "lib", "osmosis", "objectstore")
        self._objectStore = objectstore.ObjectStore(objectStorePath)
        if self._objectStoreExists():
            self._attemptObjectStoreCleanup()
        if disk.dfPercent(mountPoint) > self.ALLOWED_DISK_USAGE_PERCENT:
            self._eraseEverything()

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

    def _eraseEverything(self):
        sh.run("rm -fr %s/*" % self._mountPoint)
