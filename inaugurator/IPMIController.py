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
        """
        IPMIController initializer
        @param ipmidriver: ipmi driver
        @type ipmidriver: IPMIDriver
        @param username: user name
        @type username: string
        @param password: password
        @type password: string
        @param ipAddress: ip address for ipmi network configuration
        @type ipAddress: string
        @param netmask: netmask
        @type netmask: netmask for ipmi network configuration
        @param gateway: string
        @type gateway: default gateway for ipmi network configuration
        @param channel: ipmi channel to use
        @type channel: string
        @param restart: if to restart ipmi after configuration
        @type restart: string
        """
        self.ipmidriver = ipmidriver if ipmidriver is not None else IPMIDriver.IPMIDriver()
        self.username = username
        self.password = password
        self.ip = ipAddress
        self.netmask = netmask
        self.gateway = gateway
        self.channel = channel
        self.restart = self._convertStringToBool(restart)

    def _checkIfIPMIConfigurationNeeded(self):
        """
        check if any ipmi configuration needed
        @return: True / False
        @rtype: boolean
        """
        if any([self.username, self.password, self.ip, self.netmask, self.gateway]):
            return True
        else:
            return False

    def configureIPMIIfNeeded(self):
        """
        Configure IPMI if needed
        @return: None
        """
        if self._checkIfIPMIConfigurationNeeded():
            logging.info("Got IPMI Parameters, configuring IPMI")
            self.ipmidriver.setupIPMIDriver(self.channel)
            self.configureIPMI()
        else:
            logging.info("IPMI paramaters not found, skip IPMI configuration")

    def configureIPMI(self):
        """
        configure IPMI username & password and networking, restart ipmi if told so
        @return: None
        """
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
        """
        convert bool string to boolean
        @param str: string to convert
        @type str: string
        @return: True / False
        @rtype: boolean
        """
        if str is None:
            return False
        if str in ["True", "true"]:
            return True
        else:
            return False
