"""Module used to compute bit-vector size of each node of an AST.
"""

import ast
import re


class SizeError(Exception):
    """
    Used when a size is missing on a node
    """
    pass


def compact_repr(node):
    'Compact representation of node for error display'
    return ast.dump(node)[:50] + "..." + ast.dump(node)[-50:]


def getbvsize(node):
    'Function used to quicker access bvsize'
    return getattr(node, 'bvsize')


class ComputeBvSize(ast.NodeTransformer):
    """
    Compute bv size of a node and add it as an attribute.
    """

    def __init__(self, maxnbits):
        self.maxnbits = maxnbits

    def visit_Module(self, node):
        'Module stores the maxnbits'
        setattr(node, 'bvsize', self.maxnbits)
        return self.generic_visit(node)

    def visit_Expr(self, node):
        'Expr also on maxnbits'
        setattr(node, 'bvsize', self.maxnbits)
        return self.generic_visit(node)

    def visit_Expression(self, node):
        'Expression also on maxbits'
        setattr(node, 'bvsize', self.maxnbits)
        return self.generic_visit(node)

    def visit_Call(self, node):
        'bvX(...) is a size indication with X the size'

        match = re.search('bv([0-9]+)$', node.func.id)
        if match:
            if len(node.args) != 1:
                setattr(node, 'bvsize', self.maxnbits)
                return self.generic_visit(node.args)
            bvsize = int(match.group(1))
            setattr(node.args[0], 'bvsize', bvsize)
            self.generic_visit(node.args[0])
            return node.args[0]
        # recognized functions
        if node.func.id in {"sspam_rol", "sspam_ror"}:
            self.generic_visit(node)
            # setattr(node, 'bvsize', getattr(node.args[0], 'bvsize'))
            if isinstance(node.args[2], ast.Num):
                setattr(node, 'bvsize', node.args[2].n)
            else:
                setattr(node, 'bvsize', self.maxnbits)
            return node
        setattr(node, 'bvsize', self.maxnbits)
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        'Deduce the size of the BinOp from the size of its operands'

        self.generic_visit(node)
        lsize = getattr(node.left, 'bvsize')
        try:
            lsize = getattr(node.left, 'bvsize')
            rsize = getattr(node.right, 'bvsize')
        except AttributeError:
            raise SizeError("Size missing at node %s" % compact_repr(node))
#        if lsize != rsize:
#            raise SizeError("Arguments of different sizes at node %s"
#                            % compact_repr(node))
        setattr(node, 'bvsize', max(lsize, rsize))
        return node

    def visit_UnaryOp(self, node):
        'The size of a unary op is the size of its operand'
        self.generic_visit(node)
        setattr(node, 'bvsize', getattr(node.operand, 'bvsize'))
        return node

    def visit_Name(self, node):
        'Identifiers have maxbnbits for a start'
        setattr(node, 'bvsize', self.maxnbits)
        return node

    def visit_Num(self, node):
        'Num have maxbnbits for a start'
        setattr(node, 'bvsize', self.maxnbits)
        return node


class RecomputeBvSize(ast.NodeTransformer):
    """
    Recompute bvsize after a regroup
    """

    def __init__(self, maxbvsize):
        self.max_bvsize = maxbvsize
        self.parent_bvsize = 0

    def visit(self, node):
        'Affect parent size, except for call nodes'
        if not isinstance(node, ast.Call):
            if not self.parent_bvsize:
                setattr(node, 'bvsize', self.max_bvsize)
            else:
                setattr(node, 'bvsize', self.parent_bvsize)
            return self.generic_visit(node)
        else:
            return self.visit_Call(node)

    def visit_Call(self, node):
        'All child of bvX(...) are of size X until new bvX is encountered'
        match = re.search('bv([0-9]+)$', node.func.id)
        if match:
            if len(node.args) != 1:
                return self.generic_visit(node.args)
            bvsize = int(match.group(1))
            backup_bvsize = self.parent_bvsize
            self.parent_bvsize = bvsize
            self.visit(node.args[0])
            self.parent_bvsize = backup_bvsize
            return node.args[0]
        setattr(node, 'bvsize', self.parent_bvsize)
        return self.generic_visit(node)


class ReduceBvSize(ast.NodeTransformer):
    """
    If operands of an And node have different bit-vector sizes, the node
    with the bigger size can be reduced if it contains no function and
    no right shift.
    """

    def __init__(self):
        self.reducing = None

    def visit_BinOp(self, node):
        'Check if node is an And and if operand can be reduced'

        # version without computation of the "real" size of constant
        # nodes
        if not self.reducing:
            if isinstance(node.op, ast.BitAnd):
                lsize = getattr(node.left, 'bvsize')
                rsize = getattr(node.right, 'bvsize')
                if lsize < rsize:
                    setattr(node, 'bvsize', lsize)
                    self.reducing = lsize
                    self.visit(node.right)
                elif rsize < lsize:
                    setattr(node, 'bvsize', rsize)
                    self.reducing = rsize
                    self.visit(node.left)
            return self.generic_visit(node)
        # reducing
        else:
            if isinstance(node.op, ast.RShift):
                return node
            setattr(node, 'bvsize', self.reducing)
            return self.generic_visit(node)

    def visit_UnaryOp(self, node):
        'Reduce node if reduction in progress'
        if self.reducing:
            setattr(node, 'bvsize', self.reducing)
        return self.generic_visit(node)

    def visit_Num(self, node):
        'Reduce node if reduction in progress'
        if self.reducing:
            setattr(node, 'bvsize', self.reducing)
        return node

    def visit_Call(self, node):
        'Interrupting reduction if encountering a call node'

        if self.reducing:
            return node
        else:
            return self.generic_visit(node)


class RegroupBvSize(ast.NodeTransformer):
    """
    Applies bvN indication on biggest subgraph with same size.
    """

    def __init__(self):
        self.parent_bvsize = 0

    def visit(self, node):
        if type(node) in {ast.BinOp, ast.UnaryOp, ast.Num, ast.Call}:
            node_bvsize = getattr(node, 'bvsize')
            if node_bvsize != self.parent_bvsize:
                backup_parentbv = self.parent_bvsize
                self.parent_bvsize = node_bvsize
                self.generic_visit(node)
                self.parent_bvsize = backup_parentbv
                return ast.Call(ast.Name('bv%d' % node_bvsize, ast.Load()),
                                [node], [], None, None)
        return self.generic_visit(node)


class DisplayBvSize(ast.NodeVisitor):
    """
    Display bvsize of nodes.
    """
    # pylint: disable=no-self-use

    def visit_BinOp(self, node):
        'Display BinOp'
        print (type(node.left), node.op, type(node.right),
               ': ', getattr(node, 'bvsize'))
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        'Display UnaryOp'
        print node.op, type(node.operand), ': ', getattr(node, 'bvsize')

    def visit_Num(self, node):
        'Display Num'
        print node.n, ': ', getattr(node, 'bvsize')
