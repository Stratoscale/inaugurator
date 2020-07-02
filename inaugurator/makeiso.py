import argparse
import logging
import subprocess
import tempfile
import os
import shutil
import sys
import time
from inaugurator import sh

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("--label", required=True)
parser.add_argument("--ISOlabel", default="STRATOISO")
parser.add_argument("--output", required=True)
parser.add_argument(
    "--reserveFile", nargs="*",
    help="Space separated list of <sizeKB>:<filename>:<fill> - a file will be filled with fill"
    " for sizeKB kilobytes, allowing editing the ISO. make sure to give different fills to different files.")
parser.add_argument("--editReserved")
parser.add_argument("--showReserved", action="store_true")
parser.add_argument(
    "--reserved",
    help="<sizeKB>:<reserved filename>:<reserved fill>")
args = parser.parse_args()


def findReservedOffsetInISO():
    sizeKBText, reservedFilename, reservedFill = args.reserved.split(":")
    assert int(sizeKBText) % 16 == 0, "sizeKB % 16 != 0"
    size = int(sizeKBText) * 1024
    assert size % len(reservedFill) == 0, "fill must devide size"
    expected = (size / len(reservedFill)) * reservedFill
    with open(args.output, "r+b") as f:
        findAndSeek(f, expected)
        return f.tell(), size


def findAndSeek(f, expected):
    f.seek(0)
    firstBlock = expected[:512]
    while True:
        block = f.read(len(firstBlock))
        if block == "":
            raise Exception("Fill not found")
        if block == firstBlock:
            positionBefore = f.tell()
            candidatePosition = f.tell() - len(block)
            rest = f.read(len(expected) - len(block))
            if rest == expected[len(block):]:
                f.seek(candidatePosition)
                return
            f.seek(positionBefore)


if args.showReserved:
    offset, size = findReservedOffsetInISO()
    print "Offset:", offset
    print "Size:", size
    sys.exit(0)
elif args.editReserved:
    if ':' in args.editReserved:
        contentFilename, newFill = args.editReserved.split(':')
    else:
        contentFilename = args.editReserved
        newFill = '\0'
    offset, size = findReservedOffsetInISO()
    padding = (size / len(newFill)) * newFill
    with open(args.output, "r+b") as f:
        f.seek(offset)
        with open(contentFilename, "rb") as f2:
            data = f2.read()
        data += padding[:size - len(data)]
        f.write(data)
    sys.exit(0)


def waitForEmptyDir(directory, retry=12, interval=10):
    is_empty = False
    attempts = 0

    while not is_empty and attempts < retry:
        files = subprocess.check_output(['ls', '-l', directory]).split('\n')[1:-1]

        if len(files) == 0:
            is_empty = True
        else:
            logging.info("directory %s is not empty" % directory)
            attempts = attempts + 1
            time.sleep(interval)

    if not is_empty:
        logging.error("directory %s is not empty, failed to wait for process" % directory)
        raise Exception("%s directory is not empty - fix or rerun" % directory)


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


temp = os.path.join("/var", "tmp")
if not os.path.exists(temp):
    os.makedirs(temp)
try:
    with open(os.path.join(temp, "inaugurate_label.txt"), "w") as f:
        f.write(args.label)
    logging.info("Transferring label")
    transferOsmosisLabelWithRetry(args.label, temp)
    logging.info("Done Transferring label")
    os.makedirs(os.path.join(temp, "isolinux"))
    shutil.copy("resources/isolinux.bin", os.path.join(temp, "isolinux"))
    shutil.copy("resources/ldlinux.c32", os.path.join(temp, "isolinux"))
    INAUGURATOR_KERNEL = "resources/inaugurator.vmlinuz"
    INAUGURATOR_INITRD = "resources/inaugurator.fat.initrd.img"
    shutil.copy(INAUGURATOR_KERNEL, temp)
    shutil.copy(INAUGURATOR_INITRD, temp)
    with open(os.path.join(temp, "isolinux", "message.txt"), "w") as f:
        f.write("Inaugurator ISO\n")
    INAUGURATOR_ARGUMENTS = "--inauguratorSource=CDROM --inauguratorChangeRootPassword=strato"
    with open(os.path.join(temp, "isolinux", "isolinux.cfg"), "w") as f:
        f.write("""
display /isolinux/message.txt
prompt 0
default Inaugurator

label Inaugurator
    kernel /inaugurator.vmlinuz
    append initrd=/inaugurator.fat.initrd.img %s
""" % INAUGURATOR_ARGUMENTS)
    for opt in args.reserveFile:
        sizeKBText, filename, fill = opt.split(":")
        assert int(sizeKBText) % 16 == 0, "sizeKB % 16 != 0"
        size = int(sizeKBText) * 1024
        assert size % len(fill) == 0, "fill must devide size"
        data = (size / len(fill)) * fill
        with open(os.path.join(temp, filename), "wb") as f:
            f.write(data)
    waitForEmptyDir(os.path.join(temp, "osmosisobjectstore", "osmosisDrafts"))
    logging.info("Creating ISO")
    subprocess.check_call([
        "mkisofs", "-allow-limited-size", "-r", "-V", args.ISOlabel, "-cache-inodes", "-J", "-R", "-l",
        "-b", "isolinux/isolinux.bin", "-c", "isolinux/boot.cat", "-no-emul-boot",
        "-boot-load-size", "4", "-boot-info-table", "-o", args.output, "%s/" % temp])
    logging.info("Done creating ISO")
finally:
    shutil.rmtree(temp, ignore_errors=True)
