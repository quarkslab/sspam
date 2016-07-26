#!/usr/bin/python
"""
Script to run all tests of tests/ directory
"""

import unittest
import sys


def run_all_tests(quick=False):
    'Run all tests in the list'
    alltestmodules = [
        'test_arithm_simpl',
        'test_asttools',
        'test_cse',
        'test_pattern_matcher',
        'test_pre_processing',
        'test_simplifier',
        'test_pattern_matcher_long',
        'test_simplifier_long']

    suite = unittest.TestSuite()

    if quick:
        testmodules = [module for module in alltestmodules
                       if "long" not in module]
    else:
        testmodules = alltestmodules

    for test in testmodules:
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(test))

    if unittest.TextTestRunner().run(suite).wasSuccessful():
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'quick':
        run_all_tests(quick=True)
    else:
        run_all_tests()
