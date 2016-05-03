#!/usr/bin/python
"""Main simplification module.

Works the magic.
"""

import ast
from astunparse import unparse
import argparse
from copy import deepcopy
import os.path

from sspam.tools import asttools
from sspam import pattern_matcher
from sspam.pre_processing import all_preprocessings, all_target_preprocessings
from sspam import arithm_simpl


# list of known patterns and their replacements
DEFAULT_RULES = [("(A ^ ~B) + 2*(A | B)", "A + B - 1"),
                 ("(A | B) - (A & ~B)", "B"),
                 ("- (A ^ ~B) - 2*(A | B)", "-A - B + 1"),
                 ("A + B + 1 + (~A | ~B)", "(A | B)"),
                 ("A - B + (~(2*A) & 2*B)", "A ^ B"),
                 ("- A -(~(2*A) & 2*B)", "- (A ^ B) - B"),
                 # ("A + (~(2*A) & 2*B)", "(A ^ B) + B"),
                 ("-B + (~(2*A) & 2*B)", "(A ^ B) - A"),
                 ("-B + 2*(~A & B)", "(A ^ B) - A"),
                 ("A - B + 2*(~A & B)", "(A ^ B)"),
                 ("(A & B) + (A | B)", "A + B"),
                 ("(A ^ B) + 2*(A & B)", "A + B"),
                 ("A + B - 2*(A & B)", "(A ^ B)"),
                 ("- A - B + 2*(A | B)", "(A ^ B)"),
                 ("A + B - (A | B)", "A & B"),
                 ("(A & B) - (~A | B)", "A + 1"),
                 ("(A | B) - (A & B)", "A ^ B"),
                 ("-B + (2*(~A) & 2*B)", "(A ^ B) - A"),
                 ("-2*(~A & B) + B", "- (A ^ B) + A"),
                 ("A + B + (~A & ~B)", "(A & B) - 1"),
                 ("A + B + 2*(~A | ~B)", "(A ^ B) - 2"),
                 # makes test_my_mba.py fail if higher in the list
                 ("((2*A + 1) & 2*B)", "(2*A & 2*B)")]


DEBUG = False


