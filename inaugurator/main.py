from inaugurator import partitiontable
from inaugurator import targetdevice
import traceback
import pdb


def main():
    cmdLine = open("/proc/cmdline").read()
    targetDevice = targetdevice.TargetDevice.device()
    partitionTable = partitiontable.PartitionTable(targetDevice)
    if 'inugurator_clear_disk' in cmdLine:
        partitionTable.clear()
    partitionTable.verify()
    print "Partitions created"


try:
    main()
except Exception as e:
    print "Inaugurator raised exception: "
    traceback.print_exc(e)
finally:
    pdb.set_trace()
