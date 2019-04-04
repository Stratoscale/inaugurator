from inaugurator import sh
import json
import re
from subprocess import CalledProcessError


def get_network():
    try:
        r = sh.run('lshw -c network -json')
        return _lshw_json_fix(r)

    except Exception as e:
        return {'error': e.message}


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

def get_dimm():
    try:
        r = sh.run('lshw -c memory -json')
        return _lshw_json_fix(r)
    except Exception as e:
        return {'error': e.message}

def get_ssds():
    try:
        r = sh.run("lshw -c storage -json")
        return _lshw_json_fix(r)
    except Exception as e:
        return {'error': e.message}


def get_nvme_list():
    try:
        r = sh.run("nvme list -o json")
        return json.loads(r)
    except Exception as e:
        return {'error': e.message}


def get_loaded_nvme_devices():
    try:
        r = sh.run("ls /dev | grep nvme")
        return r.split("\n")[:-1]
    except Exception as e:
        return {'error': e.message}


def get_memory():
    '''
    result in Megabytes
    '''
    try:
        r = sh.run("free -m")
        memory = dict()
        lines = r.split('\n')
        if len(lines) > 0:
            keys = [i.strip() for i in lines[0].split()]
            values = [i.strip() for i in lines[1].split()[1:]]
            for i in range(len(keys)):
                memory[keys[i]] = values[i]

        return memory
    except Exception as e:
        return {'error': e.message}


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


def _lshw_json_fix(output):
    edited = re.sub("}\s*{", "},{", str(output))
    edited = edited.strip().strip(',')
    edited = "[" + edited + "]"
    return json.loads(edited)


class HWinfo:
    def __init__(self):
        self.data = None

    def run(self):
        data = {"network": get_network(),
                "cpu": get_cpus(),
                "ssd": get_ssds(),
                "memory": get_dimm(),
                "nvme_list": get_nvme_list(),
                "loaded_nvme_dev": get_loaded_nvme_devices(),
                "lightfield": {
                    "numa0": get_lightfield(0),
                    "numa1": get_lightfield(1),
                    "lspci": get_lspci_lf(),
                    },
                }
        return data
