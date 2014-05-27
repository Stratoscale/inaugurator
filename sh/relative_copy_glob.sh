#!/bin/sh
#copy into the initrd with creating the parent directory first
set -e
directory=`dirname $@ | head -1`
mkdir -p $DEST/$directory 2>/dev/null
for path in `find $@ -maxdepth 0 -and -not -type d`; do
    cp -faL $path $DEST/$directory/
done
