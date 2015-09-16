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


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--inauguratorClearDisk", action="store_true")
parser.add_argument("--inauguratorSource", required=True)
parser.add_argument("--inauguratorServerAMQPURL")
parser.add_argument("--inauguratorMyIDForServer")
parser.add_argument("--inauguratorNetworkLabel")
parser.add_argument("--inauguratorOsmosisObjectStores")
parser.add_argument("--inauguratorUseNICWithMAC")
parser.add_argument("--inauguratorIPAddress")
parser.add_argument("--inauguratorNetmask")
parser.add_argument("--inauguratorGateway")
parser.add_argument("--inauguratorChangeRootPassword")
parser.add_argument("--inauguratorWithLocalObjectStore", action="store_true")
parser.add_argument("--inauguratorPassthrough", default="")
parser.add_argument("--inauguratorDownload", nargs='+', default=[])
parser.add_argument("--inauguratorIgnoreDirs", nargs='+', default=[])
parser.add_argument("--inauguratorTargetDeviceCandidate", nargs='+', default=['/dev/vda', '/dev/sda'])
parser.add_argument("--inauguratorVerify", action="store_true")

try:
    print "Validating pika version..."
    # Earlier versions of pika are buggy
    packagesvalidation.validateMinimumVersions(pika="0.10.0")
    print "Pika version is valid."
    cmdLine = open("/proc/cmdline").read().strip()
    args = parser.parse_known_args(cmdLine.split(' '))[0]
    ceremonyInstance = ceremony.Ceremony(args)
    ceremonyInstance.ceremony()
except Exception as e:
    print "Inaugurator raised exception: "
    traceback.print_exc(e)
finally:
    pdb.set_trace()
