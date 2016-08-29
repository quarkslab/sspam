"""
Tests for bvsize module.
"""

# pylint: disable=relative-import

import ast
# import astunparse
import unittest

from sspam.tools.bvsize import ComputeBvSize, getbvsize
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
            ComputeBvSize(maxsize).visit(input_ast)
            self.assertEquals(getbvsize(input_ast), maxsize)

    def test_basics(self):
        'Very basics tests'
        tests = [('bv32(x)', 32), ('bv8(y)', 8), ('bv16(x + y)', 16)]
        for input_string, refsize in tests:
            input_ast = ast.parse(input_string, mode="eval")
            ComputeBvSize(32).visit(input_ast)
            self.assertEquals(getbvsize(input_ast.body), refsize)

    def test_nosize(self):
        'Test that maxnbits is chosen when size is not given'
        input_ast = ast.parse('x')
        ComputeBvSize(32).visit(input_ast)
        self.assertEquals(getbvsize(input_ast.body[0].value), 32)

    def test_multisize(self):
        'Test that several sizes into one expression are taken into account'
        input_ast = ast.parse('bv32(bv16(x) + bv8(y))', mode="eval")
        ComputeBvSize(32).visit(input_ast)
        self.assertEquals(getbvsize(input_ast.body), 32)
        self.assertEquals(getbvsize(input_ast.body.left), 16)
        self.assertEquals(getbvsize(input_ast.body.right), 8)

    def test_rol_ror(self):
        'Test when sspam_rol and sspam_ror functions are used'
        input_ast = ast.parse('sspam_rol(x, 2, 16)', mode="eval")
        ComputeBvSize(32).visit(input_ast)
        self.assertEquals(getbvsize(input_ast.body), 16)
        input_ast = ast.parse('sspam_ror(y, 3, 32)', mode="eval")
        ComputeBvSize(32).visit(input_ast)
        self.assertEquals(getbvsize(input_ast.body), 32)


# class TestBasics(unittest.TestCase):
#    """
#    First basics tests.
#    """
#
#    def test_one(self):
#        'Very quick test'
#        # pylint: disable=no-self-use
#
#        expr = ("(bv32(rol(Sym0 + bv32(1))) - bv32(8)" +
#                " - bv32(8))*bv32(256) & bv8(0xFF)")
#        print expr
#        expr_ast = ast.parse(expr)
#        bvsize.ComputeBvSize(32).visit(expr_ast)
#        bvsize.DisplayBvSize().visit(expr_ast)
#        print "-"*80
#        bvsize.ReduceBvSize().visit(expr_ast)
#        bvsize.DisplayBvSize().visit(expr_ast)
#        print astunparse.unparse(expr_ast)
#        bvsize.RegroupBvSize().visit(expr_ast)
#        print astunparse.unparse(expr_ast)
#        expr_ast = arithm_simpl.run(expr_ast, 64)
#        print ast.dump(expr_ast)
#        print astunparse.unparse(expr_ast)


if __name__ == '__main__':
    unittest.main()
