import os
import logging
from inaugurator import sh


USER_SETTINGS_DIR = "etc/default"
USER_SETTINGS_FILENAME = "grub"


def setSerialDevice(serialDevice, destination):
    destUserSettingsDir = os.path.join(destination, USER_SETTINGS_DIR)
    if os.path.isfile(destUserSettingsDir):
        logging.warning("It seems that there's a file instead of a directory in GRUB2's user settings path "
                        " (%(path)s). Removing it.", dict(path=destUserSettingsDir))
        os.unlink(destUserSettingsDir)
    if not os.path.exists(destUserSettingsDir):
        os.makedirs(destUserSettingsDir)
    destUserSettingsFilename = os.path.join(destUserSettingsDir, USER_SETTINGS_FILENAME)
    with open(destUserSettingsFilename, "wb") as userSettingsFile:
        userSettingsFile.write("# Generated by Inaugurator\n")
        userSettingsFile.write("GRUB_CMDLINE_LINUX=\"console=tty0 console=%s\"\n" % serialDevice)


def install(targetDevice, destination):
    chrootScript = 'grub2-install %s && grub2-mkconfig > /boot/grub2/grub.cfg' % targetDevice
    sh.run("/usr/sbin/busybox chroot %s sh -c '%s'" % (destination, chrootScript))
