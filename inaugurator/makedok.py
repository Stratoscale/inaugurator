import argparse
import logging
import subprocess
import tempfile
import os
import shutil
from inaugurator import sh
from inaugurator import partitiontable

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("--label", required=True)
parser.add_argument("--device", default="/dev/sdb")
parser.add_argument("--forceClear", action="store_true")
args = parser.parse_args()


def deviceSizeGB(device):
    return int(sh.run("sfdisk -s %s" % device)) / 1024 / 1024


def transferOsmosisLabelWithRetry(label, mountPoint, retry=5, sleep=5):

    success = False
    failed_count = 0

    while not success:
        try:
            transferOsmosisLabel(label, mountPoint)
            success = True
        except Exception as e:
            failed_count += 1
            if failed_count > retry:
                logging.error("Failed to transfer label %s after %s times" % (label, failed_count))
                raise e
            time.sleep(sleep)
            logging.info("Failed to transfer label %s, going to retry" % label)


def transferOsmosisLabel(label, mountPoint):
    objectStores = sh.run("solvent printobjectstores").strip()
    sh.run(
        "osmosis transfer %s --transferDestination=%s/osmosisobjectstore --objectStores=%s "
        "--putIfMissing" % (label, mountPoint, objectStores))


def installInaugurator(device, mountPoint):
    INAUGURATOR_KERNEL = "/usr/share/inaugurator/inaugurator.vmlinuz"
    INAUGURATOR_INITRD = "/usr/share/inaugurator/inaugurator.fat.initrd.img"
    shutil.copy(INAUGURATOR_KERNEL, mountPoint)
    shutil.copy(INAUGURATOR_INITRD, mountPoint)
    installerExecutable = "grub2-install"
    try:
        sh.run("which %s" % installerExecutable)
    except:
        installerExecutable = "grub-install"
    sh.run("%s --target=i386-pc --boot-directory=%s/boot %s" % (installerExecutable, mountPoint, device))
    inauguratorArguments = '--inauguratorSource=DOK --inauguratorChangeRootPassword=strato'
    grubCfg = "%s/boot/grub2/grub.cfg" % mountPoint
    if not os.path.isdir(os.path.dirname(grubCfg)):
        grubCfg = "%s/boot/grub/grub.cfg" % mountPoint
    with open(grubCfg, "w") as f:
        f.write('set timeout=1\n'
                'set default=0\n'
                'menuentry "Installer" {\n'
                '    linux /inaugurator.vmlinuz %s\n'
                '    initrd /inaugurator.fat.initrd.img\n'
                '}\n' % inauguratorArguments)


def partitionTableCheck(device):
    partitionTable = partitiontable.PartitionTable(device).parsePartitionTable()
    return len(partitionTable) == 1 and partitionTable[0]['id'] == 6

if deviceSizeGB(args.device) > 32:
    raise Exception(
        "The size of the device is %dGB, which doesn't look like a DOK. aborting to avoid "
        "deleting your own HD" % deviceSizeGB(args.device))
for i in xrange(1, 5):
    subprocess.call(
        ["umount", "%s%d" % (args.device, i)], stdout=open("/dev/null", "w"), stderr=subprocess.STDOUT)
partition = args.device + "1"
if args.forceClear or not partitionTableCheck(args.device):
    logging.info("clearing head of disk")
    sh.run("dd if=/dev/zero of=%s count=256 bs=1M" % args.device)
    logging.info("Creating partition")
    sh.run("echo '2,,6' | sfdisk %s" % args.device)
    sh.run("mkfs.vfat %s" % partition)
    sh.run("dosfslabel %s STRATODOK" % partition)
mountPoint = tempfile.mkdtemp()
try:
    sh.run("mount %s %s" % (partition, mountPoint))
    try:
        with open(os.path.join(mountPoint, "inaugurate_label.txt"), "w") as f:
            f.write(args.label)
        logging.info("Installing inaugurator")
        installInaugurator(args.device, mountPoint)
        logging.info("Transferring Osmosis Label %s" % args.label)
        transferOsmosisLabelWithRetry(args.label, mountPoint)
    finally:
        logging.info("Unmounting DOK")
        sh.run("umount %s" % mountPoint)
finally:
    os.rmdir(mountPoint)
