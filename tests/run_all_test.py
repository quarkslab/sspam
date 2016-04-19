import unittest

testmodules = [
    'test_arithm_simpl',
    'test_asttools',
    'test_cse',
    'test_pattern_matcher',
    'test_pre_processing',
    'test_simplifier',
    ]

suite = unittest.TestSuite()

for t in testmodules:
    suite.addTest(unittest.defaultTestLoader.loadTestsFromName(t))

unittest.TextTestRunner().run(suite)
