#!/bin/sh
#copy into the initrd with creating the parent directory first
set -e
at_least_one=0
for path in $@; do
    if [ ! -e "$path" ]; then
        echo "$path does not exist"
        exit 1
    fi
    at_least_one=1
done
if [ "$at_least_one" == "0" ]; then
    echo "Zero parameters provided"
    exit 1
fi
directory=`dirname $@ | head -1`
mkdir -p $DEST/$directory 2>/dev/null
for path in `find $@ -maxdepth 0 -and -not -type d`; do
    cp -faL $path $DEST/$directory/
done
