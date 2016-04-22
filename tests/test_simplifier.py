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
        tests = [("45 + x + 32", "(77 + x)"), ("x + x + x", "(3 * x)")]
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
                  "(3393925841 + (638264265 * y))"),
                 ("(4211719010 ^ 2937410391 * x) + 2 * (2937410391 * x" +
                  " | 83248285) + 4064867995",
                  "((2937410391 * x) + 4148116279)"),
                 ("(2937410391*x | 3393925841) - ((2937410391 * x)" +
                  " & 901041454) + 638264265*y",
                  "((638264265 * y) + 3393925841)")]

        for input_args, refstring in tests:
            self.generic_test(input_args, refstring)


if __name__ == '__main__':
    unittest.main()
