"""
CSE script written by Serge!
"""

import ast
import functools
from copy import deepcopy
from time import time
import sys
import os
import itertools
import StringIO

import asttools, unparse


COMMUTATIVE_OPERATORS = ast.Add, ast.Mult, ast.BitOr, ast.BitXor, ast.BitAnd
ASSOCIATIVE_OPERATORS = COMMUTATIVE_OPERATORS
BINARY_OPERATORS = COMMUTATIVE_OPERATORS + (ast.Sub, ast.LShift, ast.RShift, ast.Div)
# some operators are not considered: pow, matmult etc


class UseCount(ast.NodeVisitor):
    '''
    Basic value usage analysis

    Register, for each variable, the number of times it is used,
    based on the same assumptions as in ForwardSubstitute
    '''

    def __init__(self):
        self.result = {}

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.result[node.id] = self.result.get(node.id, 0) + 1

    def run(self, node):
        self.visit(node)
        return self.result


class ForwardSubstitute(ast.NodeTransformer):
    '''
    Perform the typical Forward substitution transformation,
    based on the following strong assumptions:

    * all values are integers (no aliasing)
    * the input consist in a sequence of assignment/ expressions
    * the assignment are in the form id = expr
    * the assigments are in SSA form
    * expressions only consist in binary operators, names and num
    '''

    def __init__(self):
        self.substitutions = {}

    def visit_Assign(self, node):
        '''
        Check if the assignment can be forward subsituted

        In that case register the substitution and prune the statement
        '''
        assert isinstance(node.targets[0], ast.Name) and len(node.targets) == 1
        targetid = node.targets[0].id
        if targetid not in self.use_count:
            return
        # literals can always be propagated
        if isinstance(node.value, ast.Num):
            self.substitutions[targetid] = node.value
            return None
        # identifiers copy are always propagated
        # with extra care to keep the substitution table valid in case of
        # assignment chaining (a = b ; c = a)
        elif isinstance(node.value, ast.Name):
            self.use_count[node.value.id] -= 1
            if self.use_count[node.value.id] > 0:
                # there is at least another use
                self.use_count[targetid] += self.use_count[node.value.id]
                self.use_count[node.value.id] = self.use_count[targetid]


            if node.value.id in self.substitutions:
                sub = self.substitutions[node.value.id]
                if self.use_count[targetid] == 1 or isinstance(sub, (ast.Name, ast.Num)):
                    self.substitutions[targetid] = sub
                    return None
                else:
                    node.value = sub
                    return node
            else:
                self.substitutions[targetid] = node.value
                return None
        # other assignment are only propagated if they are used once
        elif self.use_count[targetid] == 1:
            self.substitutions[targetid] = self.generic_visit(node.value)
            return None
        else:
            return self.generic_visit(node)

    def visit_Name(self, node):
        sub = self.substitutions.get(node.id)
        if sub:
            return deepcopy(sub)
        else:
            return node

    def run(self, node):
        '''
        entry point: perform the needed analyse and run the transformation
        '''
        uc = UseCount()
        self.use_count = uc.run(node)
        self.visit(node)


class UseCount(ast.NodeVisitor):
    '''
    Basic value usage analysis

    Register, for each variable, the number of times it is used,
    based on the same assumptions as in ForwardSubstitute
    '''

    def __init__(self):
        self.result = {}

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.result[node.id] = self.result.get(node.id, 0) + 1

    def run(self, node):
        self.visit(node)
        return self.result


def node_hash(node):
    '''
    Helper function to compute a unique hashable representation of a node
    '''
    if isinstance(node, ast.Name):
        return node.id,
    if isinstance(node, ast.Num):
        return str(node.n),
    if isinstance(node, ast.BinOp):
        children = [node_hash(node.left), node_hash(node.right)]
        if isinstance(node.op, COMMUTATIVE_OPERATORS): # commutative
            children.sort()
        return (type(node.op).__name__,) + tuple(children)
    assert False, 'unhandled node type' + ast.dump(node)


