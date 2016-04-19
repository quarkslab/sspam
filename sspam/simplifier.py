#!/usr/bin/python
"""Main simplification module.

Works the magic.
"""

import ast
import astunparse
import argparse
import copy
import sys
import os.path

from sspam.tools import asttools, leveling
import pattern_matcher
import pre_processing
import arithm_simpl


# list of known patterns and their replacements
default_rules = [("(A ^ ~B) + 2*(A | B)", "A + B - 1"),
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
                 ("((2*A + 1) & 2*B)", "(2*A & 2*B)"),
                 ("2*(A ^ 127)", "2*(~A)")
]


debug = False


class Simplifier(ast.NodeTransformer):
    """
    Simplifies a succession of assignments.
    For each assignment, simplify the value with :
    - replacing known variables
    - pattern matching
    - arithmetic simplification with z3
    - updating variable value for further replacement
    """

    def __init__(self, nbits, rules_list=default_rules):
        'Init context : correspondance between variables and values'
        self.context = {}
        self.nbits = nbits

        self.patterns = []
        for pattern, replace in rules_list:
            patt_ast = ast.parse(pattern, mode="eval").body
            patt_ast = pre_processing.all_preprocessings(patt_ast, self.nbits)
            patt_ast = leveling.LevelOperators(ast.Add).visit(patt_ast)
            rep_ast = ast.parse(replace, mode="eval").body
            self.patterns.append((patt_ast, rep_ast))

    def simplify(self, expr_ast, nbits):
        'Apply pattern matching and arithmetic simplification'
        if debug:
            print "before: "
            print astunparse.unparse(expr_ast)
            print ""
        expr_ast = pre_processing.all_preprocessings(expr_ast, self.nbits)
        expr_ast = pre_processing.NotToInv().visit(expr_ast)
        expr_ast = leveling.LevelOperators(ast.Add).visit(expr_ast)
        for pattern, replacement in self.patterns:
            rep = pattern_matcher.PatternReplacement(pattern, expr_ast, replacement)
            new_ast = copy.deepcopy(expr_ast)
            new_ast = rep.visit(new_ast)
            if debug:
                if not asttools.Comparator().visit(new_ast, expr_ast):
                    print "replaced! "

                    print astunparse.unparse(leveling.Unleveling().visit(copy.deepcopy(expr_ast)))
                    print astunparse.unparse(leveling.Unleveling().visit(copy.deepcopy(new_ast)))
                    print "before:   ", ast.dump(expr_ast)
                    print "pattern:  ", ast.dump(pattern)
                    print astunparse.unparse(leveling.Unleveling().visit(copy.deepcopy(pattern)))
                    print ""
                    print ""
                    print "after:    ", ast.dump(new_ast)
                    print ""
            expr_ast = new_ast
        # this is ugly, should be "generalized"
        expr_ast = leveling.LevelOperators(ast.BitXor).visit(expr_ast)
        expr_ast = asttools.ConstFolding(expr_ast,
                                         2**self.nbits).visit(expr_ast)
        expr_ast = leveling.Unleveling().visit(expr_ast)
        if debug:
            print "after PM: "
            print astunparse.unparse(expr_ast)
            print ""
        expr_ast = arithm_simpl.main(expr_ast, nbits)
        expr_ast = asttools.GetConstMod(self.nbits).visit(expr_ast)
        if debug:
            print "arithm simpl: "
            print astunparse.unparse(expr_ast)
            print ""
            print "-"*80
        return expr_ast

    def visit_Assign(self, node):
        'Simplify value of assignment and update context'

        # use EvalPattern to replace known variables
        node.value = pattern_matcher.EvalPattern(
            self.context).visit(node.value)
        old_value = copy.deepcopy(node.value)
        node.value = self.simplify(node.value, self.nbits)
        # simplify until fixpoint is reached
        while not asttools.Comparator().visit(old_value, node.value):
            old_value = copy.deepcopy(node.value)
            node.value = self.simplify(node.value, self.nbits)
        for target in node.targets:
            self.context[target.id] = node.value
        return node

    def visit_Expr(self, node):
        old_value = copy.deepcopy(node.value)
        node.value = self.simplify(node.value, self.nbits)
        # simplify until fixpoint is reached
        while not asttools.Comparator().visit(old_value, node.value):
            old_value = copy.deepcopy(node.value)
            node.value = self.simplify(node.value, self.nbits)
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
        getsize = asttools.GetSize()
        getsize.visit(expr_ast)
        if getsize.result:
            nbits = getsize.result
        else:
            # default bitsize is 8
            nbits = 8

    if not use_default:
        rules_list = custom_rules
    elif not custom_rules:
        rules_list = default_rules
    else:
        rules_list = default_rules + custom_rules
    expr_ast = Simplifier(nbits, rules_list).visit(expr_ast)
    return astunparse.unparse(expr_ast).strip('\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("expr", type=str, help="expression to simplify")
    parser.add_argument("-n", dest="nbits", type=int,
                        help="number of bits of the variables (default is 8)")
    args = parser.parse_args()
    print ""
    print simplify(args.expr, args.nbits)
    print ""
