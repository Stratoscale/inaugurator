import os
import logging
from inaugurator import sh


USER_SETTINGS_DIR = "etc/default"
USER_SETTINGS_FILENAME = "grub"


def changeGrubConfiguration(destination, data, parameter=None)
    destUserSettingsDir = os.path.join(destination, USER_SETTINGS_DIR)
    existingConfiguration = ""
    if os.path.isfile(destUserSettingsDir):
        logging.warning("It seems that there's a file instead of a directory in GRUB2's user settings path "
                        " (%(path)s). Removing it...", dict(path=destUserSettingsDir))
        os.unlink(destUserSettingsDir)
    if not os.path.exists(destUserSettingsDir):
        os.makedirs(destUserSettingsDir)
    destUserSettingsFilename = os.path.join(destUserSettingsDir, USER_SETTINGS_FILENAME)
    if os.path.isfile(destUserSettingsFilename):
        logging.info("GRUB2's user settings file already exists. Reading it...")
        with open(destUserSettingsFilename, "r") as grubDefaultConfig:
            existingConfiguration = grubDefaultConfig.read()
    elif os.path.exists(destUserSettingsFilename):
        logging.warning("It seems that there is a non-file in GRUB2's user settings path: %(path)s. Will not"
                        "modify GRUB2 settings.", dict(path=destUserSettingsDir))
        return
    wasGrubCmdlineLinuxParameterWritten = False
    logging.info("Modifying GRUB2 user settings file...")
    if parameter:
        newParameterConfiguration = "%s=%s" % (paramater, data)
    with open(destUserSettingsFilename, "wb") as userSettingsFile:
        for line in existingConfiguration.splitlines():
            line = line.strip()
            if line.startswith("GRUB_CMDLINE_LINUX="):
                wasGrubCmdlineLinuxParameterWritten = True
                maxSplit = 1
                cmdline = line.split("=", maxSplit)[1].strip(" \"")
                if paramater:
                    logging.info("Grub configuration: Overriding %s parameter with %s", paramater, data)
                    argsWithoutParameter = [arg for arg in cmdline.split(" ") if not arg.startswith("%s=" % parameter)]
                    configurationWithoutParameter = " ".join(argsWithoutParameter)
                    line = "GRUB_CMDLINE_LINUX=\"%(configurationWithoutParameter)s %(parameterConfiguration)s\"" % \
                        dict(configurationWithoutParameter=configurationWithoutParameter,
                             consoleConfiguration=consoleConfiguration)
                else:
                    line = "GRUB_CMDLINE_LINUX=\"%(newConfiguration)s %(oldConfiguration)\"" % \
                        dict(newConfiguration=data,
                             oldConfiguration=cmdline)
                logging.info("Grub configuration line is %s", line)

            userSettingsFile.write(line)
            userSettingsFile.write(os.linesep)
        if not wasGrubCmdlineLinuxParameterWritten:
            userSettingsFile.write("# Generated by Inaugurator\n")
            userSettingsFile.write("GRUB_CMDLINE_LINUX=\"%s\"\n" % (consoleConfiguration,))


def setSerialDevices(serialDevices, destination):
    destUserSettingsDir = os.path.join(destination, USER_SETTINGS_DIR)
    existingConfiguration = ""
    if os.path.isfile(destUserSettingsDir):
        logging.warning("It seems that there's a file instead of a directory in GRUB2's user settings path "
                        " (%(path)s). Removing it...", dict(path=destUserSettingsDir))
        os.unlink(destUserSettingsDir)
    if not os.path.exists(destUserSettingsDir):
        os.makedirs(destUserSettingsDir)
    destUserSettingsFilename = os.path.join(destUserSettingsDir, USER_SETTINGS_FILENAME)
    if os.path.isfile(destUserSettingsFilename):
        logging.info("GRUB2's user settings file already exists. Reading it...")
        with open(destUserSettingsFilename, "r") as grubDefaultConfig:
            existingConfiguration = grubDefaultConfig.read()
    elif os.path.exists(destUserSettingsFilename):
        logging.warning("It seems that there is a non-file in GRUB2's user settings path: %(path)s. Will not"
                        "modify GRUB2 settings.", dict(path=destUserSettingsDir))
        return
    wasGrubCmdlineLinuxParameterWritten = False
    logging.info("Modifying GRUB2 user settings file...")
    consoleConfiguration = " ".join(["console=%s" % (device,) for device in serialDevices])
    with open(destUserSettingsFilename, "wb") as userSettingsFile:
        for line in existingConfiguration.splitlines():
            line = line.strip()
            if line.startswith("GRUB_CMDLINE_LINUX="):
                wasGrubCmdlineLinuxParameterWritten = True
                maxSplit = 1
                cmdline = line.split("=", maxSplit)[1].strip(" \"")
                argsWithoutConsole = [arg for arg in cmdline.split(" ") if not arg.startswith("console=")]
                configurationWithoutConsole = " ".join(argsWithoutConsole)
                line = "GRUB_CMDLINE_LINUX=\"%(configurationWithoutConsole)s %(consoleConfiguration)s\"" % \
                    dict(configurationWithoutConsole=configurationWithoutConsole,
                         consoleConfiguration=consoleConfiguration)
            userSettingsFile.write(line)
            userSettingsFile.write(os.linesep)
        if not wasGrubCmdlineLinuxParameterWritten:
            userSettingsFile.write("# Generated by Inaugurator\n")
            userSettingsFile.write("GRUB_CMDLINE_LINUX=\"%s\"\n" % (consoleConfiguration,))


def install(targetDevice, destination):
    try:
        chrootScript = 'grub2-install %s && grub2-mkconfig > /boot/grub2/grub.cfg' % targetDevice
        sh.run("/usr/sbin/busybox chroot %s sh -c '%s'" % (destination, chrootScript))
        return '/boot/grub2/grub.cfg'
    except:
        logging.exception("Failed to run grub2-install or grub2-mkconfig. Is the dest rootfs a debian-like?")
        logging.warning("Trying to run grub-install and grub-mkconfig instead")
        chrootScript = 'grub-install %s && grub-mkconfig > /boot/grub/grub.cfg' % targetDevice
        sh.run("/usr/sbin/busybox chroot %s sh -c '%s'" % (destination, chrootScript))
        return '/boot/grub/grub.cfg'
