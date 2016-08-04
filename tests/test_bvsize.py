"""
Tests for bvsize module.
"""

# pylint: disable=relative-import

import ast
import astunparse
import unittest

from sspam.tools import bvsize
from sspam import arithm_simpl


class TestBasics(unittest.TestCase):
    """
    First basics tests.
    """

    def test_one(self):
        'Very quick test'
        # pylint: disable=no-self-use

        expr = ("(bv32(rol(Sym0 + bv32(1))) - bv32(8)" +
                " - bv32(8))*bv32(256) & bv8(0xFF)")
        print expr
        expr_ast = ast.parse(expr)
        bvsize.ComputeBvSize(32).visit(expr_ast)
        bvsize.DisplayBvSize().visit(expr_ast)
        print "-"*80
        bvsize.ReduceBvSize().visit(expr_ast)
        bvsize.DisplayBvSize().visit(expr_ast)
        print astunparse.unparse(expr_ast)
        bvsize.RegroupBvSize().visit(expr_ast)
        print astunparse.unparse(expr_ast)
        expr_ast = arithm_simpl.run(expr_ast, 64)
        print ast.dump(expr_ast)
        print astunparse.unparse(expr_ast)


if __name__ == '__main__':
    unittest.main()
