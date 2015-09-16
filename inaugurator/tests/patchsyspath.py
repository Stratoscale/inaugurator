import os
import sys
assert 'inaugurator' not in sys.modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def validatePaths():
    assert 'usr' not in __file__.split(os.path.sep)
