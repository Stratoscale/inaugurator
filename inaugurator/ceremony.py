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
from inaugurator import verify
import os
import time
import logging


class Ceremony:
    def __init__(self, args):
        """
        args is a 'namespace' - an object, or maybe a bunch. The following members are required:
        inauguratorClearDisk - True will cause the disk to be erase even if partition layout is ok
        inauguratorSource - 'network', 'DOK' (Disk On Key), 'local' - select from where the label
                            should be osmosed. 'local' means the label is already in the local object
                            store, and is used in upgrades.
        inauguratorServerAMQPURL - the rabbitmq AMQP url to report status to. Can be 'None'. If used,
                                   the label itself is expected to come from a rabbitmq message.
        inauguratorMyIDForServer - the unique ID for this station, used for status reporting.
        inauguratorNetworkLabel - the label to use, in 'network' mode, if inauguratorServerAMQPURL was
                                  not specified
        inauguratorOsmosisObjectStores - the object store chain used when invoking osmosis (see osmosis
                                         documentation
        inauguratorUseNICWithMAC - use this specific NIC, with this specific MAC address
        inauguratorIPAddress - the IP address to configure to that NIC
        inauguratorNetmask
        inauguratorGateway
        inauguratorChangeRootPassword - change the password in /etc/shadow to this
        inauguratorWithLocalObjectStore - use /var/lib/osmosis local object store as first tier in chain.
        inauguratorPassthrough - pass parameters to the kexeced kernel. Reminder: kexeced kernel are
                                 more vunerable to crashing, using this as the only channel of communication
                                 is risky
        inauguratorDownload - http get this file into a specific location, right before kexecing.
        inauguratorIgnoreDirs - ignore the following locations on disk, in the osmosis process. This is
                                usedful for upgrades - to keep the current configuration somewhere.
        inauguratorTargetDeviceCandidate - a list of devices (['/dev/vda', '/dev/sda']) to use as the
                                           inauguration target
        """
        self._args = args
        self._talkToServer = None
        self._assertArgsSane()

    def ceremony(self):
        before = time.time()
        self._makeSureDiskIsMountable()
        with self._mountOp.mountRoot() as destination:
            self._etcLabelFile = etclabelfile.EtcLabelFile(destination)
            self._doOsmosisFromSource(destination)
            logging.info("Osmosis complete")
            self._createBootAndInstallGrub(destination)
            logging.info("Boot sync complete")
            self._configureETC(destination)
            self._loadKernelForKexecing(destination)
            logging.info("kernel loaded")
            self._additionalDownload(destination)
        self._sync()
        if self._args.inauguratorVerify:
            self._verify()
            self._sync()
        after = time.time()
        if self._talkToServer is not None:
            self._talkToServer.done()
        logging.info("Inaugurator took: %(interval).2fs. KEXECing", dict(interval=after - before))
        self._loadKernel.execute()

    def _assertArgsSane(self):
        logging.info("Command line arguments: %(args)s", dict(args=self._args))
        if self._args.inauguratorSource == "network":
            assert (
                (self._args.inauguratorServerAMQPURL or self._args.inauguratorNetworkLabel) and
                self._args.inauguratorOsmosisObjectStores and
                self._args.inauguratorUseNICWithMAC and self._args.inauguratorIPAddress and
                self._args.inauguratorNetmask and self._args.inauguratorGateway), \
                "If inauguratorSource is 'network', all network command line paramaters must be specified"
            if self._args.inauguratorServerAMQPURL:
                assert self._args.inauguratorMyIDForServer, \
                    'If communicating with server, must specifiy --inauguratorMyIDForServer'
        elif self._args.inauguratorSource == "DOK":
            pass
        elif self._args.inauguratorSource == "local":
            pass
        else:
            assert False, "Unknown source for inaugurator: %s" % self._args.inauguratorSource

    def _createPartitionTable(self):
        lvmetad.Lvmetad()
        partitionTable = partitiontable.PartitionTable(self._targetDevice)
        if self._args.inauguratorClearDisk:
            partitionTable.clear()
        partitionTable.verify()

    def _configureETC(self, destination):
        self._etcLabelFile.write(self._label)
        fstab.createFSTab(
            rootPath=destination, root=self._mountOp.rootPartition(),
            boot=self._mountOp.bootPartition(), swap=self._mountOp.swapPartition())
        logging.info("/etc/fstab created")
        if self._args.inauguratorChangeRootPassword:
            passwd.setRootPassword(destination, self._args.inauguratorChangeRootPassword)
            logging.info("Changed root password")

    def _createBootAndInstallGrub(self, destination):
        with self._mountOp.mountBoot() as bootDestination:
            sh.run("rsync -rlpgDS --delete-before %s/boot/ %s/" % (destination, bootDestination))
        with self._mountOp.mountBootInsideRoot():
            logging.info("Installing grub")
            grub.install(self._targetDevice, destination)

    def _osmosFromNetwork(self, destination):
        network.Network(
            macAddress=self._args.inauguratorUseNICWithMAC, ipAddress=self._args.inauguratorIPAddress,
            netmask=self._args.inauguratorNetmask, gateway=self._args.inauguratorGateway)
        if self._args.inauguratorServerAMQPURL:
            self._talkToServer = talktoserver.TalkToServer(
                amqpURL=self._args.inauguratorServerAMQPURL, myID=self._args.inauguratorMyIDForServer)
            self._talkToServer.checkIn()
        osmos = osmose.Osmose(
            destination=destination,
            objectStores=self._args.inauguratorOsmosisObjectStores,
            withLocalObjectStore=self._args.inauguratorWithLocalObjectStore,
            ignoreDirs=self._args.inauguratorIgnoreDirs,
            talkToServer=self._talkToServer)
        if self._args.inauguratorServerAMQPURL:
            self._label = self._talkToServer.label()
        else:
            self._label = self._args.inauguratorNetworkLabel
        osmos.tellLabel(self._label)
        osmos.wait()

    def _osmosFromDOK(self, destination):
        dok = diskonkey.DiskOnKey()
        with dok.mount() as source:
            osmos = osmose.Osmose(
                destination, objectStores=source + "/osmosisobjectstore",
                withLocalObjectStore=self._args.inauguratorWithLocalObjectStore,
                ignoreDirs=self._args.inauguratorIgnoreDirs,
                talkToServer=self._talkToServer)
            with open("%s/inaugurate_label.txt" % source) as f:
                self._label = f.read().strip()
            osmos.tellLabel(self._label)  # This must stay under the dok mount 'with' statement
            osmos.wait()

    def _osmosFromLocalObjectStore(self, destination):
        osmos = osmose.Osmose(
            destination, objectStores=None,
            withLocalObjectStore=self._args.inauguratorWithLocalObjectStore,
            ignoreDirs=self._args.inauguratorIgnoreDirs,
            talkToServer=self._talkToServer)
        self._label = self._args.inauguratorNetworkLabel
        osmos.tellLabel(self._label)
        osmos.wait()

    def _sync(self):
        logging.info("sync...")
        sh.run(["busybox", "sync"])
        logging.info("sync done")

    def _additionalDownload(self, destination):
        if self._args.inauguratorDownload:
            downloadInstance = download.Download(self._args.inauguratorDownload)
            downloadInstance.download(destination)

    def _makeSureDiskIsMountable(self):
        udev.loadAllDrivers()
        self._targetDevice = targetdevice.TargetDevice.device(self._args.inauguratorTargetDeviceCandidate)
        self._createPartitionTable()
        logging.info("Partitions created")
        self._mountOp = mount.Mount(self._targetDevice)

    def _loadKernelForKexecing(self, destination):
        self._loadKernel = loadkernel.LoadKernel()
        self._loadKernel.fromBootPartitionGrubConfig(
            bootPath=os.path.join(destination, "boot"), rootPartition=self._mountOp.rootPartition(),
            append=self._args.inauguratorPassthrough)

    def _doOsmosisFromSource(self, destination):
        osmosiscleanup.OsmosisCleanup(destination)
        if self._args.inauguratorSource == 'network':
            self._osmosFromNetwork(destination)
        elif self._args.inauguratorSource == 'DOK':
            self._osmosFromDOK(destination)
        elif self._args.inauguratorSource == 'local':
            self._osmosFromLocalObjectStore(destination)
        else:
            assert False, "Unknown source %s" % self._args.inauguratorSource

    def _verify(self):
        verify.Verify.dropCaches()
        with self._mountOp.mountRoot() as destination:
            verify.Verify(destination, self._label, self._talkToServer).go()
