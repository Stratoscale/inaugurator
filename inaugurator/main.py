from inaugurator import ceremony
import argparse
import traceback
import rpdb
import logging
import sys
from inaugurator import packagesvalidation
from inaugurator import log
from inaugurator import consts

PDB_ON_ERROR = True

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--inauguratorStages", default="ceremony,kexec")
parser.add_argument("--inauguratorClearDisk", action="store_true")
parser.add_argument("--inauguratorSource", required=True)
parser.add_argument("--inauguratorServerAMQPURL")
parser.add_argument("--inauguratorMyIDForServer")
parser.add_argument("--inauguratorNetworkLabel")
parser.add_argument("--inauguratorOsmosisObjectStores")
parser.add_argument("--inauguratorIsNetworkAlreadyConfigured", action="store_true", default=False)
parser.add_argument("--inauguratorUseNICWithMAC")
parser.add_argument("--inauguratorIPAddress")
parser.add_argument("--inauguratorNetmask")
parser.add_argument("--inauguratorGateway")
parser.add_argument("--inauguratorChangeRootPassword")
parser.add_argument("--inauguratorWithLocalObjectStore", action="store_true")
parser.add_argument("--inauguratorNoChainTouch", action="store_true", default=False)
parser.add_argument("--inauguratorPassthrough", default="")
parser.add_argument("--inauguratorDownload", nargs='+', default=[])
parser.add_argument("--inauguratorIgnoreDirs", nargs='+', default=[])
parser.add_argument("--inauguratorVerify", action="store_true")
parser.add_argument("--inauguratorDisableNCQ", action="store_true", default=True)
parser.add_argument("--inauguratorExpectedLabel")
parser.add_argument("--inauguratorSkipPdbOnError", action="store_true", default=False)
parser.add_argument("--inauguratorPartitionLayout", default="GPT")
parser.add_argument("--inauguratorRootPartitionSizeGB", type=int, default=20)
parser.add_argument("--inauguratorBootPartitionSizeMB", type=int, default=512)
parser.add_argument("--inauguratorDontReadSmartData", action="store_true", default=False)
parser.add_argument("--inauguratorDontFailOnFailedDisk", action="store_true", default=False)
parser.add_argument("--inauguratorCleanupUpperPercentageThreshold", type=int, default=65)
parser.add_argument("--inauguratorWipeOldInauguratorInstallations", action="store_true", default=False)
parser.add_argument("--inauguratorWipeOsmosisObjectStoreIfNeeded", action="store_true", default=False)
parser.add_argument("--inauguratorExtraDataToGrubCmdLine", type=str, default="")
parser.add_argument("--inauguratorTargetDeviceCandidate", nargs='+',
                    help="This parameter is mutually exclusive with inauguratorTargetDeviceLabel "
                         "and inauguratorTargetDeviceType")
parser.add_argument("--inauguratorTargetDeviceLabel", help="This parameter is mutually exclusive "
                    "with inauguratorTargetDeviceCandidate and inauguratorTargetDeviceType")
parser.add_argument("--inauguratorTargetDeviceType", help="This parameter is mutually exclusive "
                    "with inauguratorTargetDeviceCandidate and inauguratorTargetDeviceLabel")
parser.add_argument("--inauguratorIPMIUsername")
parser.add_argument("--inauguratorIPMIPassword")
parser.add_argument("--inauguratorIPMIAddress")
parser.add_argument("--inauguratorIPMINetmask")
parser.add_argument("--inauguratorIPMIGateway")
parser.add_argument("--inauguratorIPMIChannel")
parser.add_argument("--inauguratorIPMIRestart")


def getArgsSource():
    parser = argparse.ArgumentParser(add_help=False)
    choices = ["kernelCmdline", "processArguments"]
    parser.add_argument("--inauguratorArgumentsSource", default="kernelCmdline", choices=choices)
    args = parser.parse_known_args()[0]
    return args.inauguratorArgumentsSource


def main():
    log.addStdoutHandler()
    log.addFileHandler(consts.INAUGURATOR_RAM_LOG_FILE_NAME)
    # Earlier versions of pika are buggy
    packagesvalidation.validateMinimumVersions(pika="0.10.0")
    argsSource = getArgsSource()
    if argsSource == "kernelCmdline":
        logging.info("Reading arguments from kernel command line...")
        cmdLine = open("/proc/cmdline").read().strip()
        args = parser.parse_known_args(cmdLine.split(' '))[0]
    elif argsSource == "processArguments":
        logging.info("Reading arguments from process command line...")
        args = parser.parse_known_args()[0]
    else:
        assert False, argsSource
    if args.inauguratorSkipPdbOnError:
        global PDB_ON_ERROR
        PDB_ON_ERROR = False

    ceremonyInstance = ceremony.Ceremony(args)
    for stage in args.inauguratorStages.split(","):
        logging.info("Inaugurator stage: '%s'" % (stage,))
        if stage == "ceremony":
            ceremonyInstance.ceremony()
        elif stage == "kexec":
            ceremonyInstance.kexec()
        elif stage == "reboot":
            ceremonyInstance.reboot()
        elif stage == "shutdown":
            ceremonyInstance.shutdown()
        else:
            raise Exception("Invalid stage: '%s'" % (stage,))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.info("Inaugurator raised exception: ")
        traceback.print_exc(e)
        if not PDB_ON_ERROR:
            logging.info("For PDB on error, don't use --inauguratorSkipPdbOnError.")
        raise e
    finally:
        if PDB_ON_ERROR:
            rpdb.set_trace()
