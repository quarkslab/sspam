#pylint: disable=relative-import

import ast
import astunparse
import unittest

from sspam.tools import bvsize
from sspam import arithm_simpl

class TestBasics(unittest.TestCase):

    def test_one(self):
        expr = "(bv32(rol(Sym0 + bv32(1))) - bv32(8) - bv32(8))*bv32(256) & bv8(0xFF)"
        print expr
        a = ast.parse(expr)
        bvsize.ComputeBvSize(32).visit(a)
        bvsize.DisplayBvSize().visit(a)
        print "-"*80
        bvsize.ReduceBvSize().visit(a)
        bvsize.DisplayBvSize().visit(a)
        print astunparse.unparse(a)
        bvsize.RegroupBvSize().visit(a)
        print astunparse.unparse(a)
        a = arithm_simpl.run(a, 64)
        print ast.dump(a)
        print astunparse.unparse(a)


if __name__ == '__main__':
    unittest.main()

