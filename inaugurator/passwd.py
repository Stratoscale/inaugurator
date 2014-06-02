from inaugurator import sh


def setRootPassword(rootPath, password):
    sh.run("echo '%(password)s' | chroot %(rootPath)s passwd --stdin root" % dict(
        password=password, rootPath=rootPath))
