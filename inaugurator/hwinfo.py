from inaugurator import sh
import json
import re


def get_network():
    try:
        r = sh.run('lshw -c network -json')
        return _lshw_json_fix(r)

    except Exception as e:
        return {'output': r, 'error': e.message}


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


def get_ssds():
    try:
        r = sh.run("lshw -c storage -json")
        return _lshw_json_fix(r)
    except Exception as e:
        return {'output': r, 'error': e.message}

def get_nvme_list():
    try:
        r = sh.run("nvme list -o json")
        return json.loads(r)
    except Exception as e:
        return {'output': r, 'error': e.message}

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
        return {'output': r, 'error': e.message}


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
                "memory": get_memory(),
                "nvme_list": get_nvme_list(),
                }
        return data
