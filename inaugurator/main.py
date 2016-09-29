from inaugurator import ceremony
import argparse
import traceback
import pdb
import logging
import sys
from inaugurator import packagesvalidation


logging.basicConfig(level=logging.DEBUG, stream=sys.stdout,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('pika').setLevel(logging.INFO)
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
parser.add_argument("--inauguratorTargetDeviceCandidate", nargs='+', default=['/dev/vda', '/dev/sda'])
parser.add_argument("--inauguratorTargetDeviceType")
parser.add_argument("--inauguratorVerify", action="store_true")
parser.add_argument("--inauguratorDisableNCQ", action="store_true", default=True)
parser.add_argument("--inauguratorLogfilePath")
parser.add_argument("--inauguratorExpectedLabel")
parser.add_argument("--inauguratorSkipPdbOnError", action="store_true", default=False)
parser.add_argument("--inauguratorPartitionLayout", default="GPT")
parser.add_argument("--inauguratorRootPartitionSizeGB", type=int, default=20)
parser.add_argument("--inauguratorDontReadSmartData", action="store_true", default=False)


def getArgsSource():
    parser = argparse.ArgumentParser(add_help=False)
    choices = ["kernelCmdline", "processArguments"]
    parser.add_argument("--inauguratorArgumentsSource", default="kernelCmdline", choices=choices)
    args = parser.parse_known_args()[0]
    return args.inauguratorArgumentsSource


def main():
    # Earlier versions of pika are buggy
    packagesvalidation.validateMinimumVersions(pika="0.10.0")
    argsSource = getArgsSource()
    if argsSource == "kernelCmdline":
        print "Reading arguments from kernel command line..."
        cmdLine = open("/proc/cmdline").read().strip()
        args = parser.parse_known_args(cmdLine.split(' '))[0]
    elif argsSource == "processArguments":
        print "Reading arguments from process command line..."
        args = parser.parse_known_args()[0]
    else:
        assert False, argsSource
    if args.inauguratorSkipPdbOnError:
        global PDB_ON_ERROR
        PDB_ON_ERROR = False
    ceremonyInstance = ceremony.Ceremony(args)
    for stage in args.inauguratorStages.split(","):
        print "Inaugurator stage: '%s'" % (stage,)
        if stage == "ceremony":
            ceremonyInstance.ceremony()
        elif stage == "kexec":
            ceremonyInstance.kexec()
        elif stage == "reboot":
            ceremonyInstance.reboot()
        else:
            raise Exception("Invalid stage: '%s'" % (stage,))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print "Inaugurator raised exception: "
        traceback.print_exc(e)
        if not PDB_ON_ERROR:
            print "For PDB on error, don't use --inauguratorSkipPdbOnError."
        raise e
    finally:
        if PDB_ON_ERROR:
            pdb.set_trace()
