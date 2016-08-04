"""Module to evaluate different operators not existing in Python.
For now, operators will only be evaluated on constant expressions.

Supported operators are:
- sspam_rol
- sspam_ror

"""

import ast

from sspam.tools import asttools


def sspam_rol(val, rbits, maxbits):
    'Rotation to the left'
    upper = (val << rbits) & (2**maxbits - 1)
    lower = (val >> (maxbits - (rbits % maxbits)))
    return upper | lower


def sspam_ror(val, rbits, maxbits):
    'Rotation to the right'
    lower = (val >> rbits % maxbits)
    upper = (val << (maxbits - (rbits % maxbits)) & (2**maxbits - 1))
    return upper | lower

KNOWN_OPERATORS = [sspam_rol, sspam_ror]


class EvaluateOperators(ast.NodeTransformer):
    """
    If operator is in KNOWN_OPERATORS and all arguments are constant
    expressions, evaluates the operator.
    """

    def visit_Call(self, node):
        'Check operator name and if arguments are constant'
        # pylint: disable=no-member,unused-variable

        if node.func.id not in [f.func_name for f in KNOWN_OPERATORS]:
            return self.generic_visit(node)
        for arg in node.args:
            if not asttools.CheckConstExpr().visit(arg):
                return self.generic_visit(node)
        # working for sspam_rol, sspam_ror
        firstop = node.args[0]
        secop = node.args[1]
        maxbits = firstop.nbits
        if not isinstance(firstop, ast.Num):
            firstop = asttools.ConstFolding(firstop,
                                            firstop.nbits).visit(firstop)
        if not isinstance(secop, ast.Num):
            secop = asttools.ConstFolding(secop, secop.nbits).visit(secop)
        rbits = secop.n
        val = firstop.n
        res = eval("%s(val, rbits, maxbits)" % node.func.id)
        return ast.Num(res)


# a = ast.parse('sspam_rol(33 + 1, 3)')
# setattr(a.body[0].value.args[0], 'nbits', 8)
# a = EvaluateOperators().visit(a)
# print ast.dump(a)
# print astunparse.unparse(a)
