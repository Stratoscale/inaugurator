from inaugurator import partitiontable
from inaugurator import targetdevice
from inaugurator import mount
from inaugurator import sh
from inaugurator import network
from inaugurator import loadkernel
from inaugurator import fstab
from inaugurator import passwd
from inaugurator import osmosis
from inaugurator import checkinwithserver
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
        osmos = osmosis.Osmosis(destination, hostname=args.inauguratorOsmosisHostname)
        checkIn = checkinwithserver.CheckInWithServer(hostname=args.inauguratorServerHostname)
        osmos.tellLabel(checkIn.label())
        osmos.wait()
        print "Osmosis complete"
        with mountOp.mountBoot() as bootDestination:
            sh.run("rsync -rlpgDS %s/boot/ %s/" % (destination, bootDestination))
        print "Boot sync complete"
        fstab.createFSTab(
            rootPath=destination, root=mountOp.rootPartition(), boot=mountOp.bootPartition())
        print "/etc/fstab created"
        if args.inauguratorChangeRootPassword:
            passwd.setRootPassword(destination, args.inauguratorChangeRootPassword)
            print "Changed root password"
        loadKernel = loadkernel.LoadKernel()
        loadKernel.fromBootPartitionGrubConfig(
            bootPath=os.path.join(destination, "boot"), rootPartition=mountOp.rootPartition())
        print "kernel loaded"
    after = time.time()
    print "Inaugurator took: %.2fs. KEXECing" % (after - before)
    loadKernel.execute()


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--inauguratorClearDisk")
parser.add_argument("--inauguratorServerHostname", required=True)
parser.add_argument("--inauguratorOsmosisHostname", required=True)
parser.add_argument("--inauguratorUseNICWithMAC", required=True)
parser.add_argument("--inauguratorIPAddress", required=True)
parser.add_argument("--inauguratorNetmask", required=True)
parser.add_argument("--inauguratorChangeRootPassword")

try:
    cmdLine = open("/proc/cmdline").read()
    args = parser.parse_known_args(cmdLine.split(' '))[0]
    main(args)
except Exception as e:
    print "Inaugurator raised exception: "
    traceback.print_exc(e)
finally:
    pdb.set_trace()
