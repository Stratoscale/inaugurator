import os
import sys
import mock
import logging
import unittest
import inaugurator
from inaugurator.tests.mock_sh import mock_sh
from inaugurator import sh
from inaugurator.IPMIDriver import IPMIDriver
from inaugurator.IPMIController import IPMIController


class Test(unittest.TestCase):
    testUsername = "user"
    testPass = "password"
    testIP = "10.0.0.10"
    testNetmask = "255.255.255.0"
    testGW = "10.0.0.1"
    testChannel = 2
    testRestart = "False"

    def setUp(self):
        """
        set up unit test base function
        @return: None
        @rtype: None
        """
        self.mock_sh = mock_sh()
        sh.run = self.mock_sh.runShell

    def tearDown(self):
        """
        tear down this unit test
        @return: None
        @rtype: None
        """
        sh.run = inaugurator.sh.run

    def test_IPMIControllerCreation(self):
        """
        test creation of IPMIController instances
        @return: None
        @rtype: None
        """
        testDriver = self._getDummyIPMIDriver()

        ipmi_all = IPMIController(testDriver, self.testUsername, self.testPass, self.testIP,
                                  self.testNetmask, self.testGW, self.testChannel, self.testRestart)
        self.assertNotEqual(ipmi_all.ipmidriver, None)
        self.assertEqual(ipmi_all.username, self.testUsername)
        self.assertEqual(ipmi_all.password, self.testPass)
        self.assertEqual(ipmi_all.ip, self.testIP)
        self.assertEqual(ipmi_all.netmask, self.testNetmask)
        self.assertEqual(ipmi_all.gateway, self.testGW)
        self.assertEqual(ipmi_all.channel, self.testChannel)
        self.assertEqual(str(ipmi_all.restart), self.testRestart)

        ipmi_miss_all = IPMIController()
        self.assertNotEqual(ipmi_miss_all.ipmidriver, None)
        self.assertEqual(ipmi_miss_all.username, None)
        self.assertEqual(ipmi_miss_all.password, None)
        self.assertEqual(ipmi_miss_all.ip, None)
        self.assertEqual(ipmi_miss_all.netmask, None)
        self.assertEqual(ipmi_miss_all.gateway, None)
        self.assertEqual(ipmi_miss_all.channel, None)
        self.assertEqual(ipmi_miss_all.restart, False)

        ipmi_some = IPMIController(username=self.testUsername, ipAddress=self.testIP,
                                   gateway=self.testGW, channel=self.testChannel)
        self.assertNotEqual(ipmi_some.ipmidriver, None)
        self.assertEqual(ipmi_some.username, self.testUsername)
        self.assertEqual(ipmi_some.password, None)
        self.assertEqual(ipmi_some.ip, self.testIP)
        self.assertEqual(ipmi_some.netmask, None)
        self.assertEqual(ipmi_some.gateway, self.testGW)
        self.assertEqual(ipmi_some.channel, self.testChannel)
        self.assertEqual(ipmi_some.restart, False)

    def test_ConfigurationNeeded(self):
        """
        test the function which check if IPMI configuration needed in this session
        @return: None
        @rtype: None
        """
        testDriver = self._getDummyIPMIDriver()

        # configuration needed
        ipmi_all = IPMIController(testDriver, self.testUsername, self.testPass, self.testIP,
                                  self.testNetmask, self.testGW, self.testChannel, self.testRestart)
        self.assertEqual(ipmi_all._checkIfIPMIConfigurationNeeded(), True)

        # configuration not needed
        ipmi_miss_all = IPMIController()
        self.assertEqual(ipmi_miss_all._checkIfIPMIConfigurationNeeded(), False)

    def test_configurationRestart(self):
        """
        test that configuration restart is doing the expected commands
        @return: None
        @rtype: None
        """
        ipmi_some = IPMIController(restart="True")
        cmds = [{"command": "ipmitool mc reset cold", "result": None}]
        self.mock_sh.setCommands(cmds)
        ipmi_some.configureIPMI()

    def test_kernelConfigureIPMIDoNothing(self):
        """
        test that each subset of values is not doing any configuration, as expected
        @return: None
        @rtype: None
        """
        # username or password only - do nothing
        ipmi_some = IPMIController(username=self.testUsername)
        ipmi_some.configureIPMI()

        ipmi_some = IPMIController(password=self.testPass)
        ipmi_some.configureIPMI()

        # ip, netmask and gw only, not all of them - do nothing
        ipmi_some = IPMIController(ipAddress=self.testIP)
        ipmi_some.configureIPMI()
        ipmi_some = IPMIController(netmask=self.testNetmask)
        ipmi_some.configureIPMI()
        ipmi_some = IPMIController(netmask=self.testGW)
        ipmi_some.configureIPMI()

        ipmi_some = IPMIController(ipAddress=self.testIP, netmask=self.testNetmask)
        ipmi_some.configureIPMI()
        ipmi_some = IPMIController(ipAddress=self.testIP, gateway=self.testGW)
        ipmi_some.configureIPMI()
        ipmi_some = IPMIController(netmask=self.testNetmask, gateway=self.testGW)
        ipmi_some.configureIPMI()

        # channel - do nothing
        ipmi_some = IPMIController(channel=2)
        ipmi_some.configureIPMI()

    def test_kernelRemoveModules(self):
        """
        test the remove kernel modules commands
        @return: None
        @rtype: None
        """
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "modprobe -r " + mod, "result": None} for mod in ipmi_driver.IPMI_KERNEL_MODULES]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._removeAllModules()

    def test_kernelAddModules(self):
        """
        test the load kernel modules commands
        @return: None
        @rtype: None
        """
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "modprobe " + mod, "result": None} for mod in ipmi_driver.IPMI_KERNEL_MODULES]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._loadAllModules()

    def test_kernelVerifyModules(self):
        """
        test verify kernel module commands
        @return: None
        @rtype: None
        """
        ipmi_driver = IPMIDriver()
        cmds = [
            {"command": "lsmod | awk '{print $1}' | grep ipmi_msghandler | wc -l", "result": 1},
            {"command": "lsmod | awk '{print $1}' | grep ipmi_devintf | wc -l", "result": 1},
            {"command": "lsmod | awk '{print $1}' | grep ipmi_si | wc -l", "result": 1}
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._verifyAllModulesLoaded()

    def test_IPMICreateDevice(self):
        """
        test IPMI device creation commands for using ipmi tool
        @return: None
        @rtype: None
        """
        ipmi_dev_num = 500
        ipmi_driver = IPMIDriver()
        cmds = [
            {"command": "cat /proc/devices | grep ipmidev |cut -d \" \" -f 1",
             "result": "%s" % ipmi_dev_num},
            {"command": "mknod /dev/ipmi0 c %s 0" % ipmi_dev_num, "result": None},
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._createIPMIDevice()

    def test_IPMITestipmitoolHappyFlow(self):
        """
        test ipmitool basic usage - success flow
        @return: None
        @rtype: None
        """
        channel = 1
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool lan print %s" % channel, "result": "OK"}]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._verifyIPMITool()

    def test_IPMITestipmitoolBadFlow(self):
        """
        test ipmitool basic usage - failure flow
        @return: None
        @rtype: None
        """
        channel = 1
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool lan print %s" % channel, "result": Exception()}]
        self.mock_sh.setCommands(cmds)
        self.assertRaises(Exception, ipmi_driver._verifyIPMITool)

    def test_setAvilableChannelDiscoveryChannel3(self):
        """
        test the channel discovery, channel 3 available on machine
        @return: None
        @rtype: None
        """
        channel = 3
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool lan print %s 1>/dev/null 2>/dev/null" % channel, "result": "OK"}]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(None)
        self.assertEqual(3, ipmi_driver.channel)

    def test_setAvilableChannelDiscoveryChannel1(self):
        """
        test the channel discovery, channel 1 only available on machine
        @return: None
        @rtype: None
        """
        wrong_channel = 3
        right_channel = 1
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool lan print %s 1>/dev/null 2>/dev/null" % wrong_channel,
                 "result": Exception()}]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(None)
        self.assertEqual(right_channel, ipmi_driver.channel)

    def test_setAvilableChannelUserSelectionChannel(self):
        """
        test the channel discovery, user choose each channel
        @return: None
        @rtype: None
        """
        for channel in [1, 2, 3]:
            ipmi_driver = IPMIDriver()
            cmds = [{"command": "ipmitool lan print %s" % channel, "result": None}]
            self.mock_sh.setCommands(cmds)
            ipmi_driver._setAvailableChannel(channel)
            self.assertEqual(channel, ipmi_driver.channel)

    def test_getUserID_UserFound(self):
        """
        test get user ID from ipmitool user tables
        @return: None
        @rtype: None
        """
        user = "USER"
        channel = 1
        userid = "100"
        ipmi_driver = IPMIDriver()
        cmds = [
            {"command": "ipmitool lan print %s" % channel, "result": None},
            {"command": "ipmitool user list %s | grep %s" % (channel, user), "result": userid}
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(channel)
        self.assertEqual(ipmi_driver._getUsernameID(user), userid)

    def test_getUserID_UserNotFound(self):
        """
        test get user ID from ipmitool user tables
        @return: None
        @rtype: None
        """
        user = "USER"
        channel = 1
        userid = 100
        ipmi_driver = IPMIDriver()
        cmds = [
            {"command": "ipmitool user list %s | grep %s" % (user, channel), "result": Exception()},
            {"command": "ipmitool lan print %s" % channel, "result": None}
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(channel)
        self.assertEqual(ipmi_driver._getUsernameID(user), None)

    def test_changePassword(self):
        """
        test change user password with ipmitool
        @return: None
        @rtype: None
        """
        user = "USER"
        password = "abc123"
        userid = 100
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool user set password %s %s" % (userid, password), "result": None}]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._changePassword(userid, user, password)

    def test_configureIPMINetwork(self):
        """
        test change network configuration by user
        @return: None
        @rtype: None
        """
        ip = "10.0.0.20"
        netmask = "255.255.255.0"
        gw = "10.0.0.1"
        channel = 1
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool lan print %s" % channel, "result": None}]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(channel)
        cmds = [
            {"command": "ipmitool lan print %s" % channel, "result": None},
            {"command": "ipmitool lan set %s ipsrc static" % (channel), "result": None},
            {"command": "ipmitool lan set %s ipaddr %s" % (channel, ip), "result": None},
            {"command": "ipmitool lan set %s netmask %s" % (channel, netmask), "result": None},
            {"command": "ipmitool lan set %s defgw ipaddr %s" % (channel, gw), "result": None},
            {"command": "ipmitool lan set %s access on" % channel, "result": None},
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver.configureIPMINetwork(ip, netmask, gw)

    def test_getFreeUserIDIntel(self):
        """
        test get free user ID from intel server
        @return: None
        @rtype: None
        """
        channel = 1
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool user list %s" % channel,
                 "result": self._getIPMIUserListIntelServer()}]
        self.mock_sh.setCommands(cmds)
        self.assertNotEqual(2, ipmi_driver._getFreeUserID())

    def test_getFreeUserIDSupermicro(self):
        """
        test get free user ID from Supermicro server
        @return: None
        @rtype: None
        """
        channel = 1
        ipmi_driver = IPMIDriver()
        cmds = [{"command": "ipmitool user list %s" % channel,
                 "result": self._getIPMIUserListSuperMicroServer()} for _ in range(3)]
        self.mock_sh.setCommands(cmds)
        self.assertNotEqual(2, ipmi_driver._getFreeUserID())
        self.assertNotEqual(3, ipmi_driver._getFreeUserID())
        self.assertNotEqual(4, ipmi_driver._getFreeUserID())

    def test_CreateNewUserIntelServer(self):
        """
        test get create user in Intel server
        @return:
        @rtype:
        """
        channel = 1
        userid = 15
        username = "USER1"
        password = "password"
        ipmi_driver = IPMIDriver()
        cmds = [
            {"command": "ipmitool lan print %s" % channel, "result": None},
            {"command": "ipmitool user list %s" % channel, "result": self._getIPMIUserListIntelServer()},
            {"command": "ipmitool user set name %s %s" % (userid, username), "result": None},
            {"command": "ipmitool user set password %s %s" % (userid, password), "result": None},
            {"command": "ipmitool user priv %s 4 %s" % (userid, channel), "result": None},
            {"command": "ipmitool channel setaccess %s %s callin=off ipmi=on link=on privilege=4" %
                        (channel, userid), "result": None},
            {"command": "ipmitool user enable %s" % userid, "result": None}
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(channel)
        ipmi_driver._createNewUser(username, password)

    def test_CreateNewUserSupermicroServer(self):
        """
        test get create user in Supermicro server
        @return:
        @rtype:
        """
        channel = 1
        username = "USER1"
        password = "password"
        userid = 10
        ipmi_driver = IPMIDriver()
        cmds = [
            {"command": "ipmitool lan print %s" % channel, "result": None},
            {"command": "ipmitool user list %s" % channel,
             "result": self._getIPMIUserListSuperMicroServer()},
            {"command": "ipmitool user set name %s %s" % (userid, username), "result": None},
            {"command": "ipmitool user set password %s %s" % (userid, password), "result": None},
            {"command": "ipmitool user priv %s 4 %s" % (userid, channel), "result": None},
            {"command": "ipmitool channel setaccess %s %s callin=off ipmi=on link=on privilege=4" %
                        (channel, userid), "result": None},
            {"command": "ipmitool user enable %s" % userid, "result": None}
        ]
        self.mock_sh.setCommands(cmds)
        ipmi_driver._setAvailableChannel(channel)
        ipmi_driver._createNewUser(username, password)

    def _getIPMIUserListIntelServer(self):
        """
        Get user list from ipmitool on a intel server
        @return: IPMI users table
        @rtype: string
        """
        output = "ID  Name	     Callin  Link Auth	IPMI Msg   Channel Priv Limit\n" \
                 "1                    false   false      true       ADMINISTRATOR\n" \
                 "2   root             false   true       true       ADMINISTRATOR\n" \
                 "3                    false   false      true       NO ACCESS\n" \
                 "4                    false   false      true       NO ACCESS\n" \
                 "5                    false   false      true       NO ACCESS\n" \
                 "6                    true    false      false      NO ACCESS\n" \
                 "7                    true    false      false      NO ACCESS\n" \
                 "8                    true    false      false      NO ACCESS\n" \
                 "9                    true    false      false      NO ACCESS\n" \
                 "10                   true    false      false      NO ACCESS\n" \
                 "11                   true    false      false      NO ACCESS\n" \
                 "12                   true    false      false      NO ACCESS\n" \
                 "13                   true    false      false      NO ACCESS\n" \
                 "14                   true    false      false      NO ACCESS\n" \
                 "15                   true    false      false      NO ACCESS\n"
        return output

    def _getIPMIUserListSuperMicroServer(self):
        """
        Get user list from ipmitool on a Supermicro server
        @return: IPMI users table
        @rtype: string
        """
        output = "ID  Name	     Callin  Link Auth	IPMI Msg   Channel Priv Limit\n" \
                 "1                    true    false      false      Unknown (0x00)\n" \
                 "2   ADMIN            false   false      true       ADMINISTRATOR\n" \
                 "3   root             true    false      true       ADMINISTRATOR\n" \
                 "4   test_guy         true    false      true       ADMINISTRATOR\n" \
                 "5                    true    false      false      Unknown (0x00)\n" \
                 "6                    true    false      false      Unknown (0x00)\n" \
                 "7                    true    false      false      Unknown (0x00)\n" \
                 "8                    true    false      false      Unknown (0x00)\n" \
                 "9                    true    false      false      Unknown (0x00)\n" \
                 "10                   true    false      false      Unknown (0x00)\n"
        return output

    def _getDummyIPMIDriver(self):
        """
        get dummy IPMI driver
        @return: obj
        @rtype: IPMIDriver
        """
        class DummyIPMIDriver():
            def __init__(self):
                pass

        return DummyIPMIDriver()
