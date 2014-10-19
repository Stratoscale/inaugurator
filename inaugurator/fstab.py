import os


def createFSTab(rootPath, root, boot, swap):
    filename = os.path.join(rootPath, "etc", "fstab")
    with open(filename, "w") as f:
        f.write(_TEMPLATE % dict(root=root, boot=boot, swap=swap))


_TEMPLATE = """
LABEL=ROOT /                       ext4    defaults        1 1
LABEL=SWAP swap                    swap    defaults        0 0
LABEL=BOOT /boot                   ext4    defaults        1 2
"""
