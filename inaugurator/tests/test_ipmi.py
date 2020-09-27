import os
import sys
import mock
import logging
import unittest
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
        pass

    def test_IPMIControllerCreation(self):
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
        testDriver = self._getDummyIPMIDriver()

        # needed
        ipmi_all = IPMIController(testDriver, self.testUsername, self.testPass, self.testIP,
                                  self.testNetmask, self.testGW, self.testChannel, self.testRestart)
        self.assertEqual(ipmi_all._checkIfIPMIConfigurationNeeded(), True)

        # not needed
        ipmi_miss_all = IPMIController()
        self.assertEqual(ipmi_miss_all._checkIfIPMIConfigurationNeeded(), False)

    def test_kernelConfigureIPMI(self):

        # username and password only - do nothing
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

        # channel and restart - do nothing
        ipmi_some = IPMIController(channel=2)
        ipmi_some.configureIPMI()

    def test_kernelModules(self):
        ipmi_driver = IPMIDriver()
        ipmi_driver.IPMI_KERNEL_MODULES = ["ipmi_msghandler", "ipmi_devintf"]

        try:
            ipmi_driver._removeAllModules()
            # self.assertRaises(Exception, ipmi_driver._verifyAllModulesLoaded)
            # ipmi_driver._loadAllModules()
            # ipmi_driver._verifyAllModulesLoaded()
        except Exception as e:
            self.fail("loading drivers errors, Exception: %s" % str(e))

    def _getDummyIPMIDriver(self):

        class DummyIPMIDriver():
            def __init__(self):
                pass

        return DummyIPMIDriver()
