"""Pattern matching module.

This module contains classes to detect a pattern in an expression, and
eventually replace it with another expression if found.

Classes and methods included in this module are:
 - EvalPattern: replace wildcards in a pattern with their supposed
   values
 - PatternMatcher: return true if pattern is matched exactly on
   expression
 - PatternReplacement: take pattern, replacement expression and target
   expression as input ; if pattern is found in target expression,
   replace it with replacement expression
 - match: same as PatternMatcher, but with pre-processing applied
   first
"""


import ast
import copy
import itertools
import astunparse

try:
    import z3
except ImportError:
    raise Exception("z3 module is needed to use this pattern matcher")

from tools import asttools
import pre_processing


class EvalPattern(ast.NodeTransformer):
    """
    Replace wildcards in pattern with supposed values.
    """

    def __init__(self, wildcards):
        self.wildcards = wildcards

    def visit_Name(self, node):
        'Replace wildcards with supposed value'
        if node.id in self.wildcards:
            return copy.deepcopy(self.wildcards[node.id])
        return node


class PatternMatcher(asttools.Comparator):
    """
    Try to match desired pattern with given ast.
    Wildcards are indicated with upper letters : A, B, ...
    Example : A + B will match (x | 34) + (y*67)
    """

    def __init__(self, root, pattern_ast, nbits=0):
        'Init different components of pattern matcher'

        super(PatternMatcher, self).__init__()

        # wildcards used in the pattern with their possible values
        self.wildcards = {}
        # wildcards <-> values that are known not to work
        self.no_solution = []
        # potential no_solutions for node other than root
        self.pot_no_sol = []
        # wildcards <-> value permutations
        self.perms = None

        # root node of expression
        if isinstance(root, ast.Module):
            self.root = root.body[0].value
        elif isinstance(root, ast.Expression):
            self.root = root.body
        else:
            self.root = root

        # compute nb of bits if not indicated by user
        if not nbits:
            getsize = asttools.GetSize()
            getsize.visit(self.root)
            if getsize.result:
                self.nbits = getsize.result
            # default bitsize is 8
            else:
                self.nbits = 8
        else:
            self.nbits = nbits

        # variables for z3 evaluation
        getvar = asttools.GetVariables()
        getvar.visit(self.root)
        self.variables = getvar.result

        # list of used wildcards
        getwild = asttools.GetVariables()
        getwild.visit(pattern_ast)
        self.list_wildcards = [c for c in getwild.result if c.isupper()]

    def check_eq_z3(self, node1, node2):
        'Check equivalence with z3'

        for var in self.variables:
            exec("%s = z3.BitVec('%s', %d)" % (var, var, self.nbits))
        target_ast = copy.deepcopy(node1)
        target_ast = asttools.Unleveling().visit(target_ast)
        ast.fix_missing_locations(target_ast)
        code1 = compile(ast.Expression(target_ast), '<string>', mode='eval')
        eval_pattern = copy.deepcopy(node2)
        EvalPattern(self.wildcards).visit(eval_pattern)
        eval_pattern = asttools.Unleveling().visit(eval_pattern)
        ast.fix_missing_locations(eval_pattern)
        gvar = asttools.GetVariables()
        gvar.visit(eval_pattern)
        if gvar.result.intersection(set(self.list_wildcards)) != set():
            # do not check if all patterns have not been replaced
            return False
        code2 = compile(ast.Expression(eval_pattern), '<string>', mode='eval')
        sol = z3.Solver()
        if isinstance(eval(code1), int) and eval(code1) == 0:
            # cases where node1 == 0 are too permissive
            return False
        sol.add(eval(code1) != eval(code2))
        return sol.check().r == -1

    def check_wildcard(self, node1, node2):
        'Check wildcard value or affect it'
        if node2.id in self.wildcards:
            exact_comp = asttools.Comparator().visit(self.wildcards[node2.id],
                                                     node1)
            if exact_comp:
                return True
            return self.check_eq_z3(node1, self.wildcards[node2.id])
        else:
            self.wildcards[node2.id] = node1
            return True

    def get_model(self, target, pattern):
        'When target is constant and wildcards have no value yet'

        if target.n == 0:
            # zero is too permissive
            return False

        getwild = asttools.GetVariables()
        getwild.visit(pattern)
        wilds = getwild.result
        # let's reduce the model to one wildcard for now
        # otherwise it adds a lot of checks...
        if len(wilds) > 1:
            return False

        wil = wilds.pop()
        if wil in self.wildcards:
            if not isinstance(self.wildcards[wil], ast.Num):
                return False
            exec("%s = z3.BitVecVal(%d, %d)" % (wil, self.wildcards[wil].n,
                                                self.nbits))
        else:
            exec("%s = z3.BitVec('%s', %d)" % (wil, wil, self.nbits))
        eval_pattern = copy.deepcopy(pattern)
        eval_pattern = asttools.Unleveling().visit(eval_pattern)
        ast.fix_missing_locations(eval_pattern)
        code2 = compile(ast.Expression(eval_pattern), '<string>', mode='eval')
        sol = z3.Solver()
        sol.add(target.n == eval(code2))
        if sol.check().r == 1:
            m = sol.model()
            for inst in m.decls():
                self.wildcards[str(inst)] = ast.Num(int(m[inst].as_long()))
            return True
        return False

    def check_pattern(self, target, pattern):
        'Try to match pattern written in different ways'

        if asttools.CheckConstExpr().visit(pattern):
            if isinstance(target, ast.Num):
                # if pattern is only a constant, evaluate and compare
                # to target
                pattcopy = copy.deepcopy(pattern)
                eval_pat = asttools.ConstFolding(pattcopy,
                                                 2**self.nbits).visit(pattcopy)
                return self.visit(target, eval_pat)

        if isinstance(target, ast.Num):
            # check that wildcards in pattern have not been affected
            return self.get_model(target, pattern)

        # deal with NOT that could have been evaluated before
        if isinstance(pattern, ast.UnaryOp):
            conds = (isinstance(pattern.op, ast.Invert) and
                     isinstance(pattern.operand, ast.Name) and
                     pattern.operand.id.isupper())
            if conds:
                wkey = pattern.operand.id
                if isinstance(target, ast.Num):
                    if wkey not in self.wildcards:
                        mod = 2**self.nbits
                        self.wildcards[wkey] = ast.Num((~target.n) % mod)
                        return True
                    else:
                        wilds2 = self.wildcards[pattern.operand.id]
                        num = ast.Num((~target.n) % 2**self.nbits)
                        return asttools.Comparator().visit(wilds2, num)
                else:
                    if wkey not in self.wildcards:
                        self.wildcards[wkey] = ast.UnaryOp(ast.Invert(),
                                                           target)
                        return True
            return self.check_eq_z3(target, pattern)

        # deal with (-1)*B that could have been evaluated
        condpatt = (isinstance(pattern, ast.BinOp)
                    and isinstance(pattern.op, ast.Mult)
                    and isinstance(pattern.left, ast.Num)
                    and pattern.left.n == -1
                    and isinstance(pattern.right, ast.Name)
                    and pattern.right.id.isupper())
        if condpatt:
            wkey = pattern.right.id
            if isinstance(target, ast.Num):
                if wkey not in self.wildcards:
                    mod = 2**self.nbits
                    self.wildcards[wkey] = ast.Num((-target.n) % mod)
                    return True
                else:
                    wilds2 = self.wildcards[pattern.right.id]
                    num = ast.Num((-target.n) % 2**self.nbits)
                    return asttools.Comparator().visit(wilds2, num)
            else:
                if wkey not in self.wildcards:
                    self.wildcards[wkey] = ast.BinOp(ast.Num(-1),
                                                     ast.Mult(), target)
                    return True

        # deal with 2* something
        if isinstance(pattern, ast.BinOp) and isinstance(pattern.op, ast.Mult):
            if isinstance(pattern.left, ast.Num) and pattern.left.n == 2:
                operand = pattern.right
            elif isinstance(pattern.right, ast.Num) and pattern.right.n == 2:
                operand = pattern.left
            else:
                return False

            # deal with case where wildcard operand and target are const values
            if isinstance(target, ast.Num) and isinstance(operand, ast.Name):
                conds = (operand.id in self.wildcards and
                         isinstance(self.wildcards[operand.id], ast.Num))
                if conds:
                    eva = (self.wildcards[operand.id].n)*2 % 2**(self.nbits)
                    if eva == target.n:
                        return True
                else:
                    if target.n % 2 == 0:
                        self.wildcards[operand.id] = ast.Num(target.n / 2)
                        return True
                    return False

            # get all wildcards in operand and check if they have value
            getwild = asttools.GetVariables()
            getwild.visit(operand)
            wilds = getwild.result
            for w in wilds:
                if w not in self.wildcards:
                    return False

            return self.check_eq_z3(target, pattern)
        return False

    def visit(self, target, pattern):
        'Deal with corner cases before using classic comparison'

        # if pattern contains is a wildcard, check value against target
        # or affect it
        if isinstance(pattern, ast.Name) and pattern.id.isupper():
            return self.check_wildcard(target, pattern)

        # if types are different, we might be facing the same pattern
        # written differently
        if type(target) != type(pattern):
            return self.check_pattern(target, pattern)

        # get type of node to call the right visit_ method
        nodetype = target.__class__.__name__
        comp = getattr(self, "visit_%s" % nodetype, None)

        if not comp:
            raise Exception("no comparison function for %s" % nodetype)
        c = comp(target, pattern)
        return c

    def visit_Num(self, target, pattern):
        'Check if num values are equal modulo 2**nbits'
        mod = 2**self.nbits
        return (target.n % mod) == (pattern.n % mod)

    def visit_BinOp(self, node1, node2):
        'Check type of operation and operands'

        # print "visiting", node1.op, node2.op

        if type(node1.op) != type(node2.op):
            return self.check_pattern(node1, node2)

        # if operation is commutative, left and right operands are
        # interchangeable
        previous_state = copy.deepcopy(self.wildcards)
        cond1 = (self.visit(node1.left, node2.left) and
                 self.visit(node1.right, node2.right))
        state = asttools.apply_hooks()
        nos = self.wildcards in self.no_solution
        asttools.restore_hooks(state)
        if cond1 and not nos:
            return True
        if nos:
            self.wildcards = copy.deepcopy(previous_state)
        if not cond1 and not nos:
            wildsbackup = copy.deepcopy(self.wildcards)
            self.wildcards = copy.deepcopy(previous_state)
            cond1_prime = (self.visit(node1.right, node2.right) and
                           self.visit(node1.left, node2.left))
            if cond1_prime:
                return True
            else:
                self.wildcards = copy.deepcopy(wildsbackup)

        if isinstance(node1.op, (ast.Add, ast.Mult,
                                 ast.BitAnd, ast.BitOr, ast.BitXor)):
            cond2 = (self.visit(node1.left, node2.right) and
                     self.visit(node1.right, node2.left))
            if cond2:
                return True
            wildsbackup = copy.deepcopy(self.wildcards)
            self.wildcards = copy.deepcopy(previous_state)
            cond2_prime = (self.visit(node1.right, node2.left) and
                           self.visit(node1.left, node2.right))
            if cond2_prime:
                return True
            else:
                self.wildcards = copy.deepcopy(wildsbackup)

            # if those affectations don't work, try with another order
            if node1 == self.root:
                self.no_solution.append(self.wildcards)
                self.wildcards = copy.deepcopy(previous_state)
                cond1 = (self.visit(node1.left, node2.left) and
                         self.visit(node1.right, node2.right))
                if cond1:
                    return True
                cond2 = (self.visit(node1.left, node2.right)
                         and self.visit(node1.right, node2.left))
                return cond1 or cond2
        self.wildcards = copy.deepcopy(previous_state)
        return False

    def visit_BoolOp(self, target, pattern):
        'Match pattern on leveled operators of same length'

        if type(target.op) != type(pattern.op):
            return False
        if len(target.values) != len(pattern.values):
            return False

        # try every combination wildcard <=> value
        old_context = copy.deepcopy(self.wildcards)
        for perm in itertools.permutations(target.values):
            self.wildcards = copy.deepcopy(old_context)
            res = True
            i = 0
            for i in range(len(pattern.values)):
                res &= self.visit(perm[i], pattern.values[i])
            if res:
                return res
        return False


