#!/bin/sh
#copy into the initrd the executable dependencies
#requires DEST environment set
set -e
for dependency in `ldd $1 | grep '=> /.* (' | sed 's/.*=> \(.*\?\) (0x.*/\1/'`; do
    sh/relative_copy_glob.sh $dependency
done