class Simplifier(ast.NodeTransformer):
    """
    Simplifies a succession of assignments.
    For each assignment, simplify the value with :
    - replacing known variables
    - pattern matching
    - arithmetic simplification with z3
    - updating variable value for further replacement
    """

    def __init__(self, nbits, rules_list=DEFAULT_RULES):
        'Init context : correspondance between variables and values'
        #pylint: disable=dangerous-default-value
        self.context = {}
        self.nbits = nbits

        self.patterns = []
        for pattern, replace in rules_list:
            patt_ast = ast.parse(pattern, mode="eval").body
            patt_ast = all_preprocessings(patt_ast, self.nbits)
            patt_ast = asttools.LevelOperators(ast.Add).visit(patt_ast)
            rep_ast = ast.parse(replace, mode="eval").body
            self.patterns.append((patt_ast, rep_ast))

    def simplify(self, expr_ast, nbits):
        'Apply pattern matching and arithmetic simplification'
        if DEBUG:
            print "before: "
            print unparse(expr_ast)
            print ""
        expr_ast = all_target_preprocessings(expr_ast, self.nbits)
        expr_ast = asttools.LevelOperators(ast.Add).visit(expr_ast)
        for pattern, repl in self.patterns:
            rep = pattern_matcher.PatternReplacement(pattern, expr_ast, repl)
            new_ast = rep.visit(deepcopy(expr_ast))
            if DEBUG:
                if not asttools.Comparator().visit(new_ast, expr_ast):
                    print "replaced! "
                    expr_debug = deepcopy(expr_ast)
                    expr_debug = asttools.Unleveling().visit(expr_debug)
                    print unparse(expr_debug)
                    new_debug = deepcopy(new_ast)
                    new_debug = asttools.Unleveling().visit(new_debug)
                    print unparse(new_debug)
                    print "before:   ", ast.dump(expr_ast)
                    print "pattern:  ", ast.dump(pattern)
                    patt_debug = asttools.Unleveling().visit(deepcopy(pattern))
                    print unparse(patt_debug)
                    print ""
                    print ""
                    print "after:    ", ast.dump(new_ast)
                    print ""
            expr_ast = new_ast
        # bitwise simplification: this is ugly, should be "generalized"
        expr_ast = asttools.LevelOperators(ast.BitXor).visit(expr_ast)
        expr_ast = asttools.ConstFolding(expr_ast,
                                         2**self.nbits).visit(expr_ast)
        expr_ast = asttools.Unleveling().visit(expr_ast)
        if DEBUG:
            print "after PM: "
            print unparse(expr_ast)
            print ""
        expr_ast = arithm_simpl.main(expr_ast, nbits)
        expr_ast = asttools.GetConstMod(self.nbits).visit(expr_ast)
        if DEBUG:
            print "arithm simpl: "
            print unparse(expr_ast)
            print ""
            print "-"*80
        return expr_ast

    def visit_Assign(self, node):
        'Simplify value of assignment and update context'

        # use EvalPattern to replace known variables
        node.value = pattern_matcher.EvalPattern(
            self.context).visit(node.value)
        old_value = deepcopy(node.value)
        old_value = asttools.LevelOperators().visit(old_value)
        node.value = self.simplify(node.value, self.nbits)
        copyvalue = deepcopy(node.value)
        copyvalue = asttools.LevelOperators().visit(copyvalue)
        # simplify until fixpoint is reached
        while not asttools.Comparator().visit(old_value, copyvalue):
            old_value = deepcopy(node.value)
            node.value = self.simplify(node.value, self.nbits)
            copyvalue = deepcopy(node.value)
            if len(unparse(copyvalue)) > len(unparse(old_value)):
                node.value = deepcopy(old_value)
                break
            copyvalue = asttools.LevelOperators().visit(copyvalue)
            old_value = asttools.LevelOperators().visit(old_value)
        for target in node.targets:
            self.context[target.id] = node.value
        return node

    def visit_Expr(self, node):
        'Simplify expression and replace it'
        old_value = deepcopy(node.value)
        old_value = asttools.LevelOperators().visit(old_value)
        node.value = self.simplify(node.value, self.nbits)
        copyvalue = deepcopy(node.value)
        copyvalue = asttools.LevelOperators().visit(copyvalue)
        # simplify until fixpoint is reached
        while not asttools.Comparator().visit(old_value, copyvalue):
            old_value = deepcopy(node.value)
            old_value = asttools.LevelOperators().visit(old_value)
            node.value = self.simplify(node.value, self.nbits)
            copyvalue = deepcopy(node.value)
            copyvalue = asttools.LevelOperators().visit(copyvalue)
        return node


def simplify(expr, nbits=0, custom_rules=None, use_default=True):
    """
    Take an expression and an optionnal number of bits as input.

    Expression can be given on command line or as a file, and should
    be in cse form (you can use cse script from sspam.tools)

    If not precised, number of bits will be deduced from the highest
    constant of the expression if possible, else it will be 8.

    """

    if os.path.isfile(expr):
        expr_file = open(expr, 'r')
        expr_ast = ast.parse(expr_file.read())
    else:
        expr_ast = ast.parse(expr)

    nbits = nbits
    if not nbits:
        nbits = asttools.get_default_nbits(expr_ast)

    if not use_default:
        rules_list = custom_rules
    elif not custom_rules:
        rules_list = DEFAULT_RULES
    else:
        rules_list = DEFAULT_RULES + custom_rules
    expr_ast = Simplifier(nbits, rules_list).visit(expr_ast)
    return unparse(expr_ast).strip('\n')


if __name__ == "__main__":
    #pylint: disable=invalid-name
    parser = argparse.ArgumentParser()
    parser.add_argument("expr", type=str, help="expression to simplify")
    parser.add_argument("-n", dest="nbits", type=int,
                        help="number of bits of the variables (default is 8)")
    args = parser.parse_args()
    print ""
    print simplify(args.expr, args.nbits)
    print ""
