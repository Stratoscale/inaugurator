import os


def createFSTab(rootPath, root, boot, swap):
    filename = os.path.join(rootPath, "etc", "fstab")
    if os.path.exists('/sys/firmware/efi'):
        _TEMPLATE = _COMMON_TEMPLATE + _EFI_TEMPLATE.strip("\n")
    else:
        _TEMPLATE = _COMMON_TEMPLATE
    with open(filename, "w") as f:
        f.write(_TEMPLATE)


_COMMON_TEMPLATE = """
LABEL=ROOT /                       ext4    defaults        1 1
LABEL=SWAP swap                    swap    defaults        0 0
LABEL=BOOT /boot                   ext4    defaults        1 2
"""

_EFI_TEMPLATE = """
LABEL=EFI /boot/efi                 vfat    umask=0077,shortname=winnt 0 2
"""
