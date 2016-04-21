"""Arithmetic simplification module using sympy.

This module simplifies symbolic expressions using only arithmetic operators.
"""
#pylint: disable=unused-import,exec-used
import ast
import sympy
import copy

from sspam.tools import asttools


def main(expr_ast, nbits):
    'Apply sympy arithmetic simplifications to expression ast'

    # variables for sympy symbols
    getvar = asttools.GetVariables()
    getvar.visit(expr_ast)
    variables = getvar.result

    original_type = type(expr_ast)
    # copying to avoid wierd pointer behaviour
    expr_ast = copy.deepcopy(expr_ast)
    # converting expr_ast into an ast.Expression
    if not isinstance(expr_ast, ast.Expression):
        if isinstance(expr_ast, ast.Module):
            expr_ast = ast.Expression(expr_ast.body[0].value)
        elif isinstance(expr_ast, ast.Expr):
            expr_ast = ast.Expression(expr_ast.value)
        else:
            expr_ast = ast.Expression(expr_ast)

    for var in variables:
        exec("%s = sympy.Symbol('%s')" % (var, var))
    for fun in {"mxor", "mor", "mand", "mnot", "mrshift", "mlshift"}:
        exec("%s = sympy.Function('%s')" % (fun, fun))
    expr_ast = asttools.ReplaceBitwiseOp().visit(expr_ast)
    ast.fix_missing_locations(expr_ast)
    code = compile(expr_ast, '<test>', mode='eval')
    eval_expr = eval(code)
    try:
        expr_ast = ast.parse(str(eval_expr))
    except SyntaxError as ex:
        print ex
        exit(1)

    expr_ast = asttools.ReplaceBitwiseFunctions().visit(expr_ast)
    # sympy does not consider the number of bits
    expr_ast = asttools.GetConstMod(nbits).visit(expr_ast)

    # return original type
    if original_type == ast.Expression:
        expr_ast = ast.Expression(expr_ast.body[0].value)
    elif original_type == ast.Expr:
        expr_ast = expr_ast.body[0]
    elif original_type in {ast.BinOp, ast.UnaryOp}:
        expr_ast = expr_ast.body[0].value

    return expr_ast
