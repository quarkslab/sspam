"""Tests for asttools module.

- TestGetVariables
- TestGetSize
- TestGetConstExpr
- TestConstFolding
- TestGetConstMod
"""
#pylint: disable=relative-import

import ast
import astunparse
import unittest

from sspam import pre_processing
from sspam.tools import asttools
import templates


class TestGetVariables(templates.AstVisitorCase):
    """
    Test ast visitor GetVariables.
    """

    def test_Basics(self):
        'Simple tests for GetVariable'
        corresp = [("x", {"x"}), ("3*(x & 45) + x", {"x"}),
                   ("x + 2*y", {"y", "x"}),
                   ("bla - azerty + 2*(azerty + bla)", {"azerty", "bla"})]
        self.generic_AstVisitorTest(corresp, asttools.GetVariables())

    def test_NoVariable(self):
        'Test when there is no variable'
        self.generic_AstVisitorTest('(3 + 34)*2', set(),
                                    asttools.GetVariables())


class TestGetSize(templates.AstVisitorCase):
    """
    Test ast visitor GetSize.
    """

    def test_Basics(self):
        'Simple tests for GetSize'
        corresp = [("x", 0), ("x & 3", 2), ("x - 5", 4), ("x + 250", 8),
                   ("x*(-0x1325)", 16),
                   ("0xFFFFFFFE*x", 32), ("(0x123456789876543 | x) + 12", 64)]
        self.generic_AstVisitorTest(corresp, asttools.GetSize())


class TestGetConstExpr(templates.AstVisitorCase):
    """
    Test ast visitor GetConstExpr.
    """

    def test_GetConstExpr(self):
        'Simple tests for GetConstExpr'
        hooks = asttools.apply_hooks()
        corresp = [("3", set([ast.Num(3)])),
                   ("2 + 456", set([ast.Num(2),
                                    ast.Num(456),
                                    ast.BinOp(ast.Num(2), ast.Add(),
                                              ast.Num(456))])),
                   ("(3 + x) + 45", set([ast.Num(3), ast.Num(45)])),
                   (("x + y"), set())]
        self.generic_AstVisitorTest(corresp, asttools.GetConstExpr())
        asttools.restore_hooks(hooks)


class TestConstFolding(unittest.TestCase):
    """
    Test constant folding transformer.
    """

    def generic_ConstFolding(self, origstring, refstring, nbits, lvl=False):
        'Generic test for ConstFolding transformer'
        orig = ast.parse(origstring)
        ref = ast.parse(refstring)
        if lvl:
            orig = asttools.LevelOperators().visit(orig)
            ref = asttools.LevelOperators().visit(orig)
        orig = asttools.ConstFolding(orig, 2**nbits).visit(orig)
        self.assertTrue(asttools.Comparator().visit(orig, ref))

    def test_Basics(self):
        'Simple tests for ConstFolding'
        corresp = {"45 + 2": ["47", 8], "(3 + 2 + x)": ["(5 + x)", 16],
                   "2*230": ["204", 8], "2 - 4": ["254", 8],
                   "- (3*45)": ["4294967161", 32],
                   "(3 + x)*2 + 4": ["(3 + x)*2 + 4", 64]}
        for origstring, [refstring, nbits] in corresp.iteritems():
            self.generic_ConstFolding(origstring, refstring, nbits)

    def test_Leveled_AST(self):
        'Simple tests for ConstFolding on custom BoolOps'
        corresp = {"(x + 3) + 2": ["x + 5", 8],
                   "((x ^ 14) ^ 234) ^ 48": ["x ^ 212", 8],
                   "42*34*y*z": ["1428*y*z", 16]}
        for origstring, [refstring, nbits] in corresp.iteritems():
            self.generic_ConstFolding(origstring, refstring, nbits, True)


class TestReplaceBitWiseOp(templates.AstCompCase):
    """
    Test behaviour of ast transformer ReplaceBitwiseOp.
    """

    def test_Basics(self):
        'Simple tests for ReplaceBitwiseOp'
        corresp = [("x ^ y", "mxor(x, y)"), ("x & y", "mand(x, y)"),
                   ("x | y", "mor(x,y)"), ("(x ^ y) & 45",
                                           "mand(mxor(x,y), 45)"),
                   ("~x", "mnot(x)"), ("x + y", "x + y"),
                   ("(x & 3)*2 + ~(x - 3)", "mand(x, 3)*2 + mnot(x - 3)")]
        self.generic_AstCompTest(corresp, asttools.ReplaceBitwiseOp())


class TestReplaceBitwiseFunctions(templates.AstCompCase):
    """
    Test ast transformer class ReplaceBitwiseFunction.
    """

    def test_Basics(self):
        'Simple tests for ReplaceBitwiseFunctions'
        corresp = [("mand(x, y)", "x & y"), ("mor(x, y)", "x | y"),
                   ("mxor(x ,y)", "x ^ y"), ("mnot(x)", "~x"),
                   ("mand(mor(x, 45), y) + 3", "((x | 45) & y) + 3")]
        self.generic_AstCompTest(corresp, asttools.ReplaceBitwiseFunctions())


