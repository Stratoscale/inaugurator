from inaugurator import pyudev
from inaugurator import sh
import os
import fnmatch


_ALSO = {
    'mlx4_core': ['mlx4_en']
}


def loadAllDrivers():
    context = pyudev.Context()
    aliasTable = _loadAliasTable()
    deviceList = list(context.list_devices())
    for device in deviceList:
        if u'MODALIAS' not in device:
            continue
        for k, v in device.iteritems():
            print "\t%s: %s" % (k, v)
        driver = _findDriver(device, aliasTable)
        if driver is None:
            print "No driver, skipping"
        else:
            _loadDriver(driver)


def _loadDriver(driver):
    "This is for upwards dependency, not modprobe like dependency"
    print "Driver: %s, modprobing" % driver
    sh.run("busybox modprobe %s" % driver)
    if driver in _ALSO:
        print "Additional drivers must be loaded for '%s': %s" % (driver, _ALSO[driver])
        for also in _ALSO[driver]:
            _loadDriver(also)


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
            if ':' not in alias:
                continue
            subsystem = alias.split(":")[0]
            if subsystem not in table:
                table[subsystem] = dict()
                print alias
            table[subsystem][alias] = driver
    return table


def _lookLike(alias, pattern):
    parts = pattern.split("*")
    for part in parts:
        if part not in alias:
            return False
    return True


def _findDriver(device, aliasTable):
    alias = device[u'MODALIAS']
    subsystem = alias.split(":")[0]
    for pattern in aliasTable.get(subsystem, dict()):
        if _lookLike(alias, pattern):
            if fnmatch.fnmatch(alias, pattern):
                return aliasTable[subsystem][pattern]
    return None


if __name__ == "__main__":
    global _kernelVersion
    ver = _kernelVersion()
    _kernelVersion = lambda: ver

    def fakeSH(command):
        print "COMMAND", command
    sh.run = fakeSH
    loadAllDrivers()
