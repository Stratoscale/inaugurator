import logging
from inaugurator import IPMIDriver


class IPMIController():

    def __init__(self,
                 ipmidriver=None,
                 username=None,
                 password=None,
                 ipAddress=None,
                 netmask=None,
                 gateway=None,
                 channel=None,
                 restart=None):
        self.ipmidriver = ipmidriver if ipmidriver is not None else IPMIDriver.IPMIDriver()
        self.username = username
        self.password = password
        self.ip = ipAddress
        self.netmask = netmask
        self.gateway = gateway
        self.channel = channel
        self.restart = self._convertStringToBool(restart)

    def _checkIfIPMIConfigurationNeeded(self):
        if any([self.username, self.password, self.ip, self.netmask, self.gateway]):
            return True
        else:
            return False

    def configureIPMIIfNeeded(self):
        if self._checkIfIPMIConfigurationNeeded():
            logging.info("Got IPMI Parameters, configuring IPMI")
            self.setupIPMIDriver()
            self.configureIPMI()
        else:
            logging.info("IPMI paramaters not found, skip IPMI configuration")

    def setupIPMIDriver(self):
        self.ipmidriver.setupIPMIDriver(self.channel)

    def configureIPMI(self):
        if self.username is not None and self.password is not None:
            self.ipmidriver.configureIPMIUsernameANDPassword(self.username, self.password)
        else:
            logging.info("IPMI parameters [username, password] - at least one of them not provided."
                         " Parameter found - username: %s password found (True/False): "
                         "%s . Skip configuration." %
                         (self.username, True if self.password is not None else False))

        if self.ip is not None and self.netmask is not None and self.gateway is not None:
            self.ipmidriver.configureIPMINetwork(self.ip, self.netmask, self.gateway)
        else:
            logging.info("IPMI parameters [ip, netmask, gateway] - at least one of them not provided."
                         " Parameters found - ip: %s netmask: %s gateway: %s . Skip configuration"
                         % (self.ip, self.netmask, self.gateway))

        if self.restart:
            self.ipmidriver.restartIPMI()

    def _convertStringToBool(self, str):
        if str is None:
            return False
        if str in ["True", "true"]:
            return True
        else:
            return False
