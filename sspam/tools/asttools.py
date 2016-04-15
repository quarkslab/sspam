import ast
import copy
import operator

import leveling


def flatten(l):
    'Flatten a list'
    res = []
    for elem in l:
        if isinstance(elem, list):
            res.extend(flatten(elem))
        else:
            res.append(elem)
    return res


def apply_hooks():
    # backup !
    backup_expr_hash = ast.expr.__hash__
    backup_expr_eq = ast.expr.__eq__
    backup_expr_context_hash = ast.expr_context.__hash__
    backup_operator_hash = ast.operator.__hash__

    # used for ast set comparison
    ast.expr.__hash__ = lambda self: hash(tuple(map(hash, flatten([getattr(self, field)
                                                                   for field in self._fields]))))
    ast.expr.__eq__ = lambda self, other: Comparator().visit(self, other)
    ast.expr_context.__hash__ = lambda self: hash(type(self))
    ast.operator.__hash__ = lambda self: hash(type(self))
    ast.unaryop.__hash__ = lambda self: hash(type(self))

    return (backup_expr_hash, backup_expr_eq,
            backup_expr_context_hash, backup_operator_hash)


def restore_hooks(hooks):
    ast.expr.__hash__ = hooks[0]
    ast.expr.__eq__ = hooks[1]
    ast.expr_context.__hash__ = hooks[2]
    ast.operator.__hash__ = hooks[3]


class GetVariables(ast.NodeVisitor):
    """
    Get all identifiers (instances of ast.Name) of an ast.
    """

    def __init__(self):
        'Result contains identifiers of the ast'
        self.result = set()

    def reset(self):
        self.result = set()

    def visit_Name(self, node):
        'Add node id to result'
        self.result.add(node.id)


class GetSize(ast.NodeVisitor):
    """
    Get bitsize of ast: approximate with 2**8, 2**16...
    """

    def __init__(self):
        'Init nbits'
        self.result = 0

    def reset(self):
        self.result = 0

    def visit_Num(self, node):
        'Approximate nbits with n power of two'
        bitlen = (abs(node.n)).bit_length()
        if bitlen > self.result:
            # didn't find a way to do this cleanly...
            if bitlen == 1 or bitlen == 2:
                self.result = bitlen
            elif bitlen == 3 or bitlen == 4:
                self.result = 4
            elif bitlen > 4 and bitlen < 9:
                self.result = 8
            elif bitlen > 8 and bitlen < 17:
                self.result = 16
            elif bitlen > 16  and bitlen < 33:
                self.result = 32
            elif bitlen > 32  and bitlen < 65:
                self.result = 64
            else:
                raise Exception("Nbits not supported")


class GetConstExpr(ast.NodeVisitor):
    """
    Gathers all constant math expressions (with numbers only).
    Used in ConstantFolding.

    Code shamefully stolen from pythran.
    """

    def __init__(self):
        'Result contains all constant expressions'
        self.result = set()

    def reset(self):
        self.result = set()

    def add(self, node):
        'Add a node to result and return True'
        self.result.add(node)
        return True

    # A Num node is constant by definition
    visit_Num = add

    def visit_BinOp(self, node):
        'A BinOp node is a const expr if both its operands are'
        rec = all(map(self.visit, (node.left, node.right)))
        return rec and self.add(node)

    def visit_UnaryOp(self, node):
        'A UnaryOp is a const expr if its operand is'
        return self.visit(node.operand) and self.add(node)


class CheckConstExpr(ast.NodeVisitor):
    """
    Check if given node is exactly a constant expression.
    """

    def visit_Num(self, node):
        return True

    def visit_BinOp(self, node):
        'A BinOp node is a const expr if both its operands are'
        return all(map(self.visit, (node.left, node.right)))

    def visit_BoolOp(self, node):
        'A BoolOp is a const expr if all its operands are'
        return all(map(self.visit, node.values))

    def visit_UnaryOp(self, node):
        'A UnaryOp is a const expr if its operand is'
        return self.visit(node.operand)


