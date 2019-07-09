from inaugurator import sh
import json
from subprocess import CalledProcessError


def get_cpus():
    try:
        r = sh.run("lscpu --json")
        d = json.loads(r)
        ret = dict()
        for prop in d.get('lscpu'):
            ret.update({prop['field'].strip(':').strip('(s)'): prop['data']})
        return ret
    except Exception as e:
        return {'error': e.message}


def get_nvdimm():
    try:
        r = sh.run('ndctl list -vv')
        return json.loads(r)
    except Exception as e:
        return []


def get_nvme_list():
    def load_nvme_devices():
        sh.run("mdev -s")
    try:
        load_nvme_devices()
        r = sh.run("nvme list -o json")
        return json.loads(r)
    except Exception as e:
        return {'error': e.message}


def get_loaded_nvme_devices():
    try:
        r = sh.run("ls /dev | grep nvme")
        return r.split("\n")[:-1]
    except Exception as e:
        return []


def get_lspci_lf():
    '''
    lspci indicate if exist and if lightfield is overpassed
    '''
    try:
        r = sh.run('lspci|grep -iE "8764|1d9a"')
        lines = r.strip().split('\n')
        lf_pci_lst = {}
        for line in lines:
            port, val = line.split(".", 1)
            lf_pci_lst[str(port).strip()] = val[2:]
        return lf_pci_lst
    except CalledProcessError as e:
        return {'errcode': e.returncode, 'error': e.output}
    except Exception as e:
        return {'error': e.message}


def get_lshw():
    try:
        r = sh.run("lshw -json")
        return json.loads(r)
    except Exception as e:
        return {}


def get_lightfield(numa):
    '''
    VPD output
    ----------
    when lightfield exist and its version above 3xx, 34x:
    "Read parameters:    02 01 10 29 18 10 29 02 ae 0a 01 18 03 ff ff ff 01 18 10 22 "

    Otherwise it is empty and to err stream we get
    "lf_pci_dev_init failed: found no device
    lf_pci_dev_init failed"
    '''
    try:
        r = sh.run("/root/inaugurator/inaugurator/execs/VPD -r 20 -n %s" % str(numa)).strip()
        if not r:
            return 'VPD failed'
        header, registers = r.split(':', 1)
        return {header.strip(): registers.strip()}
    except CalledProcessError as e:
        if 'no device' in e.output:
            return {'errcode': e.returncode, 'error': 'found no device'}
        return {'errcode': e.returncode, 'error': e.output}
    except Exception as e:
        return {'error': e.message}

def programtool_output(numa_idx):
    try:
        r = sh.run("/root/inaugurator/inaugurator/execs/program_tool read_version -n %d" % int(numa_idx))
        if not r:
            return {}
        return json.loads(r)
    except Exception as ex:
        return {'error': str(ex)}


class HWinfo:
    def __init__(self):
        self.data = None

    def run(self):
        data = {
                "cpu": get_cpus(),
                "nvme_list": get_nvme_list(),  # runs mdev -s
                "lshw": get_lshw(),
                "nvdimm": get_nvdimm(),
                "loaded_nvme_dev": get_loaded_nvme_devices(),
                "lightfield": {
                    "numa0": get_lightfield(0),
                    "numa1": get_lightfield(1),
                    "lspci": get_lspci_lf(),
                    "programtool": {"numa0": programtool_output(0), "numa1": programtool_output(1)}
                    },
                }
        return data
