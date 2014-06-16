import os


def createFSTab(rootPath, root, boot, swap):
    filename = os.path.join(rootPath, "etc", "fstab")
    with open(filename, "w") as f:
        f.write(_TEMPLATE % dict(root=root, boot=boot, swap=swap))


_TEMPLATE = """
%(root)s /                       ext4    defaults        1 1
%(swap)s swap                    swap    defaults        0 0
%(boot)s /boot                   ext4    defaults        1 2
"""
