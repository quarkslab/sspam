"""Module used to compute bit-vector size of each node of an AST.
"""

import ast
import astunparse
import re

from sspam import simplifier
from sspam import arithm_simpl


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
        setattr(node, 'nbits', self.maxnbits)
        return self.generic_visit(node)

    def visit_Call(self, node):
        'bvX(...) is a size indication with X the size'

        match = re.search('bv([0-9]+)$', node.func.id)
        if match:
            if len(node.args) != 1:
                setattr(node, 'nbits', self.maxnbits)
                return self.generic_visit(node.args)
            nbits = int(match.group(1))
            setattr(node.args[0], 'nbits', nbits)
            self.generic_visit(node.args[0])
            return node.args[0]
        # recognized functions
        if node.func.id in {"sspam_rol", "sspam_ror"}:
            self.generic_visit(node)
            setattr(node, 'nbits', getattr(node.args[0], 'nbits'))
            return node
        setattr(node, 'nbits', self.maxnbits)
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        'Deduce the size of the BinOp from the size of its operands'

        self.generic_visit(node)
        try:
            lsize = getattr(node.left, 'nbits')
            rsize = getattr(node.right, 'nbits')
        except AttributeError:
            raise SizeError("Size missing at node %s" % compact_repr(node))
        if lsize != rsize:
            raise SizeError("Arguments of different sizes at node %s"
                            % compact_repr(node))
        setattr(node, 'nbits', max(lsize, rsize))
        return node

    def visit_UnaryOp(self, node):
        'The size of a unary op is the size of its operand'

        self.generic_visit(node)
        setattr(node, 'nbits', getattr(node.operand, 'nbits'))
        return node

    def visit_Name(self, node):
        'Identifiers have maxnbits for a start'

        setattr(node, 'nbits', self.maxnbits)
        return node


expr = """(bv64(0x66FFFFFFF93D8D48) + sign_extend(~(byte_swap(((((ror((Mem32(Addr64((Addr64((Mem64((((((((((((((((((((((Sym0 - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) * bv64(0x00000001)) + bv64(0x00000090))) + bv64(0x00000000))) + bv64(0x100000000)))) ^ (Sym1 | (bv32(0x0001) << bcast((bcast(Sym2, bv32(0x0020)) & bv32(0x001F)),bv32(0x0020))))), bv32(0x0001)) ^ bv32(0x5DC376E0)) - bv32(0x0001)) ^bv32(0x12A41CD3)) + bv32(0x1E186A88)))), bv64(0x00000040)))"""


expr = "(bv64(0x66FFFFFFF93D8D48) + bv64(sign_extend(~(bv32(byte_swap(((((sspam_ror((bv32(Mem32(bv64(Addr64((bv64(Addr64((bv64(Mem64((((((((((((((((((((((bv64(Sym0) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) - bv64(0x00000008)) * bv64(0x00000001)) + bv64(0x00000090)))) + bv64(0x00000000)))) + bv64(0x100000000)))))) ^ (bv32(Sym1) | (bv32(0x0001) << (bv32(Sym2) & bv32(0x001F))))), bv32(0x0001)) ^ bv32(0x5DC376E0))  - bv32(0x0001)) ^ bv32(0x12A41CD3)) + bv32(0x1E186A88))))) , bv64(0x00000040))))"




a = ast.parse(expr)
ComputeBvSize(128).visit(a)
print ast.dump(a)
print astunparse.unparse(a)
print getattr(a.body[0].value, 'nbits')

a = arithm_simpl.run(a, 64)
print astunparse.unparse(a)
# print simplifier.simplify(astunparse.unparse(a))

# print getattr(a.body[0].value.left.left, 'nbits')
