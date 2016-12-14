from inaugurator import sh


def setRootPassword(rootPath, password):
    sh.run("echo root:%(password)s | chroot %(rootPath)s chpasswd" % dict(
        password=password, rootPath=rootPath))