def match(target_str, pattern_str):
    'Apply all pre-processing, then pattern matcher'
    target_ast = ast.parse(target_str, mode="eval").body
    target_ast = pre_processing.all_preprocessings(target_ast)
    target_ast = asttools.LevelOperators(ast.Add).visit(target_ast)
    pattern_ast = ast.parse(pattern_str, mode="eval").body
    pattern_ast = pre_processing.all_preprocessings(pattern_ast)
    pattern_ast = asttools.LevelOperators(ast.Add).visit(pattern_ast)
    return PatternMatcher(target_ast, pattern_ast).visit(target_ast,
                                                         pattern_ast)


class PatternReplacement(ast.NodeTransformer):
    """
    Test if a pattern is included in an expression,
    and replace it if found.
    """

    def __init__(self, patt_ast, target_ast, rep_ast, nbits=0):
        'Pattern ast should have as root: BinOp, BoolOp or UnaryOp'
        if isinstance(patt_ast, ast.Module):
            self.patt_ast = patt_ast.body[0].value
        elif isinstance(patt_ast, ast.Expression):
            self.patt_ast = patt_ast.body
        else:
            self.patt_ast = patt_ast
        if isinstance(rep_ast, ast.Module):
            self.rep_ast = copy.deepcopy(rep_ast.body[0].value)
        elif isinstance(rep_ast, ast.Expression):
            self.rep_ast = copy.deepcopy(rep_ast.body)
        else:
            self.rep_ast = copy.deepcopy(rep_ast)

        if not nbits:
            getsize = asttools.GetSize()
            getsize.visit(target_ast)
            if getsize.result:
                self.nbits = getsize.result
            # default bitsize is 8
            else:
                self.nbits = 8
        else:
            self.nbits = nbits

    def visit_BinOp(self, node):
        'Check if node is matching the pattern; if not, visit children'
        pat = PatternMatcher(node, self.patt_ast, self.nbits)
        matched = pat.visit(node, self.patt_ast)
        if matched:
            repc = copy.deepcopy(self.rep_ast)
            new_node = EvalPattern(pat.wildcards).visit(repc)
            return new_node
        else:
            return self.generic_visit(node)

    def visit_BoolOp(self, node):
        'Check if BoolOp is exaclty matching or contain pattern'

        if isinstance(self.patt_ast, ast.BoolOp):
            if len(node.values) == len(self.patt_ast.values):
                pat = PatternMatcher(node, self.patt_ast, self.nbits)
                matched = pat.visit(node, self.patt_ast)
                if matched:
                    new_node = EvalPattern(pat.wildcards).visit(self.rep_ast)
                    return new_node
                else:
                    return self.generic_visit(node)
            elif len(node.values) > len(self.patt_ast.values):
                # associativity n to m
                for combi in itertools.combinations(node.values,
                                                    len(self.patt_ast.values)):
                    rest = [elem for elem in node.values if not elem in combi]
                    testnode = ast.BoolOp(node.op, list(combi))
                    pat = PatternMatcher(testnode, self.patt_ast, self.nbits)
                    matched = pat.visit(testnode, self.patt_ast)
                    if matched:
                        new = EvalPattern(pat.wildcards).visit(self.rep_ast)
                        new = ast.BoolOp(node.op, [new] + rest)
                        new = asttools.Unleveling().visit(new)
                        return new
            return self.generic_visit(node)

        if isinstance(self.patt_ast, ast.BinOp):
            if type(node.op) != type(self.patt_ast.op):
                return self.generic_visit(node)
            op = node.op
            for combi in itertools.combinations(node.values, 2):
                rest = [elem for elem in node.values if not elem in combi]
                testnode = ast.BinOp(combi[0], op, combi[1])
                pat = PatternMatcher(testnode, self.patt_ast, self.nbits)
                matched = pat.visit(testnode, self.patt_ast)
                if matched:
                    new_node = EvalPattern(pat.wildcards).visit(self.rep_ast)
                    new_node = ast.BoolOp(op, [new_node] + rest)
                    new_node = asttools.Unleveling().visit(new_node)
                    return new_node
        return self.generic_visit(node)


def replace(target_str, pattern_str, replacement_str):
    'Apply pre-processing and replace'
    target_ast = ast.parse(target_str, mode="eval").body
    target_ast = pre_processing.all_preprocessings(target_ast)
    target_ast = pre_processing.NotToInv().visit(target_ast)
    target_ast = asttools.LevelOperators(ast.Add).visit(target_ast)
    patt_ast = ast.parse(pattern_str, mode="eval").body
    patt_ast = pre_processing.all_preprocessings(patt_ast)
    patt_ast = asttools.LevelOperators(ast.Add).visit(patt_ast)
    rep_ast = ast.parse(replacement_str)

    rep = PatternReplacement(patt_ast, target_ast, rep_ast)
    return rep.visit(target_ast)


if __name__ == '__main__':
    patt_string = "A + B + (~A & ~B)"
    test = "x + y + (~x & y)"
    rep = "(A & B) - 1"

    # print match(test, patt_string)
    # print "-"*80
    res = replace(test, patt_string, rep)
    print ast.dump(res)
    print astunparse.unparse(res)
