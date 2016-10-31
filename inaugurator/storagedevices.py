import os
import os.path
import logging
import traceback
import subprocess


class DiskFailedSelfTest(Exception):
    pass


class StorageDevices:
    @classmethod
    def disableNCQ(cls):
        devices = cls._getSSDDeviceNames()
        if not devices:
            logging.info('Did not find any non-rotational storage devices on which to disable NCQ.')
            return
        logging.info('Disabling NCQ for the following SSD devices: {}...'.format(devices))
        for device in devices:
            try:
                queueDepthPath = '/sys/block/{}/device/queue_depth'.format(device)
                logging.info(sh.run('busybox echo 1 > {}'.format(queueDepthPath)))
                logging.info(sh.run('busybox echo "{} is now:" '.format(queueDepthPath)))
                logging.info(sh.run('busybox cat {}'.format(queueDepthPath)))
            except:
                logging.info(traceback.format_exc())

    @classmethod
    def findFirstDeviceOfType(cls, deviceType, talkToServer=None):
        if deviceType == "SSD":
            devices = cls._getSSDDeviceNames()
        else:
            assert deviceType == "HDD", deviceType
            devices = cls._getHDDDeviceNames()
        if not devices:
            if talkToServer is not None:
                talkToServer.targetDeviceTypeNotFound(deviceType)
            raise Exception("Could not find a %s device to be used as a target device" % (deviceType,))
        logging.info("The following devices were found: %s" % (",".join(devices),))
        devicePath = os.path.join("/dev", devices[0])
        return devicePath

    @classmethod
    def readSmartDataFromAllDevices(cls, talkToServer=None, failOnFailedHealthTest=False):
        devices = cls._getSSDDeviceNames() + cls._getHDDDeviceNames()
        if devices:
            logging.info("Reading SMART data...")
            for device in devices:
                try:
                    cls._readSmartDataFromDevice(device)
                except DiskFailedSelfTest as ex:
                    if failOnFailedHealthTest:
                        if talkToServer is not None:
                            talkToServer.healthTestFailed(device)
                        raise ex
        else:
            logging.warning("No storage devices were found to read SMART data from.")

    @staticmethod
    def _readSmartDataFromDevice(device):
        device = "/dev/{}".format(device)
        cmd = ["smartctl", "-a", "-i", device]
        logging.info("Reading SMART data from device %(device)s...", dict(device=device))
        cmdPipe = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
        output, _ = cmdPipe.communicate()
        if "overall-health self-assessment test result: FAILED!" in output:
            raise DiskFailedSelfTest(output)
        if cmdPipe.returncode != os.EX_OK:
            logging.error("Failed reading SMART data for device %(device)s", dict(device=device))

    @staticmethod
    def _getStorageDeviceNames():
        blockDevices = os.listdir('/sys/block')
        storageDevices = [dev for dev in blockDevices if dev.startswith('sd')]
        return storageDevices

    @classmethod
    def _getHDDDeviceNames(cls):
        devices = cls._getStorageDeviceNames()
        ssdDevices = cls._filterRotationalDevices(devices)
        nonSSDDevices = [device for device in devices if device not in ssdDevices]
        return nonSSDDevices

    @classmethod
    def _getSSDDeviceNames(cls):
        devices = cls._getStorageDeviceNames()
        ssdDevices = cls._filterRotationalDevices(devices)
        return ssdDevices

    @classmethod
    def _filterRotationalDevices(cls, devices):
        ssdDevices = []
        for device in devices:
            isRotationalPathComponents = ['sys', 'block', device, 'queue', 'rotational']
            isRotationalPath = os.path.join(*isRotationalPathComponents)
            with open(isRotationalPath, 'rb') as f:
                isRotational = f.read()
            isRotational = bool(int(isRotational.strip()))
            if not isRotational:
                ssdDevices.append(device)
        return ssdDevices