class TestGetConstMod(templates.AstCompCase):
    """
    Test GetContMod.
    """

    def test_Basics(self):
        'Simple tests for GetConstMod'
        corresp = {"34": ["2", 4], "356 + x": ["100 + x", 8],
                   "75901*y + 456": ["10365*y + 456", 16]}
        for origstring, [refstring, nbits] in corresp.iteritems():
            transformer = asttools.GetConstMod(nbits)
            self.generic_AstCompTest(origstring, refstring, transformer)


class TestComparator(unittest.TestCase):
    """
    Some tests for comparator because it's used in a lot in other tests.
    """

    def test_comp(self):
        'Basic tests for comparison'
        comp = asttools.Comparator()

        add_a = ast.parse('x + y')
        add_b = ast.parse('x + y')
        self.assertTrue(comp.visit(add_a, add_b))
        add_c = ast.parse('y + x')
        self.assertTrue(comp.visit(add_a, add_c))

        sub_a = ast.parse('x - y')
        self.assertFalse(comp.visit(add_a, sub_a))
        sub_b = ast.parse('y - x')
        self.assertFalse(comp.visit(sub_a, sub_b))

        expr_a = ast.parse('2*(x & y) + ((a - 3) ^ 45)')
        expr_b = ast.parse('2*(x & y) + ((a - 3) ^ 45)')
        self.assertTrue(comp.visit(expr_a, expr_b))
        expr_c = ast.parse('2*(y & x) + (45 ^ (a - 3))')
        self.assertTrue(comp.visit(expr_a, expr_c))
        expr_d = ast.parse('3*(y & x) + (45 ^ (a - 3))')
        self.assertFalse(comp.visit(expr_b, expr_d))

        expr_a = ast.parse('(3*x) + 57 - (x | (-2))')
        expr_b = ast.parse('3*x + 57 - (x | (-2))')
        self.assertTrue(comp.visit(expr_a, expr_b))

    def test_onBoolOp(self):
        'Tests on BoolOp'

        expr_a = ast.BoolOp(ast.Add(), [ast.Num(1), ast.Num(2), ast.Num(3)])
        expr_b = ast.BoolOp(ast.Add(), [ast.Num(3), ast.Num(2), ast.Num(1)])
        self.assertTrue(asttools.Comparator().visit(expr_a, expr_b))

        expr_a = ast.BoolOp(ast.Add, [ast.Num(1), ast.BoolOp(ast.Mult(),
                                                             [ast.Num(5),
                                                              ast.Num(6)]),
                                      ast.Num(4)])
        expr_b = ast.BoolOp(ast.Add, [ast.BoolOp(ast.Mult(), [ast.Num(6),
                                                              ast.Num(5)]),
                                      ast.Num(4),
                                      ast.Num(1)])
        self.assertTrue(asttools.Comparator().visit(expr_a, expr_b))


