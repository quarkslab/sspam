"""Tests for sspam lib.

This module contains tests for all the main functions and classes of
the "sspam" lib.

Tested features are:
 - pre_processing.py with TestShiftMult and TestOrderAst
 - pattern_matcher.py with TestPatternMatcher, TestPatternIncluded
   and TestMatch
"""

import ast
import os
import unittest

from sspam import *
from sspam.tools import asttools, leveling
import templates


# tests of pre-processing

class TestShiftMult(templates.AstCompCase):
    """
    Test pre-processing that transforms shifts in mults.
    """

    def test_Basics(self):
        'Simple tests for shift -> mult replacement'
        tests = [("x << 1", "x*2"), ("(y*32) << 1", "(y*32)*2"),
                 ("var << 4", "var*16"), ("3 << var", "3 << var"),
                 ("(x ^ y) + (x << 1)", "(x ^ y) + 2*x")]
        self.generic_AstCompTest(tests, pre_processing.ShiftToMult())


class TestSubToMult(templates.AstCompCase):
    """
    Test pre-processing that transforms subs in mults of -1.
    """

    def test_Basics(self):
        'Simple tests for sub -> -1 mult replacement'
        tests = [("-x", "(-1)*x"), ("x - 3", "x + (-1)*3"),
                 ("- x - y", "(-1)*x + (-1)*y")]
        self.generic_AstCompTest(tests, pre_processing.SubToMult())


# tests for PatternMatcher

