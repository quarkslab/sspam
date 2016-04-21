#!/usr/bin/python
"""
Script to run all tests of tests/ directory
"""

#pylint: disable=invalid-name
import unittest
import sys

testmodules = [
    'test_arithm_simpl',
    'test_asttools',
    'test_cse',
    'test_pattern_matcher',
    'test_pre_processing']

suite = unittest.TestSuite()

if len(sys.argv) > 1 and sys.argv[1] == 'full':
    testmodules.append("test_simplifier")

for t in testmodules:
    suite.addTest(unittest.defaultTestLoader.loadTestsFromName(t))

if unittest.TextTestRunner().run(suite).wasSuccessful():
    exit(0)
else:
    exit(1)
