#!/bin/sh
#list the drivers for the fat version
BLACKLIST='-e bfa -e csiostor -e cxgb4 -e bna -e aic94xx -e r8169'
KERNEL_VERSION=$1
set -e
find /lib/modules/$KERNEL_VERSION/kernel/drivers/net/ethernet /lib/modules/$KERNEL_VERSION/kernel/drivers/scsi /lib/modules/$KERNEL_VERSION/kernel/drivers/nvme /lib/modules/$KERNEL_VERSION/kernel/drivers/message /lib/modules/$KERNEL_VERSION/kernel/weak-updates/cciss -type f -printf '%f\n' | sed 's/\.ko$//' | sed 's/\.ko.xz$//' | grep -v $BLACKLIST
