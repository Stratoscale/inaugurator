#!/bin/bash
source ${WORKSPACE_TOP}/common/tools/version_functions

if [ "$1" != "inaugurator"  ]; then
	exit 1
fi

cd $WORKSPACE_TOP/inaugurator

VERSION=$(git rev-parse HEAD)
UNVERSIONED=$(md5sum_git_modified_unversioned .)
echo $(md5sum_string "$VERSION$UNVERSIONED" | cut -c1-12)
