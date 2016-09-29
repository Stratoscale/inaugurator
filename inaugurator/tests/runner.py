import os
import logging
import unittest
import argparse

logLevels = {0: logging.CRITICAL + 1,
             1: logging.CRITICAL,
             2: logging.CRITICAL,
             3: logging.WARNING,
             4: logging.INFO,
             5: logging.DEBUG}


def configureLogging(verbosity):
    logger = logging.getLogger()
    maxVerbosity = max(logLevels.keys())
    if verbosity > maxVerbosity:
        verbosity = maxVerbosity
    elif verbosity < 0:
        verbosity = 0
    logLevel = logLevels[verbosity]
    logger.setLevel(logLevel)


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-pattern", type=str, default="test_")
    parser.add_argument("--verbosity", type=int, default=0)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parseArgs()
    configureLogging(args.verbosity)
    tests_pattern = "*%s*" % (args.tests_pattern)
    suite = unittest.TestLoader().discover('.', tests_pattern)
    unittest.TextTestRunner(verbosity=args.verbosity).run(suite)
