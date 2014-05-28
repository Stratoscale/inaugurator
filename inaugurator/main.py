from inaugurator import partitiontable
from inaugurator import targetdevice
from inaugurator import mount
from inaugurator import sh
from inaugurator import network
import argparse
import traceback
import pdb
import os
import time


def main(args):
    before = time.time()
    targetDevice = targetdevice.TargetDevice.device()
    partitionTable = partitiontable.PartitionTable(targetDevice)
    if args.inauguratorClearDisk:
        partitionTable.clear()
    partitionTable.verify()
    print "Partitions created"
    mountOp = mount.Mount(targetDevice)
    with mountOp.mountRoot() as destination:
        network.Network(
            macAddress=args.inauguratorUseNICWithMAC, ipAddress=args.inauguratorIPAddress,
            netmask=args.inauguratorNetmask)
        result = os.system(
            "/usr/bin/osmosis checkout %s %s --MD5 --removeUnknownFiles --serverHostname=%s" % (
                destination, args.inauguratorOsmosisLabel, args.inauguratorOsmosisHostname))
        if result != 0:
            raise Exception("Osmosis failed")
        print "Osmosis complete"
        with mountOp.mountBoot() as bootDestination:
            sh.run("rsync -rlpgDS %s/boot/ %s/" % (destination, bootDestination))
        print "Boot sync complete"
    after = time.time()
    print "Inaugurator took: %.2fs" % (after - before)


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--inauguratorClearDisk")
parser.add_argument("--inauguratorOsmosisHostname", required=True)
parser.add_argument("--inauguratorOsmosisLabel", required=True)
parser.add_argument("--inauguratorUseNICWithMAC", required=True)
parser.add_argument("--inauguratorIPAddress", required=True)
parser.add_argument("--inauguratorNetmask", required=True)

try:
    cmdLine = open("/proc/cmdline").read()
    args = parser.parse_known_args(cmdLine.split(' '))[0]
    main(args)
except Exception as e:
    print "Inaugurator raised exception: "
    traceback.print_exc(e)
finally:
    pdb.set_trace()
