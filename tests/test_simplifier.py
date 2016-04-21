"""Tests for simplifier module.
"""

import ast
import os
import unittest

from sspam import simplifier
from sspam.tools import asttools


class TestSimplifier(unittest.TestCase):
    """
    Tests for Simplifier script.
    """

    def generic_test(self, expr, refstring, nbits=0):
        'Generic test for simplifier script'
        output_string = simplifier.simplify(expr, nbits)
        output = ast.parse(output_string)
        ref = ast.parse(refstring)
        self.assertTrue(asttools.Comparator().visit(output, ref))

    def test_input_file(self):
        'Test with file as an input'
        testfile = open("input.py", 'w')
        testfile.write("(4211719010 ^ 2937410391*x)" +
                       "+ 2*(2937410391*x | 83248285) + 4064867995")
        testfile.close()
        self.generic_test("input.py", "(4148116279 + (2937410391 * x))")
        os.remove("input.py")

    def test_basics(self):
        'Some basics tests'
        tests = [("45 + x + 32", "(77 + x)"), ("x + x + x", "(3 * x)"),
                 ("""
a = 3 + x + 0
b = 4 + x - x + x
c = - 7 + a + b""",
                  """a = (3 + x)
b = (4 + x)
c = (2 * x)""")]
        for input_args, refstring in tests:
            self.generic_test(input_args, refstring)

    def test_real(self):
        'Tests based on real events'
        tests = [("(4211719010 ^ 2937410391*x) + " +
                  "2*(2937410391*x | 83248285) + 4064867995",
                  "(4148116279 + (2937410391 * x))"),
                 ("(2937410391*x | 3393925841) - " +
                  "((2937410391*x) & 901041454) + 638264265*y",
                  "(3393925841 + (638264265 * y))"),
                 ("(2937410391*x | 3393925841) + 638264265*y" +
                  "- ((2937410391 * x) & 901041454)",
                  "(3393925841 + (638264265 * y))")]

        for input_args, refstring in tests:
            self.generic_test(input_args, refstring)

    def test_samples(self):
        'Tests on real samples'
        samples_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "samples")
        for samplefilename in os.listdir(samples_dir):
            fname = os.path.join(samples_dir, samplefilename)
            samplefile = open(fname, 'r')
            refstring = samplefile.readline()[2:-1]
            output_string = simplifier.simplify(fname).split('\n')[-1]
            self.assertTrue(refstring == output_string)


if __name__ == '__main__':
    unittest.main()
