from inaugurator import sh


def install(targetDevice, destination):
    chrootScript = 'grub2-install %s && grub2-mkconfig > /boot/grub2/grub.cfg' % targetDevice
    sh.run("/usr/sbin/busybox chroot %s sh -c '%s'" % (destination, chrootScript))
