"""Tests for cse script.
"""

import ast
import unittest
import os

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
        tests = [("2*x + 2*x", "cse0Mult0 = (2 * x)\nresult = (cse0Mult0 + cse0Mult0)"),
                 ("2*x + x*2", "cse_a = 2*x \ncse_a + cse_a"),
                 # ("(a + b) + (3 & (a + b))",
                  # "cse_a = (a + b) \ncse_a + (3 & cse_a)"),
                 # ("((a + b) + c) + (43 | ((a + b) + c))",
                  # "cse_a = ((a + b) + c) \ncse_a + (43 | cse_a)"),
                 # ("(a + b) + (a + b)*2 + ((a + b) + 76)",
                  # "cse_a = (a + b) \ncse_a + cse_a*2 + cse_a + 76")]
                 ]
        for orig, ref in tests:
            self.generic_basicCSE(orig, ref)

#    def test_MultipleCSE(self):
#        'Test matching of AST with more complex examples'
#        tests = [("(a + b) + ((a + b)*2 + 3) + (a + b)*2",
#                  "cse_b = (a + b) \ncse_a = cse_b*2" +
#                  "\ncse_b + cse_a + 3 + cse_a"),
#                 ("(92 | x) + (12 + (x | 92))*3 + ((x | 92) + 12)",
#                  "cse_b = (92 | x) \ncse_a = cse_b + 12" +
#                  "\ncse_b + cse_a*3 + cse_a"),
#                 ("(((((((a + b) * 2) + (c + d)) + (a + b)) + (c + d))" +
#                  "+ (((a + b) & 45) + ((((a + b) * 2) + (c + d)) + " +
#                  "(a + b)))) + ((((a + b) & 45) + ((((a + b) * 2) + " +
#                  "(c + d)) + (a + b))) * 2))",
#                  "cse_c = (a + b) \ncse_a = (c + d)\n" +
#                  "cse_b = (cse_c + (cse_a + (2 * cse_c)))\n" +
#                  "cse_f = (cse_b + (45 & cse_c))\n" +
#                  "(((cse_a + cse_b) + cse_f) + (2 * cse_f))"),
#                 ("((((((x) & 255) + 55)) + ((x) & 255)*13)*2) +" +
#                  "(((((x) & 255) + 55)) + ((x) & 255)*13)",
#                  "cse_c = (255 & x) \n" +
#                  "cse_a = ((55 + cse_c) + (13 * cse_c))\n" +
#                  "(cse_a + (2 * cse_a))")]
#        for orig, ref in tests:
#            self.generic_basicCSE(orig, ref)

#    def test_Xor36(self):
#        'Test that CSE of the xor36 function is equivalent to original'
#        input_file = open(os.path.join(os.path.dirname(os.path.realpath(__file__)),
#                                       'samples/xor36_flat.py'), 'r')
#        input_string = input_file.read()
#        input_ast = ast.parse(input_string)
#        coderef = compile(ast.Expression(input_ast.body[0].value),
#                          '<string>', 'eval')
#        jack = asttools.GetVariables()
#        jack.visit(input_ast)
#
#        input_cse = cse.apply_cse(input_string)
#        # gathering all assignments in one ast
#        ast_cses = ast.Module(input_cse.body[:-1])
#        ast.fix_missing_locations(ast_cses)
#        # excluding final expression in an ast
#        ast_final_expr = ast.Expression(input_cse.body[-1].value)
#        ast.fix_missing_locations(ast_final_expr)
#
#        code_cses = compile(ast_cses, '<string>', 'exec')
#        code_final_expr = compile(ast_final_expr, '<string>', 'eval')
#
#        for var in list(jack.result):
#            exec("%s = z3.BitVec('%s', 8)" % (var, var))
#        exec(code_cses)
#        # get the output of z3.prove ("proved" or counterexample)
#        with Capturing() as output:
#            z3.prove(eval(coderef) == eval(code_final_expr))
#        self.assertEquals(output, ["proved"])


if __name__ == '__main__':
    unittest.main()
