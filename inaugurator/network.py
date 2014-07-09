import re
from inaugurator import sh


class Network:
    _CONFIG_SCRIPT_PATH = "/etc/udhcp_script.sh"

    def __init__(self, macAddress, ipAddress, netmask, gateway):
        interfacesTable = self._interfacesTable()
        assert macAddress.lower() in interfacesTable
        interfaceName = interfacesTable[macAddress.lower()]
        sh.run("/usr/sbin/ifconfig %s %s netmask %s" % (interfaceName, ipAddress, netmask))
        sh.run("busybox route add default gw %s" % gateway)

    def _interfacesTable(self):
        REGEX = re.compile(r'\d+:\s+([^:]+):\s+.*\s+link/ether\s+((?:[a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2})')
        ipOutput = sh.run("/usr/sbin/ip -o link")
        return {mac.lower(): interface for interface, mac in REGEX.findall(ipOutput)}
