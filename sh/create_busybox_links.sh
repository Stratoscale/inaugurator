#!/bin/sh
#create links for busybox applets
set -e
busybox=$1
directory=$(dirname $busybox)
cd $DEST/$directory
for applet in $($busybox --list); do
    if [ ! -e $applet ]; then
	ln -s $busybox $applet
    fi
done
