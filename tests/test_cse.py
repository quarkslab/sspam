"""Tests for cse script.
"""

import ast
import unittest
import os
import z3

from sspam.tools import asttools, cse


class TestCSE(unittest.TestCase):
    """
    Test that cse produce expected ast.
    """

    def generic_basicCSE(self, instring, refstring):
        'Generic test for CSE: matching of CSE AST and ref AST'
        output_cse = cse.apply_cse(instring)
        self.assertEquals(refstring, output_cse)

    def test_Basics(self):
        'Test matching of AST with simple examples'
        tests = [("2*x + 2*x",
                  "cse0Mult0 = (2 * x)\nresult = (cse0Mult0 + cse0Mult0)"),
                 # this test is not working
                 # ("2*x + x*2", "cse_a = 2*x \ncse_a + cse_a"),
                 ("(a + b) + (3 & (a + b))",
                  "cse0Add0 = (a + b)\nresult = (cse0Add0 + (3 & cse0Add0))"),
                 ("((a + b) + c) + (43 | ((a + b) + c))",
                  "cse1Add1 = ((a + b) + c)\n" +
                  "result = (cse1Add1 + (43 | cse1Add1))"),
                 ("(a + b) + (a + b)*2 + ((a + b) + 76)",
                  "cse1Add0 = (a + b)\nresult = ((cse1Add0 + 76)" +
                  " + ((cse1Add0 * 2) + cse1Add0))"),
                 ]
        for orig, ref in tests:
            self.generic_basicCSE(orig, ref)

    def test_MultipleCSE(self):
        'Test matching of AST with more complex examples'
        tests = [("(a + b) + ((a + b)*2 + 3) + (a + b)*2",
                  "cse0Add0 = (a + b)\ncse0Mult0 = (cse0Add0 * 2)\n" +
                  "result = ((cse0Add0 + cse0Mult0) + (3 + cse0Mult0))"),
                 ("(92 | x) + (12 + (x | 92))*3 + ((x | 92) + 12)",
                  "cse0BitOr0 = (x | 92)\ncse1Add0 = (12 + cse0BitOr0)\n" +
                  "result = (cse1Add0 + ((cse1Add0 * 3) + cse0BitOr0))"),
                 ("(((((((a + b) * 2) + (c + d)) + (a + b)) + (c + d))" +
                  "+ (((a + b) & 45) + ((((a + b) * 2) + (c + d)) + " +
                  "(a + b)))) + ((((a + b) & 45) + ((((a + b) * 2) + " +
                  "(c + d)) + (a + b))) * 2))",
                  "cse8Add0 = (a + b)\ncse6Add1 = (c + d)\n" +
                  "cse5Add2 = (cse6Add1 + (cse8Add0 * 2))\n" +
                  "cse7Add4 = ((cse5Add2 + cse8Add0) + (cse8Add0 & 45))\n" +
                  "result = (cse8Add0 + (((cse7Add4 + cse6Add1) + cse5Add2)" +
                  " + (cse7Add4 * 2)))"),
                 ("((((((x) & 255) + 55)) + ((x) & 255)*13)*2) +" +
                  "(((((x) & 255) + 55)) + ((x) & 255)*13)",
                  "cse0BitAnd0 = (x & 255)\n" +
                  "cse1Add1 = ((cse0BitAnd0 + 55) + (cse0BitAnd0 * 13))\n" +
                  "result = (cse1Add1 + (cse1Add1 * 2))")]
        for orig, ref in tests:
            self.generic_basicCSE(orig, ref)

    def test_Xor36(self):
        'Test that CSE of the xor36 function is equivalent to original'
        #pylint: disable=exec-used
        pwd = os.path.dirname(os.path.realpath(__file__))
        input_file = open(os.path.join(pwd, 'xor36_flat'), 'r')
        input_string = input_file.read()
        input_ast = ast.parse(input_string)
        coderef = compile(ast.Expression(input_ast.body[0].value),
                          '<string>', 'eval')
        jack = asttools.GetVariables()
        jack.visit(input_ast)

        cse_string = cse.apply_cse(input_string)
        # get all assignment in one ast
        assigns = cse_string[:cse_string.rfind('\n')]
        cse_assign_ast = ast.parse(assigns, mode='exec')
        assign_code = compile(cse_assign_ast, '<string>', mode='exec')
        # get final expression in one ast
        result_string = cse_string.splitlines()[-1]
        result_ast = ast.Expression(ast.parse(result_string).body[0].value)
        result_code = compile(result_ast, '<string>', mode='eval')

        for var in list(jack.result):
            exec("%s = z3.BitVec('%s', 8)" % (var, var))
        exec(assign_code)
        sol = z3.Solver()
        sol.add(eval(coderef) != eval(result_code))
        self.assertEqual(sol.check().r, -1)


if __name__ == '__main__':
    unittest.main()
