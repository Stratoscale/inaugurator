import re
import logging
from inaugurator import sh


class Network:
    _CONFIG_SCRIPT_PATH = "/etc/udhcp_script.sh"
    _NR_PING_ATTEMPTS = 20

    def __init__(self, macAddress, ipAddress, netmask, gateway):
        self._gateway = gateway
        interfacesTable = self._interfacesTable()
        assert macAddress.lower() in interfacesTable
        interfaceName = interfacesTable[macAddress.lower()]
        sh.run("/usr/sbin/ifconfig %s %s netmask %s" % (interfaceName, ipAddress, netmask))
        sh.run("busybox route add default gw %s" % self._gateway)
        self._validateLinkIsUp()

    def _validateLinkIsUp(self):
        logging.info("Waiting for the connection to actually be up by pinging %s..." % (self._gateway,))
        linkIsUp = False
        for attemptIdx in xrange(self._NR_PING_ATTEMPTS):
            attemptNr = attemptIdx + 1
            try:
                result = sh.run("busybox ping -w 1 -c 1 %s" % (self._gateway,))
                linkIsUp = True
                logging.info("Ping attempt #%d succeeded." % (attemptNr,))
                break
            except:
                logging.info("Ping attempt #%d failed." % (attemptNr,))
        if not linkIsUp:
            raise Exception("No response from %s when trying to test if link was up" % (self._gateway,))

    def _interfacesTable(self):
        REGEX = re.compile(r'\d+:\s+([^:]+):\s+.*\s+link/ether\s+((?:[a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2})')
        ipOutput = sh.run("/usr/sbin/ip -o link")
        return {mac.lower(): interface for interface, mac in REGEX.findall(ipOutput)}