class TestLeveling(unittest.TestCase):
    """
    Test that leveling produce expected ast.
    """

    def generic_leveling(self, refstring_list, result):
        'Test matching of leveled AST and ref AST'
        for refstring in refstring_list:
            ref = ast.parse(refstring, mode="eval").body
            ref = asttools.LevelOperators().visit(ref)
            self.assertTrue(asttools.Comparator().visit(ref, result))

    def test_basics(self):
        'Simple tests with matching of AST'
        corresp = [(["a + b + c", "a + (b + c)", "b + c + a"],
                    ast.BoolOp(ast.Add(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.Name('c', ast.Load())])),
                   (["a + b + c + d", "(a + b) + (c + d)",
                     "a + (b + c + d)", "a + (b + (c + d))"],
                    ast.BoolOp(ast.Add(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.Name('c', ast.Load()),
                                ast.Name('d', ast.Load())])),
                   (["a + b + c*d", "a + c*d + b"],
                    ast.BoolOp(ast.Add(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.BinOp(ast.Name('c', ast.Load()),
                                          ast.Mult(),
                                          ast.Name('d', ast.Load()))])),
                   (["a*b*c"],
                    ast.BoolOp(ast.Mult(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.Name('c', ast.Load())])),
                   (["a + c*d*e"],
                    ast.BinOp(ast.Name('a', ast.Load()), ast.Add(),
                              ast.BoolOp(ast.Mult(),
                                         [ast.Name('c', ast.Load()),
                                          ast.Name('d', ast.Load()),
                                          ast.Name('e', ast.Load())]))),
                   (["a + b + c + c*d", "a + c*d + b + c"],
                    ast.BoolOp(ast.Add(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.Name('c', ast.Load()),
                                ast.BinOp(ast.Name('c', ast.Load()),
                                          ast.Mult(),
                                          ast.Name('d', ast.Load()))])),
                   (["a + b + c*d*e", "a + c*d*e + b", "b + e*c*d + a"],
                    ast.BoolOp(ast.Add(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.BoolOp(ast.Mult(),
                                           [ast.Name('c', ast.Load()),
                                            ast.Name('d', ast.Load()),
                                            ast.Name('e', ast.Load())])])),
                   (["a + c*d*e + b + c"],
                    ast.BoolOp(ast.Add(),
                               [ast.Name('a', ast.Load()),
                                ast.Name('b', ast.Load()),
                                ast.Name('c', ast.Load()),
                                ast.BoolOp(ast.Mult(),
                                           [ast.Name('c', ast.Load()),
                                            ast.Name('d', ast.Load()),
                                            ast.Name('e', ast.Load())])]))]
        for refstring, result in corresp:
            self.generic_leveling(refstring, result)

    def test_astform(self):
        'Tests with different types of ast'
        t1 = ast.parse("1 + 2 + 3", mode="eval").body
        t1_ref = ast.BoolOp(ast.Add(), [ast.Num(1), ast.Num(2), ast.Num(3)])
        t2 = ast.parse("1 + 2 + 3", mode="eval")
        t3 = ast.parse("1 + 2 + 3").body[0]
        tests = [(t1, t1_ref), (t2, ast.Expression(t1_ref)),
                 (t3, ast.Expr(t1_ref))]
        for test, ref in tests:
            ltest = asttools.LevelOperators().visit(test)
            self.assertTrue(asttools.Comparator().visit(ltest, ref))

    def test_afterSubMult(self):
        'Tests after SubToMult pre-processing'

        tests = [("1 + 2 - 3", ast.BoolOp(ast.Add(), [ast.Num(1), ast.Num(2),
                                                      ast.BinOp(ast.Num(-1),
                                                                ast.Mult(),
                                                                ast.Num(3))])),
                 ("1 + 2 - 3 + 4", ast.BoolOp(ast.Add(),
                                              [ast.Num(1),
                                               ast.Num(2),
                                               ast.BinOp(ast.Num(-1),
                                                         ast.Mult(),
                                                         ast.Num(3)),
                                               ast.Num(4)])),
                 ("(1 + 2) - (3 + 4)",
                  ast.BoolOp(ast.Add(),
                             [ast.Num(1), ast.Num(2),
                              ast.BinOp(ast.Num(-1), ast.Mult(),
                                        ast.BinOp(ast.Num(3), ast.Add(),
                                                  ast.Num(4)))]))]
        for teststring, ref_ast in tests:
            test_ast = ast.parse(teststring, mode="eval").body
            test_ast = pre_processing.all_preprocessings(test_ast)
            test_ast = asttools.LevelOperators(ast.Add).visit(test_ast)
            self.assertTrue(asttools.Comparator().visit(test_ast, ref_ast))

    def test_withUnaryOp(self):
        'Test with UnaryOp involved'
        tests = [("5 + (-(6 + 2)) + 3",
                  ast.BoolOp(ast.Add(),
                             [ast.Num(5),
                              ast.UnaryOp(ast.USub(), ast.BinOp(ast.Num(6),
                                                                ast.Add(),
                                                                ast.Num(2))),
                              ast.Num(3)]))]
        for teststring, ref_ast in tests:
            test_ast = ast.parse(teststring, mode="eval").body
            test_ast = asttools.LevelOperators(ast.Add).visit(test_ast)
            self.assertTrue(asttools.Comparator().visit(test_ast, ref_ast))

    def test_NoLeveling(self):
        'Tests where nothing should be leveled'
        corresp = [(["a + b", "b + a"],
                   ast.BinOp(ast.Name('a', ast.Load()),
                             ast.Add(),
                             ast.Name('b', ast.Load()))),
                   (["c*d", "d*c"],
                    ast.BinOp(ast.Name('c', ast.Load()),
                              ast.Mult(),
                              ast.Name('d', ast.Load()))),
                   (["a + c*d", "d*c + a"],
                    ast.BinOp(ast.Name('a', ast.Load()), ast.Add(),
                              ast.BinOp(ast.Name('c', ast.Load()), ast.Mult(),
                                        ast.Name('d', ast.Load()))))]
        for refstring, result in corresp:
            self.generic_leveling(refstring, result)

    def test_UnLeveling(self):
        'Tests to see if unleveling is correct'

        tests = [("x + (3 + y)", "3 + (y + x)"),
                 ("x*(2*z)", "2*(z*x)"),
                 ("x + (y + (z*(5*var)))", "y + (5*(var*z) + x)")]

        for test, ref in tests:
            ref_ast = ast.parse(ref)
            ast_test = ast.parse(test)
            asttools.LevelOperators().visit(ast_test)
            asttools.Unleveling().visit(ast_test)
            self.assertTrue(asttools.Comparator().visit(ast_test, ref_ast))
            self.assertFalse('BoolOp' in astunparse.unparse(ast_test))


if __name__ == '__main__':
    unittest.main()
