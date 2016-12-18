import paramiko
import time
import scp
import os

SERVER = "10.16.3.1"
USER = "root"
PASS = "strato"

#INAUGURATOR_IMAGE = "inaugurator.thin.initrd.img"
INAUGURATOR_IMAGE = "test.img"
INAUGURATOR_PATH = "/usr/share/inaugurator/backup-"
PXE_PATH = "/var/lib/rackattack/pxeboot/backup-"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=USER, password=PASS)

for basePath in [INAUGURATOR_PATH, PXE_PATH]:

    cmd = "ls -Ct -d %s*/ | awk '{print $1}'" % basePath
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    backupDir = ssh_stdout.read().split("\n")[0]
    print "Rolling back from: %s" % backupDir

    print "Restoring old inaugurator to main folder: %s" % basePath
    oldInauguratorPath = os.path.join(backupDir, INAUGURATOR_IMAGE)
    cmd = "cp %s %s" % (oldInauguratorPath, basePath)
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
