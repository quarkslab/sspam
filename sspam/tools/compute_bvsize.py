"""Module used to compute bit-vector size of each node of an AST.
"""

import ast
import astunparse
import re

from sspam import simplifier
from sspam import arithm_simpl
from sspam.tools import asttools

class SizeError(Exception):
    pass


def compact_repr(node):
    return ast.dump(node)[:50] + "..." + ast.dump(node)[-50:]


class ComputeBvSize(ast.NodeTransformer):
    """
    Computes bv size of a node and add it as an attribute.
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
            setattr(node, 'bvsize', getattr(node.args[0], 'bvsize'))
            return node
        setattr(node, 'bvsize', self.maxnbits)
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        'Deduce the size of the BinOp from the size of its operands'

        self.generic_visit(node)
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
                self.parent_bvsize = node_bvsize
                self.generic_visit(node)
                return ast.Call(ast.Name('bv%d' % node_bvsize, ast.Load()),
                                [node], [], None, None)
        return self.generic_visit(node)


class DisplayBvSize(ast.NodeVisitor):

    def visit_BinOp(self, node):
        print type(node.left), node.op, type(node.right), ': ', getattr(node, 'bvsize')
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        print node.op, type(node.operand), ': ', getattr(node, 'bvsize')

    def visit_Num(self, node):
        print node.n, ': ', getattr(node, 'bvsize')


expr = """(bv64(0x66FFFFFFF93D8D48) + sign_extend(~(byte_swap(((((ror((Mem32(Addr64((Addr64((Mem64((((((((((((((((((((((Sym0 - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) * bv64(0x00000001)) + bv64(0x00000090))) + bv64(0x00000000))) + bv64(0x100000000)))) ^ (Sym1 | (bv32(0x0001) << bcast((bcast(Sym2, bv32(0x0020)) & bv32(0x001F)),bv32(0x0020))))), bv32(0x0001)) ^ bv32(0x5DC376E0)) - bv32(0x0001)) ^bv32(0x12A41CD3)) + bv32(0x1E186A88)))), bv64(0x00000040)))"""


expr = "(bv64(0x66FFFFFFF93D8D48) + bv64(sign_extend(~(bv32(byte_swap(((((sspam_ror((bv32(Mem32(bv64(Addr64((bv64(Addr64((bv64(Mem64((((((((((((((((((((((bv64(Sym0) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) * bv64(0x00000001)) + bv64(0x00000090)))) + bv64(0x00000000)))) + bv64(0x100000000)))))) ^ (bv32(Sym1) | (bv32(0x0001) << (bv32(Sym2) & bv32(0x001F))))), bv32(0x0001)) ^ bv32(0x5DC376E0))  - bv32(0x0001)) ^ bv32(0x12A41CD3)) + bv32(0x1E186A88))))) , bv64(0x00000040))))"

expr = "((((((((((((((((((((((bv64(Sym0) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) * bv64(0x00000001)) + bv64(0x00000090)))"


#a = ast.parse(expr)
#ComputeBvSize(128).visit(a)
#print ast.dump(a)
#print astunparse.unparse(a)
#print getattr(a.body[0].value, 'bvsize')
#
#a = arithm_simpl.run(a, 64)
#print astunparse.unparse(a)
# print simplifier.simplify(astunparse.unparse(a))

# print getattr(a.body[0].value.left.left, 'nbits')

expr = "(bv32(rol(Sym0 + bv32(1))) - bv32(8) - bv32(8))*bv32(256) & bv8(0xFF)"
print expr
a = ast.parse(expr)
ComputeBvSize(32).visit(a)
DisplayBvSize().visit(a)
print "-"*80
ReduceBvSize().visit(a)
DisplayBvSize().visit(a)
print astunparse.unparse(a)
print getattr(a.body[0].value.left.right, 'bvsize')

RegroupBvSize().visit(a)
print astunparse.unparse(a)


# bv8((((bv32(rol((Sym0 + 1))) - bv8(8)) - 8) * 256) & 255)
