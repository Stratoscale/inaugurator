import os


def createFSTab(rootPath, root, boot):
    filename = os.path.join(rootPath, "etc", "fstab")
    with open(filename, "w") as f:
        f.write(_TEMPLATE % dict(root=root, boot=boot))


_TEMPLATE = """
%(root)s /                       ext4    defaults        1 1
%(boot)s /boot                   ext4    defaults        1 2
"""
