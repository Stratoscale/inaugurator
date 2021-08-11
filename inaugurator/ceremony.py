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
from inaugurator import cdrom
from inaugurator import udev
from inaugurator import download
from inaugurator import etclabelfile
from inaugurator import lvmetad
from inaugurator import verify
from inaugurator import debugthread
from inaugurator import hwinfo as selfTest
from inaugurator import dirsize
import os
import re
import time
import logging
import threading
import json
import requests
import signal

DIR_THRESHOLD = 0.7


class OsmosisTimeoutException(Exception):
    pass


class Ceremony:

    def __init__(self, args):
        """
        args is a 'namespace' - an object, or maybe a bunch. The following members are required:
        inauguratorArgumentsSource - Indicates where the Inaugurator should read arguments from, apart from
                                     this argument; Either 'kernelCmdline' to read from kernel arguments or
                                     'processArguments' to read from the process arguments. Should this
                                     argument appear, it must appear as a process argument. The rest of the
                                     arguments should appear correspondingly to the value mentioned in this
                                     argument).
        inauguratorClearDisk - True will cause the disk to be erase even if partition layout is ok
        inauguratorSource - 'network', 'DOK' (Disk On Key), 'CDROM' or 'local' - select from where the label
                            should be osmosed. 'local' means the label is already in the local object
                            store, and is used in upgrades.
        inauguratorServerAMQPURL - the rabbitmq AMQP url to report status to. Can be 'None'. If used,
                                   the label itself is expected to come from a rabbitmq message.
        inauguratorMyIDForServer - the unique ID for this station, used for status reporting.
        inauguratorNetworkLabel - the label to use, in 'network' mode, if inauguratorServerAMQPURL was
                                  not specified
        inauguratorOsmosisObjectStores - the object store chain used when invoking osmosis (see osmosis
                                         documentation
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
        inauguratorLogfilePath - Path of log file to keep track of shell commands that are run during
                                 inauguration.
        inauguratorStages - A comma-seperated list of stages to perform by order. Available stages:
                            'ceremony','kexec','reboot'.
        inauguratorExpectedLabel - A label that identifies the source device, when using either a CDROM or
                                   a Diskonkey (in --inauguratorSource). If not used, then the first device
                                   of that kind that was found will be used.
        inauguratorIsNetworkAlreadyConfigured - If not given, and if inauguratorSource is 'network', then
                                                the network interface will be configured according
                                                to the following 4 arguments (that in which case, are
                                                manadtory).
        inauguratorUseNICWithMAC - use this specific NIC, with this specific MAC address
        inauguratorIPAddress - the IP address to configure to that NIC
        inauguratorNetmask
        inauguratorGateway
        inauguratorSelfTestServerUrl - the url (ip+port) for self test server example: 192.168.70.66:50007
        hypervisor - most of disk size will be under inaugurator--v%d-root
        """
        self._args = args
        self._talkToServer = None
        self._assertArgsSane()
        self._debugPort = None
        self._isExpectingReboot = False
        self._grubConfig = None
        self._localObjectStore = None
        sh.logFilepath = self._args.inauguratorLogfilePath
        self._before = time.time()
        self._bootPartitionPath = None

    def ceremony(self):
        self._makeSureDiskIsMountable()
        if self._args.inauguratorDisableNCQ:
            self._disableNCQ()
        else:
            print 'Skipping the disabling of NCQ.'
        with self._mountOp.mountRoot() as destination, self._mountOp.mountOsmosisCache() as osmosisCache:
            self._localObjectStore = osmosisCache
            self._etcLabelFile = etclabelfile.EtcLabelFile(destination)
            self._doOsmosisFromSource(destination)
            logging.info("Osmosis complete")
            self._createBootAndInstallGrub(destination)
            logging.info("Boot sync complete")
            self._configureETC(destination)
            self._loadKernelForKexecing(destination)
            logging.info("kernel loaded")
            self._additionalDownload(destination)

    def kexec(self):
        self._sync()
        self._verify()
        after = time.time()
        if self._talkToServer is not None:
            self._talkToServer.done()
        if self._before is not None:
            logging.info("Inaugurator took: %(interval).2fs.", dict(interval=after - self._before))
        logging.info("KEXECing...")
        self._loadKernel.execute()

    def reboot(self):
        self._sync()
        self._verify()
        sh.run("reboot -f")

    def _assertArgsSane(self):
        logging.info("Command line arguments: %(args)s", dict(args=self._args))
        msg = "Unknown source for inaugurator: %s" % self._args.inauguratorSource
        assert self._args.inauguratorSource in ["network", "DOK", "local", "CDROM"], msg
        if self._args.inauguratorSource != "network":
            return
        if self._args.inauguratorServerAMQPURL is None and self._args.inauguratorNetworkLabel is None:
            msg = "If inauguratorSource is 'network', either inauguratorServerAMQPURL or " \
                  "inauguratorNetworkLabel must be specified."
            raise Exception(msg)
        if self._args.inauguratorOsmosisObjectStores is None:
            msg = "If inauguratorSource is 'network', the inauguratorOsmosisObjectStores argument must be " \
                  " specified."
            raise Exception(msg)
        if self._args.inauguratorIsNetworkAlreadyConfigured is None:
            mandatory = ["inauguratorUseNICWithMAC",
                         "inauguratorIPAddress",
                         "inauguratorNetmask",
                         "inauguratorGateway"]
            unspecified = [arg for arg in mandatory if getattr(self._args, arg) is None]
            if unspecified:
                msg = "If inauguratorIsNetworkAlreadyConfigured is not given, the following network " \
                      " command line arguments must be specified: %(mandatory)s. The following were not: " \
                      "%(unspecified)s" % \
                      dict(mandatory=", ".join(mandatory), unspecified=", ".join(unspecified))
                raise Exception(msg)
        if self._args.inauguratorServerAMQPURL is not None:
            assert self._args.inauguratorMyIDForServer is not None, \
                'If communicating with server, must specifiy --inauguratorMyIDForServer'

    def _createPartitionTable(self):
        lvmetad.Lvmetad()
        logging.info("Target device is %(device)s layout=%(layout)s",
                     dict(device=self._targetDevice, layout=self._args.inauguratorPartitionLayout))
        partitionTable = partitiontable.PartitionTable(self._targetDevice,
                                                       layoutScheme=self._args.inauguratorPartitionLayout, hypervisor=self._args.hypervisor)
        if self._args.inauguratorClearDisk:
            partitionTable.clear()
        partitionTable.verify()
        self._bootPartitionPath = partitionTable.getBootPartitionPath()

    def _configureETC(self, destination):
        self._etcLabelFile.write(self._label)
        fstab.createFSTab(
            rootPath=destination, root=self._mountOp.rootPartition(),
            boot=self._mountOp.bootPartition(), swap=self._mountOp.swapPartition())
        logging.info("/etc/fstab created")
        if self._args.inauguratorChangeRootPassword:
            passwd.setRootPassword(destination, self._args.inauguratorChangeRootPassword)
            logging.info("Changed root password")

    @staticmethod
    def _getSerialDevices():
        with open("/proc/cmdline", "r") as cmdLineFile:
            cmdLine = cmdLineFile.read()
        args = cmdLine.split(" ")
        keyValuePairs = [arg.split("=", 1) for arg in args if "=" in arg]
        consoles = [value for key, value in keyValuePairs if key == "console"]
        return consoles

    def _createBootAndInstallGrub(self, destination):
        with self._mountOp.mountBoot() as bootDestination:
            sh.run("rm -rf %s/*; sync" % bootDestination)  # LBM1-4920
            sh.run("rsync -rlpgDS --delete-before %s/boot/ %s/" % (destination, bootDestination))
        with self._mountOp.mountBootInsideRoot():
            serialDevices = self._getSerialDevices()
            if serialDevices:
                logging.info("Overriding GRUB2 user settings to set serial devices to '%(devices)s'...",
                             dict(devices=serialDevices))
            else:
                logging.warn("a 'console' argument was not given. Cannot tell which serial device to "
                             "redirect the console output to (default values in the label will be used).")
            grub.updateGrubConf(serialDevices, destination, self._args.inauguratorPassthrough)
            logging.info("Installing GRUB2...")
            grub.install(self._targetDevice, destination)
            logging.info("Reading newly generated GRUB2 configuration file for later use...")
            grub_prefix = grub.grub_prefix(destination)
            assert grub_prefix is not None
            grubConfigFilename = os.path.join(destination, "boot", grub_prefix, "grub.cfg")
            with open(grubConfigFilename, "r") as grubConfigFile:
                self._grubConfig = grubConfigFile.read()

    def _osmosFromNetwork(self, destination, timeout_after = 20*60): #20min
        if not self._args.inauguratorIsNetworkAlreadyConfigured:
            network.Network(
                macAddress=self._args.inauguratorUseNICWithMAC, ipAddress=self._args.inauguratorIPAddress,
                netmask=self._args.inauguratorNetmask, gateway=self._args.inauguratorGateway)
        self._debugPort = debugthread.DebugThread()
        if self._args.inauguratorServerAMQPURL:
            self._talkToServer = talktoserver.TalkToServer(
                amqpURL=self._args.inauguratorServerAMQPURL, myID=self._args.inauguratorMyIDForServer)
            hwinfo = {'net': network.list_devices_info()}
            self.send_hwinfo(self._args.inauguratorSelfTestServerUrl)
            if dirsize.check_storage_size_over_threshold(destination, DIR_THRESHOLD):
                logging.info("dir: %s is over threshold: %s - cleaning osmosis" % (destination, str(DIR_THRESHOLD)))
                self.try_to_remove_osmosis(destination)
            self._talkToServer.checkIn(hwinfo=hwinfo)
            message = self._talkToServer.label()
            self._label = json.loads(message)['rootfs']
        else:
            self._label = self._args.inauguratorNetworkLabel
        ATTEMPTS = 2
        signal.signal(signal.SIGALRM, self._raise_timeout_exception)
        signal.alarm(timeout_after)
        try:
            for attempt in range(ATTEMPTS):
                try:
                    if attempt == 0:
                        self._checkoutOsmosFromNetwork(destination,
                                                       self._args.inauguratorOsmosisObjectStores,
                                                       self._args.inauguratorWithLocalObjectStore,
                                                       self._localObjectStore,
                                                       self._args.inauguratorIgnoreDirs,
                                                       self._talkToServer,
                                                       inspectErrors=True)
                    else:
                        self._checkoutOsmosFromNetwork(destination,
                                                       self._args.inauguratorOsmosisObjectStores,
                                                       self._args.inauguratorWithLocalObjectStore,
                                                       self._localObjectStore,
                                                       self._args.inauguratorIgnoreDirs,
                                                       talkToServer=None,
                                                       inspectErrors=False)
                    return
                except osmose.CorruptedObjectStore:
                    logging.info("Found corrupted object store - purge osmosis!")
                    self.try_to_remove_osmosis(destination)
                except OsmosisTimeoutException as e:
                    logging.info("Failed _osmosFromNetwork due to Timeout. attempt #%d" % attempt)
                    self.try_to_remove_osmosis(destination)
                except Exception as e:
                    if self._debugPort is not None and self._debugPort.wasRebootCalled():
                        logging.info("Waiting to be reboot (from outside)...")
                        blockForever = threading.Event()
                        blockForever.wait()
                    else:
                        try:
                            self._talkToServer.failed(message=str(e))
                        except:
                            pass
                    raise e
        except Exception:
            raise e
        finally:
            signal.alarm(0)


    def try_to_remove_osmosis(self, destination):
        try:
            objectStorePath = os.path.join(destination, "var", "lib", "osmosis", "objectstore")
            osmosiscleanup.OsmosisCleanup(destination, objectStorePath=objectStorePath).eraseEverything()
        except:
            pass


    def _checkoutOsmosFromNetwork(self, destination, osmosisObjectStore, withLocalObjectStore, localOsmosisObjectStroe,
                                  ignoreDir, talkToServer, inspectErrors=False):
            osmos = osmose.Osmose(
                destination=destination,
                objectStores=osmosisObjectStore,
                withLocalObjectStore=withLocalObjectStore,
                localObjectStore=localOsmosisObjectStroe,
                ignoreDirs=ignoreDir,
                talkToServer=talkToServer)
            osmos.tellLabel(self._label)
            osmos.wait(inspect_erros=inspectErrors)

    def _osmosFromDOK(self, destination):
        dok = diskonkey.DiskOnKey(self._args.inauguratorExpectedLabel)
        with dok.mount() as source:
            osmos = osmose.Osmose(
                destination, objectStores=source + "/osmosisobjectstore",
                withLocalObjectStore=self._args.inauguratorWithLocalObjectStore,
                localObjectStore=self._localObjectStore,
                ignoreDirs=self._args.inauguratorIgnoreDirs,
                talkToServer=self._talkToServer)
            with open("%s/inaugurate_label.txt" % source) as f:
                self._label = f.read().strip()
            osmos.tellLabel(self._label)  # This must stay under the dok mount 'with' statement
            osmos.wait()

    def _osmosFromCDROM(self, destination):
        cdromInstance = cdrom.Cdrom(self._args.inauguratorExpectedLabel)
        with cdromInstance.mount() as source:
            osmos = osmose.Osmose(
                destination, objectStores=source + "/osmosisobjectstore",
                withLocalObjectStore=self._args.inauguratorWithLocalObjectStore,
                localObjectStore=self._localObjectStore,
                ignoreDirs=self._args.inauguratorIgnoreDirs,
                talkToServer=self._talkToServer)
            with open("%s/inaugurate_label.txt" % source) as f:
                self._label = f.read().strip()
            osmos.tellLabel(self._label)  # This must stay under the mount 'with' statement
            osmos.wait()

    def _osmosFromLocalObjectStore(self, destination):
        osmos = osmose.Osmose(
            destination, objectStores=None,
            withLocalObjectStore=self._args.inauguratorWithLocalObjectStore,
            localObjectStore=self._localObjectStore,
            ignoreDirs=self._args.inauguratorIgnoreDirs,
            talkToServer=self._talkToServer)
        self._label = self._args.inauguratorNetworkLabel
        osmos.tellLabel(self._label)
        osmos.wait()

    def _sync(self):
        logging.info("sync...")
        sh.run("busybox", "sync")
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
        assert self._bootPartitionPath is not None, "Please initialize boot partition path first"
        self._mountOp.setBootPartitionPath(self._bootPartitionPath)

    def _loadKernelForKexecing(self, destination):
        self._loadKernel = loadkernel.LoadKernel()
        self._loadKernel.fromBootPartitionGrubConfig(
            grubConfig=self._grubConfig,
            bootPath=os.path.join(destination, "boot"), rootPartition=self._mountOp.rootPartition())

    def _doOsmosisFromSource(self, destination):
        cleanup = osmosiscleanup.OsmosisCleanup(destination, objectStorePath=self._localObjectStore)
        try:
            self._doOsmosisFromSourceUnsafe(destination)
        except Exception as e:
            logging.exception("Failed to osmosis from source. %(type)s, %(msg)s", dict(type=type(e), msg=e.message))
            cleanup.eraseEverything()
            sh.run("busybox rm -fr %s/*" % destination)
            if self._talkToServer:
                self._talkToServer.progress(dict(state='warning', message=str(e)))

    def _raise_timeout_exception(signum, frame, args = None):
        raise OsmosisTimeoutException("SIGALRM Timeout was triggered")

    def _doOsmosisFromSourceUnsafe(self, destination):
        if self._args.inauguratorSource == 'network':
            self._osmosFromNetwork(destination)
        elif self._args.inauguratorSource == 'DOK':
            self._osmosFromDOK(destination)
        elif self._args.inauguratorSource == 'CDROM':
            self._osmosFromCDROM(destination)
        elif self._args.inauguratorSource == 'local':
            self._osmosFromLocalObjectStore(destination)
        else:
            assert False, "Unknown source %s" % self._args.inauguratorSource

    def _verify(self):
        if not self._args.inauguratorVerify:
            return
        self._sync()
        verify.Verify.dropCaches()
        with self._mountOp.mountRoot() as destination:
            verify.Verify(destination, self._label, self._talkToServer, self._localObjectStore).go()

    def _getSSDDeviceNames(self):
        blockDevices = os.listdir('/sys/block')
        storageDevices = [dev for dev in blockDevices if dev.startswith('sd')]
        ssdDevices = []
        for device in storageDevices:
            isRotationalPathComponents = ['sys', 'block', device, 'queue', 'rotational']
            isRotationalPath = os.path.join(*isRotationalPathComponents)
            with open(isRotationalPath, 'rb') as f:
                isRotational = f.read()
            isRotational = bool(int(isRotational.strip()))
            if not isRotational:
                ssdDevices.append(device)
        return ssdDevices

    def _disableNCQ(self):
        devices = self._getSSDDeviceNames()
        if not devices:
            print 'Did not find any non-rotational storage devices on which to disable NCQ.'
            return
        print 'Disabling NCQ for the following SSD devices: {}...'.format(devices)
        for device in devices:
            try:
                queueDepthPath = '/sys/block/{}/device/queue_depth'.format(device)
                print sh.run('busybox echo 1 > {}'.format(queueDepthPath))
                print sh.run('busybox echo "{} is now:" '.format(queueDepthPath))
                print sh.run('busybox cat {}'.format(queueDepthPath))
            except Exception, ex:
                print ex.message

    def send_hwinfo(self, url):
        with open('/destRoot/hwinfo_defaults', 'w') as f:
            json.dump({'mac': self._args.inauguratorUseNICWithMAC, 'ip': self._args.inauguratorIPAddress,
                       'id': self._args.inauguratorMyIDForServer, 'url': url}, f)
        try:
            self_test_data = selfTest.HWinfo().run()

            msg = dict(info=self_test_data,
                       mac=self._args.inauguratorUseNICWithMAC,
                       ip=self._args.inauguratorIPAddress,
                       id=self._args.inauguratorMyIDForServer
                       )
            url = "http://{}/{}/".format(url, msg['id'])
            logging.info("send HW info to self test in url: %(url)s", dict(url=url))
            requests.post(url, json=msg)
        except Exception as e:
            logging.info("self test failed... %(type)s, %(msg)s", dict(type=type(e), msg=e.message))
