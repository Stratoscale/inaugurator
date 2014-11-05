from inaugurator import pyudev
from inaugurator import sh
import os
import fnmatch


def loadAllDrivers():
    context = pyudev.Context()
    aliasTable = _loadAliasTable()
    for device in context.list_devices():
        if u'MODALIAS' not in device:
            continue
        print "Found Device", device
        for k, v in device.iteritems():
            print "\t%s: %s" % (k, v)
        driver = _findDriver(device, aliasTable)
        if driver is None:
            print "No driver, skipping"
        else:
            print "Driver: %s, modprobing" % driver
            sh.run("busybox modprobe %s" % device[u'MODALIAS'])


def _kernelVersion():
    return sh.run("busybox uname -r").strip()


def _loadAliasTable():
    path = os.path.join("/lib/modules/%s/modules.alias" % _kernelVersion())
    table = dict()
    with open(path) as f:
        for line in f.readlines():
            if line.startswith("#"):
                continue
            alias, driver = line.strip().split(" ")[1:]
            table[alias] = driver
    return table


def _findDriver(device, aliasTable):
    alias = device[u'MODALIAS']
    for pattern in aliasTable:
        if fnmatch.fnmatch(alias, pattern):
            return aliasTable[pattern]
    return None


if __name__ == "__main__":
    loadAllDrivers()
