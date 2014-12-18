import os
import logging


class EtcLabelFile:
    def __init__(self, mountPoint):
        self._labelFile = os.path.join(mountPoint, "etc", "inaugurator.label")
        if os.path.exists(self._labelFile):
            try:
                with open(self._labelFile, "r") as f:
                    label = f.read().strip()
                logging.info("Label previously inaugurated to HD: '%(label)s'", dict(label=label))
            except:
                logging.exception("Unable to read label")

    def write(self, label):
        with open(self._labelFile, "w") as f:
            f.write(label)