class TestPatternMatcher(unittest.TestCase):
    """
    Test for false positive / negative matchings.
    """

    def generic_test_positive(self, input_string, patt_string, preproc=False):
        'Generic test for positive matching'
        input_ast = ast.parse(input_string)
        pattern_ast = ast.parse(patt_string)
        pat = pattern_matcher.PatternMatcher(input_ast, pattern_ast)
        if not preproc:
            self.assertTrue(pat.visit(input_ast, pattern_ast))
        self.assertTrue(pattern_matcher.match(input_string, patt_string))

    def generic_test_negative(self, input_string, pattern_string, preproc=False):
        'Generic test for negative matching'
        input_ast = ast.parse(input_string)
        pattern_ast = ast.parse(pattern_string)
        pat = pattern_matcher.PatternMatcher(input_ast, pattern_ast)
        if not preproc:
            self.assertFalse(pat.visit(input_ast, pattern_ast))
        self.assertFalse(pattern_matcher.match(input_string, pattern_string))

    def test_reduced(self):
        'Small tests for basic pattern matching'
        pattern_string = "(A ^ ~B) + B"
        tests_pos = ["(x ^ ~y) + y", "(x ^ ~35) + 35", "(42 ^ ~y) + y",
                     "((x*a) ^ var) + ~var", "(42 ^ x) + 213",
                     "(42 ^ (a*x + b)) + 213", "((g ^ 23) ^ x) + (g ^ 232)"]
        for input_string in tests_pos:
            self.generic_test_positive(input_string, pattern_string)
        pattern_string = "(A ^ B) + ~B"
        tests_pos = ["(x ^ y) + ~y", "(x ^ ~y) + y", "(x ^ 45) + 210",
                     "(210 ^ x) + 45", "45 + (x ^ 210)"]
        test_pos = ["(x ^ ~y) + y"]
        for input_string in tests_pos:
            self.generic_test_positive(input_string, pattern_string)
        pattern_string = "(A ^ ~B) - B"
        test_pos = ["(x ^ ~y) - y", "(x ^ 45) - 210"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string)
        test_neg = ["(x ^ y) - y", "y - (x ^ ~y)", "(x ^ ~y) - z"]
        for input_string in test_neg:
            self.generic_test_negative(input_string, pattern_string)

    def test_csts(self):
        'Tests containing constants'
        test_pos = [("x + 172", "A + 2*B"),
                    ("x + 8", "A + B*2"),
                    ("x - 45 + 45", "A + B - B"),
                    ("254*x + 255", "-2*A - 1")]
        for input_string, patt_string in test_pos:
            self.generic_test_positive(input_string, patt_string, True)
        test_neg = [("x + 9", "B*2 + A")]
        for input_string, patt_string in test_neg:
            self.generic_test_negative(input_string, patt_string, True)

    def test_mod(self):
        'Tests where modulo on constants is useful'
        test_pos = [("(x | 54) + 255*(x & 54)",  "(A | B) - (A & B)"),
                    ("254*x + 255", "-2*A - 1")]
        for input_string, patt_string in test_pos:
            self.generic_test_positive(input_string, patt_string, True)

    def test_subs(self):
        'Tests with substractions (with pre-processing)'
        pattern_string = "-(A ^ ~B) - (A | B)"
        test_pos = ["-(43 ^ ~tmp2) - (43 | tmp2)",
                    "-(43 ^ ~tmp2) - (tmp2 | 43)",
                    "-(~tmp2 ^ 43) - (43 | tmp2)"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string, True)
        pattern_string = "A + B - 2*(A & B)"
        test_pos = ["x + 108 - 2*(x & 108)"]  #"-2*(x & 108) + x + 108",
                    # "(x & 108)*(-2) + x + 108"]
                    # those test work when the commented part of
                    # subtomult is activated
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string, True)

    def test_mbaxor_one(self):
        'Test positive / negative matchings for one XOR mba'
        pattern_string = "(A ^ ~B) + 2*(A | B)"

        tests_pos = ["(x ^ ~y) + 2*(x | y)", "(x | y)*2 + (x ^ ~y)",
                     "(y | x)*2 + (x ^ ~y)", "(y | x)*2 + (~y ^ x)",
                     "(x | y)*2 + (~x ^ y)", "(y | x)*2 + (y ^ ~x)",
                     "(x ^ ~45) + (45 | x)*2", "(x ^ 210) + 2*(x | 45)",
                     "((a + 32) ^ ~(var*5)) + ((a + 32) | (var*5))*2",
                     "((g ^ 23) | (a*x + b))*2 + ((a*x + b) ^ (g ^ 232))",
                     "((g + 45) | (12 & n))*2 + ((-g - 46) ^ (12 & n))",
                     "(g | (12 & n))*2 + ((g ^ (-1)) ^ (12 & n))"]
        for input_string in tests_pos:
            self.generic_test_positive(input_string, pattern_string)

        tests_neg = ["(x ^ y) + 2*(x | y)", "(~x ^ ~y) + 2*(x | y)",
                     "(x ^ 42) + 2*(x | 34)", "3*(x | y) + (x ^ ~y)",
                     "((g + 45) | (12 & n))*2 + ((-g - 47) ^ (12 & n))"]
        for input_string in tests_neg:
            self.generic_test_negative(input_string, pattern_string)

        # test with pre-processing
        tests_preproc = ["(x ^ ~y) + ((x | y) << 1)"]
        for input_string in tests_preproc:
            self.generic_test_positive(input_string, pattern_string, True)

    def test_mbaxor_two(self):
        'Test positive / negative matchings for another XOR mba'
        pattern_string = "(A ^ B) + 2*(A & B)"

        test_pos = ["(x ^ y) + 2*(x & y)", "(x ^ 35) + 2*(x & 35)",
                    "(y & 78)*2 + (y ^ 78)", "(x ^ ~y) + 2*(x & ~y)",
                    "((x + 2) ^ (y*3)) + ((x + 2) & (y*3))*2"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string)

        tests_neg = ["(x ^ x) + 2*(x & y)", "(x ^ ~y) + 2*(x & y)",
                     "(x ^ y) + 3*(x & y)"]
        for input_string in tests_neg:
            self.generic_test_negative(input_string, pattern_string)

    def test_mba_three(self):
        'Test positive / negative for an anoying MBA'
        pattern_string = "A - B + (~(2*A) & 2*B)"
        test_pos = ["x + (~(2*x) & 2*y) - y", "x + (~(2*x) & 90) + 211",
                    "x + ((-(2*x) - 1) & 90) + 211",
                    "x + ((254*x + 255) & 90) + 211"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string, True)

    def test_mba_four(self):
        'Test for MBA requiring to test with right nodes before left nodes'
        pattern_string = "-(~(2*A) & 2*B) -A"
        test_pos = ["-((-2*(x ^ 214) - 1) & 172) - (x ^ 214)",
                    "-((254*(x ^ 214) + 255) & 172) - (x ^ 214)"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string, True)

    def test_two_mult(self):
        'Test for equivalence of 2*(...) and something else with z3'
        pattern_string = "2*(A & B) + A + B"
        test_pos = ["2*(x & y) + x + y"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string)

    def test_leveled(self):
        'Test positive matchings for leveled ast'
        pattern_string = "A + 2*B + 3*C"
        test_pos = ["x + 2*y + 3*z", "3*z + 2*y + x", "2*y + 3*z + x"]
        for input_string in test_pos:
            self.generic_test_positive(input_string, pattern_string, True)

        # actual pre-processing only level ADD nodes, but this test is
        # for code coverage
        test_neg = ast.parse("x ^ 2*y ^ 2*z")
        test_neg = pre_processing.all_preprocessings(ast.parse(test_neg))
        test_neg = leveling.LevelOperators().visit(test_neg)
        patt_ast = ast.parse(pattern_string)
        patt_ast = pre_processing.all_preprocessings(patt_ast)
        patt_ast = leveling.LevelOperators(ast.Add).visit(patt_ast)
        pat = pattern_matcher.PatternMatcher(test_neg, patt_ast)
        self.assertFalse(pat.visit(test_neg, patt_ast))

    def test_with_nbits(self):
        'Test with nbits given by the user'
        tests = [("(x ^ 52) + 2*(x | 203)", 8),
                 ("(x ^ 789) + 2*(64746 | x)", 16)]
        for input_string, nbits in tests:
            input_ast = ast.parse(input_string)
            pattern_ast = ast.parse("(A ^ ~B) + 2*(A | B)")
            pat = pattern_matcher.PatternMatcher(input_ast, pattern_ast, nbits)
            self.assertTrue(pat.visit(input_ast, pattern_ast))

    def test_real(self):
        'Tests inspirend from real events'
        pattern_string = "(A ^ ~B) + 2*(A | B)"
        tests = [("((4211719010 ^ (2937410391 * x))" +
                 "+ (2 * ((2937410391 * x) | 83248285)))")]
        for input_string in tests:
            self.generic_test_positive(input_string, pattern_string)

    def test_root(self):
        'Test with different types of roots'
        pattern_ast = ast.parse("A + B", mode='eval')
        input_ast = ast.parse("x + y", mode='eval')
        pat = pattern_matcher.PatternMatcher(input_ast, pattern_ast)
        self.assertTrue(pat.visit(input_ast, pattern_ast))


