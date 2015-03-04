from inaugurator import partitiontable
from inaugurator import targetdevice
from inaugurator import mount
from inaugurator import sh
from inaugurator import network
from inaugurator import loadkernel
from inaugurator import fstab
from inaugurator import passwd
from inaugurator import osmose
from inaugurator import osmosiscleanup
from inaugurator import talktoserver
from inaugurator import grub
from inaugurator import diskonkey
from inaugurator import udev
from inaugurator import download
from inaugurator import etclabelfile
from inaugurator import lvmetad
import argparse
import traceback
import pdb
import os
import time
import logging
import sys


logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logging.getLogger('pika').setLevel(logging.INFO)


def main(args):
    before = time.time()
    udev.loadAllDrivers()
    targetDevice = targetdevice.TargetDevice.device()
    lvmetad.Lvmetad()
    partitionTable = partitiontable.PartitionTable(targetDevice)
    if args.inauguratorClearDisk:
        partitionTable.clear()
    partitionTable.verify()
    logging.info("Partitions created")
    mountOp = mount.Mount(targetDevice)
    talkToServer = None
    with mountOp.mountRoot() as destination:
        etcLabelFile = etclabelfile.EtcLabelFile(destination)
        osmosiscleanup.OsmosisCleanup(destination)
        if args.inauguratorSource == 'network':
            network.Network(
                macAddress=args.inauguratorUseNICWithMAC, ipAddress=args.inauguratorIPAddress,
                netmask=args.inauguratorNetmask, gateway=args.inauguratorGateway)
            if args.inauguratorServerAMQPURL:
                talkToServer = talktoserver.TalkToServer(
                    amqpURL=args.inauguratorServerAMQPURL, myID=args.inauguratorMyIDForServer)
                talkToServer.checkIn()
            osmos = osmose.Osmose(
                destination=destination,
                objectStores=args.inauguratorOsmosisObjectStores,
                withLocalObjectStore=args.inauguratorWithLocalObjectStore,
                ignoreDirs=args.inauguratorIgnoreDirs,
                talkToServer=talkToServer)
            if args.inauguratorServerAMQPURL:
                label = talkToServer.label()
            else:
                label = args.inauguratorNetworkLabel
            osmos.tellLabel(label)
            osmos.wait()
        elif args.inauguratorSource == 'DOK':
            dok = diskonkey.DiskOnKey()
            with dok.mount() as source:
                osmos = osmose.Osmose(
                    destination, objectStores=source + "/osmosisobjectstore",
                    withLocalObjectStore=args.inauguratorWithLocalObjectStore,
                    ignoreDirs=args.inauguratorIgnoreDirs,
                    talkToServer=talkToServer)
                with open("%s/inaugurate_label.txt" % source) as f:
                    label = f.read().strip()
                osmos.tellLabel(label)  # This must stay under the dok mount 'with' statement
                osmos.wait()
        elif args.inauguratorSource == 'local':
            osmos = osmose.Osmose(
                destination, objectStores=None,
                withLocalObjectStore=args.inauguratorWithLocalObjectStore,
                ignoreDirs=args.inauguratorIgnoreDirs)
            label = args.inauguratorNetworkLabel
            osmos.tellLabel(label)
            osmos.wait()
        else:
            assert False, "Unknown source %s" % args.inauguratorSource
        print "Osmosis complete"
        etcLabelFile.write(label)
        with mountOp.mountBoot() as bootDestination:
            sh.run("rsync -rlpgDS --delete-before %s/boot/ %s/" % (destination, bootDestination))
        with mountOp.mountBootInsideRoot():
            print "Installing grub"
            grub.install(targetDevice, destination)
        print "Boot sync complete"
        fstab.createFSTab(
            rootPath=destination, root=mountOp.rootPartition(),
            boot=mountOp.bootPartition(), swap=mountOp.swapPartition())
        print "/etc/fstab created"
        if args.inauguratorChangeRootPassword:
            passwd.setRootPassword(destination, args.inauguratorChangeRootPassword)
            print "Changed root password"
        loadKernel = loadkernel.LoadKernel()
        loadKernel.fromBootPartitionGrubConfig(
            bootPath=os.path.join(destination, "boot"), rootPartition=mountOp.rootPartition(),
            append=args.inauguratorPassthrough)
        print "kernel loaded"
        if args.inauguratorDownload:
            downloadInstance = download.Download(args.inauguratorDownload)
            downloadInstance.download(destination)
    print "sync..."
    sh.run(["busybox", "sync"])
    print "sync done"
    after = time.time()
    if talkToServer is not None:
        talkToServer.done()
    print "Inaugurator took: %.2fs. KEXECing" % (after - before)
    loadKernel.execute()


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--inauguratorClearDisk", action="store_true")
parser.add_argument("--inauguratorSource", required=True)
parser.add_argument("--inauguratorServerAMQPURL")
parser.add_argument("--inauguratorMyIDForServer")
parser.add_argument("--inauguratorNetworkLabel")
parser.add_argument("--inauguratorOsmosisObjectStores")
parser.add_argument("--inauguratorUseNICWithMAC")
parser.add_argument("--inauguratorIPAddress")
parser.add_argument("--inauguratorNetmask")
parser.add_argument("--inauguratorGateway")
parser.add_argument("--inauguratorChangeRootPassword")
parser.add_argument("--inauguratorWithLocalObjectStore", action="store_true")
parser.add_argument("--inauguratorPassthrough", default="")
parser.add_argument("--inauguratorDownload", nargs='+', default=[])
parser.add_argument("--inauguratorIgnoreDirs", nargs='+', default=[])

try:
    cmdLine = open("/proc/cmdline").read().strip()
    args = parser.parse_known_args(cmdLine.split(' '))[0]
    print "Command line arguments:", args
    if args.inauguratorSource == "network":
        assert (
            (args.inauguratorServerAMQPURL or args.inauguratorNetworkLabel) and
            args.inauguratorOsmosisObjectStores and
            args.inauguratorUseNICWithMAC and args.inauguratorIPAddress and
            args.inauguratorNetmask and args.inauguratorGateway), \
            "If inauguratorSource is 'network', all network command line paramaters must be specified"
        if args.inauguratorServerAMQPURL:
            assert args.inauguratorMyIDForServer, \
                'If communicating with server, must specifiy --inauguratorMyIDForServer'
    elif args.inauguratorSource == "DOK":
        pass
    elif args.inauguratorSource == "local":
        pass
    else:
        assert False, "Unknown source for inaugurator: %s" % args.inauguratorSource
    main(args)
except Exception as e:
    print "Inaugurator raised exception: "
    traceback.print_exc(e)
finally:
    pdb.set_trace()
