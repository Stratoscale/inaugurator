import string


def _digitsOnly(expression):
    return "".join([c for c in expression if c in string.digits])


# Not using setuptools' StrictVersion and LooseVersion since these are deprecated.
def _normalizedVersionNumber(version):
    components = version.split(".")
    components = [_digitsOnly(component) for component in components]
    components = [int(component) for component in components]
    return components


def _validateMinimumVersion(packageName, minVersion):
    minVersion = _normalizedVersionNumber(minVersion)
    package = __import__(packageName)
    actualVersion = package.__version__
    actualVersion = _normalizedVersionNumber(actualVersion)
    for componentNr in xrange(len(minVersion)):
        minimumComponent = minVersion[componentNr]
        actualComponent = actualVersion[componentNr]
        if actualComponent < minimumComponent:
            errorMsg = "Package '%(packageName)s' required minimum version: %(minVersion)s. Actual:" \
                       " %(actualVersion)s." % \
                       dict(packageName=packageName, minVersion=minVersion,
                            actualVersion=package.__version__)
            assert False, errorMsg
        if actualComponent != minimumComponent:
            break


def validateMinimumVersions(**packagesVersions):
    for packageName, minVersion in packagesVersions.iteritems():
        _validateMinimumVersion(packageName, minVersion)
