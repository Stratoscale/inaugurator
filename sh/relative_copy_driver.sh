#!/bin/sh
#copy into the initrd the executable and its dependencies
#requires DEST environment set
set -e
mkdir `dirname $INSMOD_SCRIPT` 2>/dev/null || true
modprobe --show-depends $1 >> $INSMOD_SCRIPT
for ko in `modprobe --show-depends $1 | sed 's/insmod //'`; do
    sh/relative_copy_glob.sh $ko
done
for firmware in `modinfo --field firmware $1`; do
    sh/relative_copy_glob.sh /lib/firmware/$firmware
done
