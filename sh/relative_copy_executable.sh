#!/bin/sh
#copy into the initrd the executable and its dependencies
#requires DEST environment set
set -e
sh/relative_copy_glob.sh $1
sh/relative_copy_executable_dependencies.sh $1
