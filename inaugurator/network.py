import re
from inaugurator import sh
import os
import time
import thread


class Network:
    _CONFIG_SCRIPT_PATH = "/etc/udhcp_script.sh"
    _NR_PING_ATTEMPTS = 40

    def __init__(self, macAddress, ipAddress, netmask, gateway):
        self._gateway = gateway
        interfacesTable = self._interfacesTable()
        assert macAddress.lower() in interfacesTable, "macAddress %s interfacesTable %s" % (macAddress, interfacesTable)
        interfaceName = interfacesTable[macAddress.lower()]
        sh.run("/usr/sbin/ifconfig lo 127.0.0.1")
        sh.run("/usr/sbin/ifconfig %s %s netmask %s" % (interfaceName, ipAddress, netmask))
        sh.run("busybox route add default gw %s" % self._gateway)
        self._validateLinkIsUp()

    def _validateLinkIsUp(self):
        print "Waiting for the connection to actually be up by pinging %s..." % (self._gateway,)
        linkIsUp = False
        for attemptIdx in xrange(self._NR_PING_ATTEMPTS):
            attemptNr = attemptIdx + 1
            try:
                result = sh.run("busybox ping -w 1 -c 1 %s" % (self._gateway,))
                linkIsUp = True
                print "Ping attempt #%d succeeded." % (attemptNr,)
                break
            except:
                print "Ping attempt #%d failed." % (attemptNr,)
        if not linkIsUp:
            raise Exception("No response from %s when trying to test if link was up" % (self._gateway,))

    def _interfacesTable(self):
        REGEX = re.compile(r'\d+:\s+([^:]+):\s+.*\s+link/ether\s+((?:[a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2})')
        ipOutput = sh.run("/usr/sbin/ip -o link")
        return {mac.lower(): interface for interface, mac in REGEX.findall(ipOutput)}

class NetworkInterface:
    def __init__(self, iface_name):
        self.iface = iface_name

    def ifup(self):
        cmd = "/usr/sbin/ip link set %s up" % self.iface
        sh.run(cmd)

    def _dev_status_path(self):
        return "/sys/class/net/%s" % self.iface

    def _device_attr(self, attr_name):
        return  sh.run("/usr/sbin/cat %s/%s" % (self._dev_status_path(), attr_name)).strip()

    def wait_link_up(self):
        NR_UP_ATTEMPTS = 10
        operstate = ""
        for _ in range(NR_UP_ATTEMPTS):
            operstate = self._device_attr('operstate')
            if operstate == 'up':
                return
            time.sleep(1)
        print "Gave up on waiting operstate up for device %s mac %s operstate %s" %\
                     (self.iface, self._device_attr('address'), operstate)

    def stat(self):
        address = self._device_attr('address')
        mtu = self._device_attr('mtu')
        operstate = self._device_attr('operstate')
        speed = self._device_attr('speed')
        carrier = self._device_attr('carrier')
        return {"address" : address,
                "mtu": mtu,
                "operstate" : operstate,
                "speed" : speed,
                "carrier" : carrier}

def list_devices_info():
    devices = os.listdir('/sys/class/net')
    interfaces = []
    devices_info = []
    for device in devices:
        # Dont gather stats on link local
        if device == 'lo':
            continue
        interfaces.append(NetworkInterface(device))

    # power up all network devices in parallel as it can takes
    # several seconds for each device to powerup
    print "Waiting for all interfaces to go up"
    for iface in interfaces:
        thread.start_new_thread(iface.ifup, ())

    # now wait all devices up and get stats
    for iface in interfaces:
        iface.wait_link_up()
        devices_info.append(iface.stat())

    return devices_info