class PromoteUnaryOp(ast.NodeTransformer):

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            # return ast.BinOp(ast.Num(0), ast.Sub(), operand)
            return ast.BinOp(ast.Num(-1), ast.Mult(), operand)
        if isinstance(node.op, ast.Invert):
            return ast.BinOp(ast.Num(-1), ast.Xor(), operand)
        assert False, 'unhandled node type: ' + ast.dump(node)



class Substitute(ast.NodeTransformer):
    '''
    Perform node substitution after cse

    I.e. add extra assigments and use the assigned value in the original expression
    '''

    def __init__(self, prefix, op, term_to_node, rewritten_terms, result_nodes):
        self.prefix = prefix
        self.op = op
        self.rewrite = dict()
        self.assigned_values = set()

        target_ids = set()
        assigns = {}
        for terms_part, result_node in zip(rewritten_terms, result_nodes):
            if result_node in self.rewrite:
                continue
            new_node = None
            ordered_assign_keys = []
            ordered_assign_values = []
            if len(terms_part) == 1 and isinstance(terms_part[0], ast.Name):
                new_node = terms_part[0]
            else:
                for term in terms_part:
                    if term not in assigns:
                        new_id = self.prefix.format(len(assigns))
                        new_subnode = ast.Name(new_id, ast.Load())
                        assigns[term] = new_subnode
                        ordered_assign_keys.append(term)
                        ordered_assign_values.append(new_subnode)
                    else:
                        new_subnode = deepcopy(assigns[term])
                    if new_node:
                        new_node = ast.BinOp(new_node, self.op(), new_subnode)
                    else:
                        new_node = new_subnode

            new_assigns = [ast.Assign([ast.Name(target.id, ast.Store())], value)
                       for target, value
                       in zip(ordered_assign_values, [functools.reduce(lambda x,y:ast.BinOp(x, self.op(), y), [term_to_node[term] for term in terms]) for terms in ordered_assign_keys])
                      ]
            self.rewrite[result_node] = new_node, new_assigns

    def visit_TopLevelStmt(self, node):
        self.new_assigns = []
        candidate_assigns = self.new_assigns + [self.generic_visit(node)]
        new_node = []
        for candidate_assign in candidate_assigns:
            if isinstance(candidate_assign, ast.Assign):
                if candidate_assign.targets[0].id not in self.assigned_values:
                    self.assigned_values.add(candidate_assign.targets[0].id)
                    new_node.append(candidate_assign)
            else:
                new_node.append(candidate_assign)
        del self.new_assigns
        return new_node

    visit_Expr = visit_Assign = visit_TopLevelStmt

    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        rewrite = self.rewrite.get(node)
        if rewrite:
            new_node, new_assigns = rewrite
            for new_assign in new_assigns:
                self.new_assigns.append(new_assign)
            return new_node
        else:
            return node


class GatherOpClasses(ast.NodeVisitor):
    '''
    Builds the sets of associative operations found in the input node
    '''

    def __init__(self, op):
        self.op = op
        self.result = []
        self.result_nodes = []
        self.hash_to_node = {}
        self.hash_to_term = {}
        self.term_to_node = {}

    def to_terms(self):
        terms = []
        for part in self.result:
            terms_part = []
            for node in part:
                nhash = node_hash(node)
                if nhash in self.hash_to_node:
                    term = self.hash_to_term[nhash]
                else:
                    self.hash_to_node[nhash] = node
                    term = len(self.hash_to_term)
                    self.hash_to_term[nhash] = term
                    self.term_to_node[term] = node
                terms_part.append(term)
            terms.append(tuple(terms_part))
        return terms


    def from_terms(self, terms):
        nodes = []
        for terms_part in terms:
            nodes_part = []
            for term in terms_part:
                nodes_part.append(deepcopy(self.term_to_node[term]))
            nodes.append(nodes_part)
        return nodes


    def visit_BinOp(self, node, partial=False):
        if isinstance(node.op, self.op):
            operands = []
            for child in node.left, node.right:
                if isinstance(child, ast.BinOp) and isinstance(child.op, self.op) and self.op in ASSOCIATIVE_OPERATORS:
                    operands.extend(self.visit_BinOp(child, partial=True))
                else:
                    self.visit(child)
                    operands.append(child)
            if not partial:
                self.result_nodes.append(node)
                self.result.append(operands)
            return operands
        else:
            self.generic_visit(node)
            return []



