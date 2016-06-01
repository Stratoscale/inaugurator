#!/bin/bash


if [ "$1" != "inaugurator"  ]; then
	exit 1
fi

cd $WORKSPACE_TOP/inaugurator

VERSION=$(git rev-parse HEAD)
UNVERSIONED_FILES=$(git status -s  | awk '{print $2}')

VERSION=$(md5sum <<< "${VERSION}")| awk '{print $1}'

if [ x"$UNVERSIONED_FILES" != x"" ]; then 
	HASHES="$(md5sum ${UNVERSIONED_FILES} |  awk '{print $1}')  $VERSION"
	VERSION=$(md5sum <<< ${HASHES} | awk '{print $1}')
fi

echo $VERSION | cut -c1-12

