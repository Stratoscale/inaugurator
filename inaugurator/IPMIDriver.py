import logging
from inaugurator import sh


class IPMIDriver():
    """
    IPMIDriver is a driver that able to configure through IPMI protocol
    """

    IPMI_KERNEL_MODULES = ["ipmi_msghandler", "ipmi_devintf", "ipmi_si"]

    def __init__(self):
        self.channel = 3

    def _loadModule(self, module):
        """
        load kernel module
        @param module: module name
        @type module: string
        """
        logging.debug("going to load kernel module for IPMI - module %s" % module)
        sh.run("modprobe %s" % module)
        logging.debug("Kernel module for IPMI load successfully- module %s" % module)

    def _removeModule(self, module):
        """
        remove/unload kernel module
        @param module: module name
        @type module: string
        """
        logging.debug("going to remove kernel module for IPMI - module %s" % module)
        sh.run("modprobe -r %s" % module)
        logging.debug("Kernel module for IPMI removed successfully- module %s" % module)

    def _verifyModuleLoaded(self, module):
        """
        verify kernel module is loaded. if not - raises exception.
        @param module: module name
        @type module: string
        @return: None - raise exception if kernel module not loaded
        """
        output = sh.run("lsmod | awk '{print $1}' | grep %s | wc -l" % module)

        if int(output) > 1:
            loadedModules = sh.run("lsmod | awk '{print $1}' | grep %s" % module)
            logging.info("more than one IPMI kernel module found for module %s and loaded modules are %s"
                         % (module, loadedModules))
        elif int(output) < 1:
            raise Exception("Cannot find kernel module for IPMI- module %s. all loaded IPMI modules are %s."
                            % (module, self._getAllLoadedIPMIModules()))

    def _getAllLoadedIPMIModules(self):
        """
        get all ipmi kernel modules loaded
        @return: ipmitool kernel modules names
        @rtype: list of strings
        """
        return sh.run("lsmod | grep ipmi | awk '{print $1}'").split('\n')

    def _loadAllModules(self):
        """
        load all ipmi kernel modules
        @return: None
        """
        for mod in self.IPMI_KERNEL_MODULES:
            self._loadModule(mod)

    def _removeAllModules(self):
        """
        remove/unload all ipmi kernel modules
        @return: None
        """
        for mod in reversed(self.IPMI_KERNEL_MODULES):
            self._removeModule(mod)

    def _verifyAllModulesLoaded(self):
        """
        verify all kernel modules loaded
        if not - raise Exception
        @return: None / raise Exception
        """
        for mod in self.IPMI_KERNEL_MODULES:
            self._verifyModuleLoaded(mod)

    def _createIPMIDevice(self):
        """
        create ipmitool device for communicate with ipmi device (for example - BMC)
        @return: None / raises Exception if device can't be created
        """
        logging.debug("going to create /dev/ipmi0 for ipmitool")
        ipmiMinorNodeID = sh.run("cat /proc/devices | grep ipmidev |cut -d \" \" -f 1").split('\n')[0]
        sh.run("mknod /dev/ipmi0 c %s 0" % ipmiMinorNodeID)

    def _verifyIPMITool(self):
        """
        verify ipmitool is avilable and can be used
        @return: None / raises Exception is ipmitool is not ready
        """
        logging.debug("going to verify ipmitool is working using ipmitool command")
        ipmiOutput = sh.run("ipmitool lan print 1")

        if ipmiOutput < 1:
            raise Exception("Cannot use ipmitool")

    def _setAvailableChannel(self, channel=None):
        """
        set IPMIDriver channel.
        if input is None, this function will discover an available channel.
        if got channel, verify this channcel can be used.
        discovery is tring to use channel 3 if available,
        if channel 3 isn't available fallback to channel 1.
        @param channel: channel to use / None
        @type channel: string
        @return: None / raise Exception if channel isn't available
        """
        if channel is None:
            # try to use channel 3 and fallback to 1
            try:
                logging.info("IPMI channel not provided, will assign channel automatically")
                sh.run("ipmitool lan print 3 1>/dev/null 2>/dev/null")
                self.channel = 3
            except Exception:
                self.channel = 1
        else:
            logging.info("IPMI channel provided, channel - %s" % channel)
            sh.run("ipmitool lan print %s" % channel)
            self.channel = channel

        logging.info("IPMI channel assigned - %s" % self.channel)

    def _getUsernameID(self, username):
        """
        get user ID by user name
        @param username: user name
        @type username:string
        @return: user id / None if user name not found
        @rtype: string
        """
        try:
            userid = sh.run("ipmitool user list %s | grep %s" % (self.channel, username)).split(' ')[0]
            return userid
        except Exception:
            return None

    def _changePassword(self, userid, username, password):
        """
        change user password on ipmi user table
        @param userid: user id
        @type userid: string
        @param username: user name
        @type username: string
        @param password: password
        @type password: string
        @return: None
        """
        logging.info("IPMI - going to change password for user - %s id - %s"
                     % (username, userid))
        sh.run("ipmitool user set password %s %s" % (userid, password))
        logging.info("IPMI - password changed successfully for user - %s" % username)

    def _getFreeUserID(self):
        """
        get free user ID from ipmi user table
        @return: free user id / raise Exception if no user available
        @rtype: string
        """
        users_output = sh.run("ipmitool user list 1")

        # remove space from output
        users_output = users_output.replace("NO ACCESS", "NO-ACCESS")
        users_output = users_output.replace("No Access", "NO-ACCESS")
        users_output = users_output.replace("OEM Proprietary", "OEM-PRORPIETARY")
        users_output = users_output.replace("OEM-PRORPIETARY", "OEM-PRORPIETARY")
        users_output = users_output.replace("Unknown (0x00)", "UNKNOWN-(0x00)")
        users_output = users_output.replace("UNKNOWN (0x00)", "UNKNOWN-(0x00)")

        # format user records
        users_unformated = users_output.split('\n')
        users_unformated = users_unformated[1:-1]
        usersList = []

        for user_raw_record in users_unformated:
            user_formatted_record = " ".join(user_raw_record.split()).split(" ")
            usersList.append(user_formatted_record)

        # get max list property
        maxProps = 0
        for usr in usersList:
            if len(usr) > maxProps:
                maxProps = len(usr)

        # find user with no name property
        for usr in reversed(usersList):
            if len(usr) < maxProps:
                return usr[0]

        raise Exception("IPMI - can't find free user ID to create a new user")

    def _createNewUser(self, username, password):
        """
        create new user on ipmi user table
        @param username: user name
        @type username: string
        @param password: password
        @type password: string
        @return: None
        """
        logging.info("IPMI - going to create user as administrator, username: %s" % username)
        userid = self._getFreeUserID()
        sh.run("ipmitool user set name %s %s" % (userid, username))
        sh.run("ipmitool user set password %s %s" % (userid, password))
        sh.run("ipmitool user priv %s 4 %s" % (userid, self.channel))
        sh.run("ipmitool channel setaccess %s %s callin=off ipmi=on link=on privilege=4" %
               (self.channel, userid))
        sh.run("ipmitool user enable %s" % userid)
        logging.info("IPMI - user created successfully, username: %s" % username)

    def setupIPMIDriver(self, channel=None):
        """
        setup IPMIDriver and verify it can be work properly
        @param channel: channel to use
        @type channel: string
        @return: None
        """
        logging.info("Setting up IPMI driver")
        self._removeAllModules()
        self._loadAllModules()
        self._verifyAllModulesLoaded()
        self._createIPMIDevice()
        self._verifyIPMITool()
        self._setAvailableChannel(channel)
        logging.info("IPMI driver setup done")

    def configureIPMIUsernameANDPassword(self, username, password):
        """
        configure user on ipmi user table.
        if user already exist - change password
        if user not exist - create a new user
        @param username: user name
        @type username: string
        @param password: password
        @type password: string
        """
        userid = self._getUsernameID(username)

        if userid is None:
            self._createNewUser(username, password)
        else:
            self._changePassword(userid, username, password)

    def configureIPMINetwork(self, ip, netmask, gateway):
        """
        configure ipmi networking
        @param ip: ip address
        @type ip: string
        @param netmask: netmask
        @type netmask: string
        @param gateway: default gateway
        @type gateway: string
        @return: None
        """
        logging.info("IPMI going to set network configuration on channel %s,"
                     " ip address: %s, netmask: %s, default gateway: %s" %
                     (self.channel, ip, netmask, gateway))
        sh.run("ipmitool lan set %s ipsrc static" % self.channel)
        sh.run("ipmitool lan set %s ipaddr %s" % (self.channel, ip))
        sh.run("ipmitool lan set %s netmask %s" % (self.channel, netmask))
        sh.run("ipmitool lan set %s defgw ipaddr %s" % (self.channel, gateway))
        sh.run("ipmitool lan set %s access on" % self.channel)
        logging.info("IPMI network configuration done successfully")

    def restartIPMI(self):
        """
        restart ipmi
        @return: None
        """
        logging.info("IPMI - restarting IPMI management controller using cold mode")
        sh.run("ipmitool mc reset cold")