class TestPatternReplacement(unittest.TestCase):
    """
    Test PatternReplacement class.
    """

    def generic_test_replacement(self, tests, pattern, replacement):
        'Generic test for a list of input/output'
        for input_string, refstring in tests:
            input_ast = ast.parse(input_string)
            ref_ast = ast.parse(refstring)
            patt_ast = ast.parse(pattern)
            rep_ast = ast.parse(replacement)
            rep = pattern_matcher.PatternReplacement(patt_ast, input_ast,
                                                     rep_ast)
            input_ast = rep.visit(input_ast)
            self.assertTrue(asttools.Comparator().visit(input_ast, ref_ast))

    def test_simple(self):
        'Simple tests for replacement'
        pattern = "(A ^ ~B) + 2*(A | B)"
        replacement = "A + B - 1"
        tests = [("(x ^ ~y) + 2*(x | y)", "x + y - 1"),
                 ("(x ^ ~45) + (45 | x)*2", "x + 45 - 1"),
                 ("((a + 32) ^ ~(var*5)) + ((a + 32) | (var*5))*2",
                  "(a + 32) + (var*5) - 1"),
                 ("((g ^ 23) | (a*x + b))*2 + ((a*x + b) ^ (g ^ 232))",
                  "~(g ^ 232) + (a*x + b) - 1"),
                 ("((g + 45) | (12 & n))*2 + ((-g - 46) ^ (12 & n))",
                  "(g + 45) + (12 & n) - 1")]
        self.generic_test_replacement(tests, pattern, replacement)

    def test_associativity(self):
        'Simple tests for associativity'
        pattern = "3*A + 2*B"
        replacement = "B"
        tests = [("2*x + 3*y", "x"), ("2*x + y + 3*g", "x + y")]
        for input_string, refstring in tests:
            ref_ast = ast.parse(refstring, mode="eval").body
            output_ast = pattern_matcher.replace(input_string, pattern,
                                                 replacement)
            self.assertTrue(asttools.Comparator().visit(output_ast, ref_ast))

    def test_leveled(self):
        'Test on leveled ast'
        patt_string = "A + 2*B + 3*C"
        rep_string = "A"
        test_pos = "3*z + x + 2*y"
        ref_ast = ast.parse("x", mode='eval').body
        output_ast = pattern_matcher.replace(test_pos, patt_string, rep_string)
        self.assertTrue(asttools.Comparator().visit(output_ast, ref_ast))

        # only ADD nodes are leveled right now, this is for code
        # coverage
        test_neg = ast.parse("3*z ^ x ^ 2*y")
        test_neg = leveling.LevelOperators().visit(test_neg)
        patt_ast = ast.parse("A + 3*z")
        patt_ast = leveling.LevelOperators().visit(patt_ast)
        rep_ast = ast.parse(rep_string)
        ref_ast = ast.parse("3*z ^ x ^ 2*y")
        ref_ast = leveling.LevelOperators().visit(ref_ast)
        rep = pattern_matcher.PatternReplacement(patt_ast, test_neg, rep_ast)
        output_ast = rep.visit(test_neg)
        self.assertTrue(asttools.Comparator().visit(output_ast, ref_ast))

    def test_real(self):
        'Tests inspired from real events'

        pattern = "(A ^ ~B) + 2*(A | B)"
        replacement = "A + B - 1"
        tests = [(("(4211719010 ^ 2937410391*x) +" +
                   "2*(2937410391*x | 83248285) + 4064867995"),
                  "((((2937410391 * x) + 83248285) - 1) + 4064867995)")]
        self.generic_test_replacement(tests, pattern, replacement)

    def test_root(self):
        'Test with different types of roots'
        patt_ast = ast.parse("A + B", mode='eval')
        input_ast = ast.parse("x + y", mode='eval')
        ref_ast = ast.parse("89", mode='eval')
        rep_ast = ast.parse("89", mode='eval')
        rep = pattern_matcher.PatternReplacement(patt_ast, input_ast, rep_ast)
        input_ast = rep.visit(input_ast)
        self.assertTrue(asttools.Comparator().visit(input_ast, ref_ast))


# test of arithm_simpl

class TestArithSimplifier(unittest.TestCase):
    """
    Tests for arithm_simplifier function.
    """

    def generic_test(self, input_ast, ref_ast, nbits):
        'Generic test for arithmetic simplification'
        output_ast = arithm_simpl.main(input_ast, nbits)
        self.assertTrue(asttools.Comparator().visit(output_ast, ref_ast))

    def test_simple(self):
        'Some basics tests'

        nbits = 8
        tests = [("x", "x"), ("x + 3 - 3", "x"), ("x + x*y - x*y", "x"),
                 ("x + 45 + 243", "x + 32")]
        for input_string, ref_string in tests:
            input_ast = ast.parse(input_string, mode='eval')
            ref_ast = ast.parse(ref_string, mode='eval')
            self.generic_test(input_ast, ref_ast, nbits)
        # test with ast.Module
        for input_string, ref_string in tests:
            input_ast = ast.parse(input_string)
            ref_ast = ast.parse(ref_string)
            self.generic_test(input_ast, ref_ast, nbits)


# tests for generic simplifier

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
