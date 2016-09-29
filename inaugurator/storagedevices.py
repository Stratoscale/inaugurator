import os
import os.path
import logging


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
            except Exception, ex:
                logging.info(ex.message)

    @classmethod
    def findFirstDeviceOfType(cls, deviceType):
        if deviceType == "SSD":
            devices = cls._getSSDDeviceNames()
        else:
            assert deviceType == "HDD", deviceType
            devices = cls._getHDDDeviceNames()
        if not devices:
            if cls._args.inauguratorServerAMQPURL:
                cls._talkToServer.targetDeviceTypeNotFound(deviceType)
            raise Exception("Could not find a %s device to be used as a target device" % (deviceType,))
        logging.info("The following devices were found: %s" % (",".join(devices),))
        devicePath = os.path.join("/dev", devices[0])
        return devicePath

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