class ConstFolding(ast.NodeTransformer):
    """
    Applies constant folding on an ast.
    Also stolen from pythran.
    """

    def __init__(self, node, mod):
        'Gather constant expressions'
        analyzer = GetConstExpr()
        analyzer.visit(node)
        self.constexpr = analyzer.result
        self.mod = mod

    def visit_BinOp(self, node):
        'If node is a constant expression, replace it with its evaluated value'
        if node in self.constexpr:
            # evaluation
            fake_node = ast.Expression(ast.BinOp(node, ast.Mod(),
                                                 ast.Num(self.mod)))
            ast.fix_missing_locations(fake_node)
            code = compile(fake_node, '<constant folding>', 'eval')
            obj_env = globals().copy()
            exec code in obj_env
            value = eval(code, obj_env)

            new_node = ast.Num(value)
            return new_node
        else:
            return self.generic_visit(node)

    def visit_BoolOp(self, node):
        'A custom BoolOp can be used in leveled AST'
        if type(node.op) not in (ast.Add, ast.Mult,
                                 ast.BitXor,ast.BitAnd, ast.BitOr):
            return self.generic_visit(node)
        # get constant parts of node:
        list_cste = [child for child in node.values if isinstance(child, ast.Num)]
        if len(list_cste) < 2:
            return self.generic_visit(node)
        rest_values = [n for n in node.values if n not in list_cste]
        fake_node = ast.Expression(leveling.Unleveling().visit(ast.BoolOp(node.op, list_cste)))
        ast.fix_missing_locations(fake_node)
        code = compile(fake_node, '<constant folding>', 'eval')
        obj_env = globals().copy()
        exec code in obj_env
        value = eval(code, obj_env)

        new_node = ast.Num(value)
        rest_values.append(new_node)
        return ast.BoolOp(node.op, rest_values)

    def visit_UnaryOp(self, node):
        'Same idea as visit_BinOp'
        if node in self.constexpr:
            # evaluation
            fake_node = ast.Expression(ast.BinOp(node, ast.Mod(),
                                                 ast.Num(self.mod)))
            ast.fix_missing_locations(fake_node)
            code = compile(fake_node, '<constant folding>', 'eval')
            obj_env = globals().copy()
            exec code in obj_env

            value = eval(code, obj_env)
            new_node = ast.Num(value)
            return new_node
        else:
            return self.generic_visit(node)


class ReplaceBitwiseOp(ast.NodeTransformer):
    """
    Replace bitwise operations (&, |, ^, ~) with custom functions
    (mand, mor, mxor, mnot) so that expression may be used in sympy.
    """

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.BitAnd):
            return ast.Call(ast.Name('mand', ast.Load()),
                            [node.left, node.right], [], None, None)
        if isinstance(node.op, ast.BitOr):
            return ast.Call(ast.Name('mor', ast.Load()),
                            [node.left, node.right], [], None, None)
        if isinstance(node.op, ast.BitXor):
            return ast.Call(ast.Name('mxor', ast.Load()),
                            [node.left, node.right], [], None, None)
        if isinstance(node.op, ast.LShift):
            return ast.Call(ast.Name('mlshift', ast.Load()),
                            [node.left, node.right], [], None, None)
        if isinstance(node.op, ast.RShift):
            return ast.Call(ast.Name('mrshift', ast.Load()),
                            [node.left, node.right], [], None, None)
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Invert):
            return ast.Call(ast.Name('mnot', ast.Load()),
                            [node.operand], [], None, None)
        return node


