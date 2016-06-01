from inaugurator import sh


def setRootPassword(rootPath, password):
    if sh.has_tool(rootPath, 'chpasswd'):
        sh.run("echo 'root:%(password)s' | chroot %(rootPath)s chpasswd" % dict(
            password=password, rootPath=rootPath))
    else:
        sh.run("echo '%(password)s' | chroot %(rootPath)s passwd --stdin root" % dict(
            password=password, rootPath=rootPath))
