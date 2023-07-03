import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="inaugurator",
    version="1.6.0",
    author="Guy Menahem",
    author_email="guymenahem@neokarm.com",
    description=(
        "Osmos complete rootfs images by booting this initrd,"
        "from the network or a DOK"),
    keywords="Osmosis rootfs initrd boot",
    url="http://packages.python.org/inaugurator",
    packages=['inaugurator', 'inaugurator.pyudev', 'inaugurator.server'],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
    ],
    requires=['pyudev','mock', 'rpdb'],
)