def simple_cse(node, operators=BINARY_OPERATORS, timeout=None):
    def cse_generation(op, generation):
        # just to avoid infinite recursion
        if generation < 30:
            prefix = 'cse{}{}{{}}'.format(generation, op.__name__)
            goc = GatherOpClasses(op)
            goc.visit(node)
            terms = goc.to_terms()
            frequency = {}
            combinations = {}
            if not terms:
                return
            for term in terms:
                combinations[term] = list(itertools.combinations(term, 2))
                for pair in combinations[term]:
                    frequency[pair] = frequency.get(pair, 0) + 1
            max_pair, _ = max(frequency.items(), key=lambda x: x[1])
            if frequency[max_pair] > 1:
                new_terms = []
                for term in terms:
                    new_term = []
                    if max_pair in combinations[term]:
                        new_term.append(tuple(max_pair))
                        remaining = list(term)
                        for elem in max_pair:
                            remaining.remove(elem)
                        if remaining:
                            new_term.append(tuple(remaining))
                    else:
                        new_term.append(tuple(term))
                    new_terms.append(tuple(new_term))

                Substitute(prefix, op, goc.term_to_node, new_terms, goc.result_nodes).visit(node)
                ForwardSubstitute().run(node)
                cse_generation(op, generation + 1)

    for op in operators:
        cse_generation(op, 0)


class PostProcessing(ast.NodeTransformer):
    """
    Actual cse might need some post-processing:

    - remove constant subexpr
    - change final expr in an assign
    """

    def __init__(self):
        self.replace = {}

    def visit_Module(self, node):
        new_body = []
        for elem in node.body:
            nodetype = elem.__class__.__name__
            visitor = getattr(self, "visit_%s" % nodetype, None)
            new_node = visitor(elem)
            if new_node:
                new_body.append(new_node)
        node.body = deepcopy(new_body)
        return node

    def visit_Assign(self, node):
        'Register node id if value is a constant expression'
        if len(node.targets) != 1:
            return self.generic_visit(node)
        if asttools.CheckConstExpr().visit(node.value):
            self.replace[node.targets[0].id] = deepcopy(node.value)
            return None
        return self.generic_visit(node)

    def visit_Name(self, node):
        'Replace id if it points to a constant expr'
        if isinstance(node.ctx, ast.Load) and node.id in self.replace:
            return self.replace[node.id]
        else:
            return node

    def visit_Expr(self, node):
        return ast.Assign([ast.Name('result', ast.Store())], self.generic_visit(node.value))


def apply_cse(expr, outputfile=None):
    """
    Apply CSE on expression file or string
    """

    if os.path.isfile(expr):
        expr_file = open(expr, 'r')
        expr_ast = ast.parse(expr_file.read())
    else:
        expr_ast = ast.parse(expr)

    result_expr = PromoteUnaryOp().visit(expr_ast)
    simple_cse(expr_ast, timeout=None)
    expr_ast = PostProcessing().visit(expr_ast)
    output = StringIO.StringIO()
    unparse.Unparser(expr_ast, output)
    expr = output.getvalue()[1::]
    output.close()
    if outputfile:
        unparse.Unparser(expr_ast, open(outputfile, 'w'))
    return expr


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: %s <input file> [output file]" % sys.argv[0])
        exit(0)

    if len(sys.argv) == 2:
        print apply_cse(sys.argv[1])
    if len(sys.argv) == 3:
        print apply_cse(sys.argv[1], sys.argv[2])