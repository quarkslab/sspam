#!/usr/bin/python
"""
Level operators in a python AST: a succession of the same
associative operation will be represented with a single node having
multiple operands.
"""

import ast


class LevelOperators(ast.NodeTransformer):
    """
    Walk through the ast and level successions of associative
    operators (+, x, &, |, ^).
    """

    def __init__(self, onlyop=None):
        'Init current operation and storage for leveled nodes and operands'
        self.current_leveling = ast.BinOp(None, None, None)
        self.leveled_op = {}
        self.onlyop = onlyop

    def visit_BinOp(self, node):
        'Transforms BinOp into leveled BoolOp if possible'

        self.leveled_op.setdefault(node, [])
        if self.onlyop and type(node.op) != self.onlyop:
            self.current_leveling = ast.BinOp(None, None, None)
            return self.generic_visit(node)
        if type(node.op) != type(self.current_leveling.op):
            if isinstance(node.op, (ast.Add, ast.Mult, ast.BitAnd,
                                    ast.BitOr, ast.BitXor)):
                cond1 = (isinstance(node.left, ast.BinOp)
                         and type(node.left.op) == type(node.op))
                cond2 = (isinstance(node.right, ast.BinOp)
                         and type(node.right.op) == type(node.op))
                if cond1 or cond2:
                    self.current_leveling = node
                    self.generic_visit(node)
                    if ((not isinstance(node.right, ast.BinOp)
                         or type(node.right.op) != type(node.op))):
                        self.leveled_op[node].append(node.right)
                    if ((not isinstance(node.left, ast.BinOp)
                         or type(node.left.op) != type(node.op))):
                        self.leveled_op[node].append(node.left)
                else:
                    self.generic_visit(node)

        else:
            current_leveling = self.current_leveling
            self.generic_visit(node)
            self.current_leveling = current_leveling
            for child in (node.left, node.right):
                if not (isinstance(child, ast.BinOp) and type(child.op) == type(node.op)):
                    self.leveled_op[self.current_leveling].append(child)

        if self.leveled_op.get(node, None) and len(self.leveled_op[node]) > 1:
            return ast.BoolOp(node.op, self.leveled_op[node])
        return node


class Unleveling(ast.NodeTransformer):
    """
    Change leveled BoolOps back to regular BinOps.
    """

    def visit_BoolOp(self, node):
        'Build a serie of BinOp from BoolOp Children'

        self.generic_visit(node)
        rchildren = node.values[::-1]
        prev = ast.BinOp(rchildren[1], node.op, rchildren[0])

        for child in rchildren[2::]:
            prev = ast.BinOp(child, node.op, prev)

        return prev
