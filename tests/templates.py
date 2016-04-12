"""
This module contains templates to use for most common tests.

Available templates are:
 - AstCompCase (compare obfuscated ast and original ast)
 - AstVisitorCase (to compare result of an ast visitor)
"""

import unittest
import ast

from sspam.tools import asttools


class AstCompCase(unittest.TestCase):
    """
    Generic method to compare obfuscated ast and original ast.
    """

    def generic_AstCompTest(self, *args):
        """Args: (tests, transformer) with tests a list,
        or (input_string, refstring, transformer)"""

        if len(args) != 2 and len(args) != 3:
            raise Exception("generic_AstTest should be " +
                            "called with 3 or 4 arguments")
        if len(args) == 2:
            tests = args[0]
            transformer = args[1]
        else:
            tests = [(args[0], args[1])]
            transformer = args[2]
        for origstring, refstring in tests:
            orig = ast.parse(origstring)
            ref = ast.parse(refstring)
            orig = transformer.visit(orig)
            self.assertTrue(asttools.Comparator().visit(orig, ref))


class AstVisitorCase(unittest.TestCase):
    """
    Generic method to compare result of ast visitor.
    """

    def generic_AstVisitorTest(self, *args):
        'Generic test for comparison of NodeVisitor results'

        if len(args) != 2 and len(args) != 3:
            print args
            raise Exception("generic_AstVisitorTest should be " +
                            "called with 3 or 4 arguments")

        if len(args) == 2:
            tests = args[0]
            visitor = args[1]
        else:
            tests = [(args[0], args[1])]
            visitor = args[2]
        for refstring, results in tests:
            ref = ast.parse(refstring)
            visitor.visit(ref)
            out = visitor.result
            self.assertEquals(out, results)
            visitor.reset()
