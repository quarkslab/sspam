#!/usr/bin/python
"""
Script to run all tests of tests/ directory
"""

#pylint: disable=invalid-name
import unittest
import sys

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

if len(sys.argv) > 1 and sys.argv[1] == 'quick':
    testmodules = [module for module in alltestmodules if not "long" in module]
else:
    testmodules = alltestmodules

for t in testmodules:
    suite.addTest(unittest.defaultTestLoader.loadTestsFromName(t))

if unittest.TextTestRunner().run(suite).wasSuccessful():
    exit(0)
else:
    exit(1)
