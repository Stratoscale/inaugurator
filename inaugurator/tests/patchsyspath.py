import os
import sys
assert 'pika' not in sys.modules
assert 'inaugurator' not in sys.modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
if 'PIKA_EGG_PATH' in os.environ:
    sys.path.insert(0, os.environ['PIKA_EGG_PATH'])


def validatePaths():
    assert 'usr' not in __file__.split(os.path.sep)
    import pika
    assert 'usr' not in os.path.dirname(pika.__file__)
    assert '.egg' in pika.__file__
