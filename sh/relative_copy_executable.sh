#!/bin/sh
#copy into the initrd the executable and its dependencies
#requires DEST environment set
set -e
sh/relative_copy_glob.sh $1
for dependency in `ldd $1 | grep '=> /.* (' | sed 's/.*=> \(.*\?\) (0x.*/\1/'`; do
    sh/relative_copy_glob.sh $dependency
done
