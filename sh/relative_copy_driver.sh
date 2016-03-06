#!/bin/sh
#copy into the initrd the executable and its dependencies
#requires DEST environment set
#requires KERNEL_UNAME_R environment set

#Blacklist of firmware binaries not found in the distribution
# See: http://www.spinics.net/lists/linux-scsi/msg85340.html
FIRMWARE_BLACKLIST="-e ql2600_fw.bin -e ql2700_fw.bin -e ql8300_fw.bin"

set -e
for ko in `modprobe --show-depends $1 --set-version=$KERNEL_UNAME_R | sed 's/insmod //'`; do
    sh/relative_copy_glob.sh $ko
done
modinfo --field firmware $1 --set-version=$KERNEL_UNAME_R >& /dev/null
for firmware in `modinfo --field firmware $1 --set-version=$KERNEL_UNAME_R | grep -v $FIRMWARE_BLACKLIST`; do
    sh/relative_copy_glob.sh /lib/firmware/$firmware
done
