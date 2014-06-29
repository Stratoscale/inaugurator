#!/bin/sh
#copy into the initrd the executable and its dependencies
#requires DEST environment set
#requires KERNEL_UNAME_R environment set
set -e
mkdir `dirname $INSMOD_SCRIPT` 2>/dev/null || true
modprobe --show-depends $1 --set-version=$KERNEL_UNAME_R >> $INSMOD_SCRIPT
for ko in `modprobe --show-depends $1 --set-version=$KERNEL_UNAME_R | sed 's/insmod //'`; do
    sh/relative_copy_glob.sh $ko
done
modinfo --field firmware $1 --set-version=$KERNEL_UNAME_R >& /dev/null
for firmware in `modinfo --field firmware $1 --set-version=$KERNEL_UNAME_R`; do
    sh/relative_copy_glob.sh /lib/firmware/$firmware
done