class ReplaceBitwiseFunctions(ast.NodeTransformer):
    """
    Replace mand, mxor and mor with their respective operations.
    """

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name):
            if len(node.args) == 2:
                if node.func.id == "mand":
                    op = ast.BitAnd()
                elif node.func.id == "mxor":
                    op = ast.BitXor()
                elif node.func.id == "mor":
                    op = ast.BitOr()
                elif node.func.id == "mlshift":
                    op = ast.LShift()
                elif node.func.id == "mrshift":
                    op = ast.RShift()
                else:
                    return node

                return ast.BinOp(node.args[0],
                                 op,
                                 node.args[1])

            elif len(node.args) == 1 and node.func.id == "mnot":
                arg = node.args[0]
                self.generic_visit(node)
                return ast.UnaryOp(ast.Invert(), arg)

        return self.generic_visit(node)


class GetConstMod(ast.NodeTransformer):
    """
    Replace constants with their value mod 2^n
    """

    def __init__(self, nbits):
        self.nbits = nbits

    def visit_Num(self, node):
        node.n = node.n % 2**self.nbits
        return self.generic_visit(node)


class Comparator(object):
    """
    Compare two ast to check if they're equivalent
    """

    def __init__(self, commut=True):
        'Specify if comparator is commutative or not'
        self.commut = commut

    def visit(self, node1, node2):
        'Call appropriate visitor for matching types'
        if type(node1) != type(node2):
            return False

        # get type of node to call the right visit_ method
        nodetype = node1.__class__.__name__
        comp = getattr(self, "visit_%s" % nodetype, None)

        if not comp:
            raise Exception("no comparison function for %s" % nodetype)
            return False

        return comp(node1, node2)

    def visit_Module(self, node1, node2):
        'Check if body of are equivalent'
        if len(node1.body) != len(node2.body):
            return False
        for i in range(len(node1.body)):
            if not self.visit(node1.body[i], node2.body[i]):
                return False
            return True

    def visit_Expression(self, node1, node2):
        'Check if bodies are the same'
        return self.visit(node1.body, node2.body)

    def visit_Expr(self, node1, node2):
        'Check if value are equivalent'
        return self.visit(node1.value, node2.value)

    def visit_Call(self, node1, node2):
        'Check func id and arguments'
        if node1.func.id != node2.func.id:
            return False
        return all(self.visit(arg1, arg2) for arg1, arg2 in zip(node1.args, node2.args))

    def visit_BinOp(self, node1, node2):
        'Check type of operation and operands'
        if type(node1.op) != type(node2.op):
            return False

        # if operation is commutative, left and right operands are
        # interchangeable
        cond1 = (self.visit(node1.left, node2.left) and
                 self.visit(node1.right, node2.right))
        cond2 = (self.visit(node1.left, node2.right)
                 and self.visit(node1.right, node2.left))

        # non-commutative comparator
        if not self.commut:
            return cond1
        if isinstance(node1.op, (ast.Add, ast.Mult,
                                 ast.BitAnd, ast.BitOr, ast.BitXor)):
            if cond1 or cond2:
                return True
            else:
                return False
        else:
            if cond1:
                return True
        return False

    def visit_BoolOp(self, node1, node2):
        'Check type of operation and operands (not considering order)'

        if type(node1.op) != type(node2.op):
            return False
        if len(node1.values) != len(node2.values):
            return False

        # redefine __hash__ for set comparison
        hooks = apply_hooks()
        # this implies that operation is associative / commutative
        result = set(node1.values) == set(node2.values)
        restore_hooks(hooks)
        return result

    def visit_UnaryOp(self, node1, node2):
        'Check type of operation and operand'
        if type(node1.op) != type(node2.op):
            return False
        return self.visit(node1.operand, node2.operand)

    def visit_Assign(self, node1, node2):
        return (self.visit(node1.targets[0], node2.targets[0])
                and self.visit(node1.value, node2.value))

    def visit_Name(self, node1, node2):
        'Check id'
        return (node1.id == node2.id and type(node1.ctx) == type(node2.ctx))

    def visit_Num(self, node1, node2):
        'Check num value'
        return node1.n == node2.n
