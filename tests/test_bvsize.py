"""
Tests for bvsize module.
"""

# pylint: disable=relative-import

import ast
# from astunparse import unparse
import unittest

from sspam.tools import bvsize
# from sspam import arithm_simpl


class TestComputeBvSize(unittest.TestCase):
    """
    Test the computation of the size of a node.
    """

    def test_maxsize(self):
        'Test that maxsize if correctly stored in Module / Expr / Expression'
        tests = [('bv12(x)', 64), ('y', 32), ('z + 35', 16)]
        for input_string, maxsize in tests:
            input_ast = ast.parse(input_string, mode="eval")
            bvsize.ComputeBvSize(maxsize).visit(input_ast)
            self.assertEquals(bvsize.getbvsize(input_ast), maxsize)

    def test_basics(self):
        'Very basic tests'
        tests = [('bv32(x)', 32), ('bv8(y)', 8), ('bv16(x + y)', 16)]
        for input_string, refsize in tests:
            input_ast = ast.parse(input_string, mode="eval")
            bvsize.ComputeBvSize(32).visit(input_ast)
            self.assertEquals(bvsize.getbvsize(input_ast.body), refsize)

    def test_nosize(self):
        'Test that maxnbits is chosen when size is not given'
        input_ast = ast.parse('x')
        bvsize.ComputeBvSize(32).visit(input_ast)
        self.assertEquals(bvsize.getbvsize(input_ast.body[0].value), 32)

    def test_multisize(self):
        'Test that several sizes into one expression are taken into account'
        input_ast = ast.parse('bv32(bv16(x) + bv8(y))', mode="eval")
        bvsize.ComputeBvSize(32).visit(input_ast)
        self.assertEquals(bvsize.getbvsize(input_ast.body), 32)
        self.assertEquals(bvsize.getbvsize(input_ast.body.left), 16)
        self.assertEquals(bvsize.getbvsize(input_ast.body.right), 8)

    def test_rol_ror(self):
        'Test when sspam_rol and sspam_ror functions are used'
        input_ast = ast.parse('sspam_rol(x, 2, 16)', mode="eval")
        bvsize.ComputeBvSize(32).visit(input_ast)
        self.assertEquals(bvsize.getbvsize(input_ast.body), 16)
        input_ast = ast.parse('sspam_ror(y, 3, 32)', mode="eval")
        bvsize.ComputeBvSize(32).visit(input_ast)
        self.assertEquals(bvsize.getbvsize(input_ast.body), 32)


class ReduceBvSize(unittest.TestCase):
    """
    Test the soundness of bvsize reduction.
    """

    def test_basics(self):
        'Basic tests'
        input_ast = ast.parse('(x + bv32(651289) & bv8(23))', mode="eval")
        bvsize.ComputeBvSize(32).visit(input_ast)
        bvsize.ReduceBvSize().visit(input_ast)
        self.assertEquals(bvsize.getbvsize(input_ast.body), 8)
        self.assertEquals(bvsize.getbvsize(input_ast.body.left), 8)
        self.assertEquals(bvsize.getbvsize(input_ast.body.left.right), 8)
        self.assertEquals(input_ast.body.left.right.n, 25)


# class TestSimpl(unittest.TestCase):
#     """
#     A few tests for simplification with bit-vector size.
#     """
#
#     def test_basic_arithm(self):
#         'Very basic tests for arithmetic simplification'
#         # pylint: disable=no-self-use
#
#         expr = "bv32(8) + bv32(8)"
#         expr_ast = ast.parse(expr)
#         bvsize.ComputeBvSize(32).visit(expr_ast)
#         bvsize.RegroupBvSize().visit(expr_ast)
#         expr_ast = arithm_simpl.run(expr_ast, 64)
#         refstring = "\n16\n"
#         self.assertEquals(unparse(expr_ast), refstring)
#         print ast.dump(expr_ast)
#         print unparse(expr_ast)


if __name__ == '__main__':
    unittest.main()
