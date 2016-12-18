import paramiko
import time
import scp
import os

SERVER = "10.16.3.1"
USER = "root"
PASS = "strato"

INAUGURATOR_IMAGE = "inaugurator.thin.initrd.img"
INAUGURATOR_PATH = "/usr/share/inaugurator"
PXE_PATH = "/var/lib/rackattack/pxeboot"
NEW_INAUGURATOR_IMAGE = "build/inaugurator.thin.initrd.img"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=USER, password=PASS)

for basePath in [INAUGURATOR_PATH, PXE_PATH]:

    backupDir = "backup_" + time.strftime("%d%b%H%M%S")
    backupPath = os.path.join(basePath, backupDir)

    cmd = "mkdir %s" % backupPath
    print "Creating backup folder: %s" % cmd
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)

    imagePath = os.path.join(basePath, INAUGURATOR_IMAGE)
    cmd = "cp %s %s" % (imagePath, backupPath)
    print "Copying old inaugurator to backup folder: %s" % cmd
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)

    print "Copying new inaugurator to replace the old one: %s" % basePath
    scp_session = scp.SCPClient(ssh.get_transport())
    scp_session.put(NEW_INAUGURATOR_IMAGE, basePath)
