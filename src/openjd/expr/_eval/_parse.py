# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Expression parsing and static analysis."""

from __future__ import annotations

import ast
import secrets
import string
from keyword import kwlist
from typing import Optional

from .._errors import ExpressionError


class _FixupRenamedKeywordsVisitor(ast.NodeTransformer):
    """Restores original keyword names in attribute positions after parsing."""

    def __init__(self, keywords_renamed: dict[str, str]):
        self._rename = {value: key for key, value in keywords_renamed.items()}
        super().__init__()

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        value = self.visit(node.value)
        attr = self._rename.get(node.attr, node.attr)
        return ast.Attribute(value=value, attr=attr, ctx=node.ctx)


class _AdjustLineNumbersVisitor(ast.NodeTransformer):
    """Adjusts line numbers after wrapping expression in parentheses."""

    def __init__(self, offset: int):
        self._offset = offset
        super().__init__()

    def visit(self, node: ast.AST) -> ast.AST:
        if hasattr(node, "lineno"):
            node.lineno = node.lineno + self._offset
        if hasattr(node, "end_lineno") and node.end_lineno is not None:
            node.end_lineno = node.end_lineno + self._offset
        return super().visit(node)


def ast_parse_keyword_context(source: str) -> ast.AST:
    """Parse with context-sensitive keywords: Python keywords are allowed after '.'.

    Wraps multi-line expressions in parentheses to allow implicit line continuation,
    then adjusts line numbers back.
    """
    keywords_renamed: dict[str, str] = {}
    sub_chars = string.ascii_letters + string.digits
    # Only wrap if multi-line (to allow implicit line continuation)
    is_multiline = "\n" in source
    if is_multiline:
        wrapped = f"(\n{source}\n)"
    else:
        wrapped = source
    working_source = wrapped
    while True:
        try:
            ast_node: ast.AST = ast.parse(working_source, mode="eval")
            if keywords_renamed:
                ast_node = _FixupRenamedKeywordsVisitor(keywords_renamed).visit(ast_node)
            # Adjust line numbers back if we wrapped
            if is_multiline:
                ast_node = _AdjustLineNumbersVisitor(-1).visit(ast_node)
                ast.fix_missing_locations(ast_node)
            _validate_string_literals(ast_node, source)
            _validate_allowed_ast_nodes(ast_node, source)
            return ast_node
        except SyntaxError as exc:
            # Adjust error line number for the wrapping
            if is_multiline and exc.lineno is not None:
                exc.lineno -= 1
            if is_multiline and hasattr(exc, "end_lineno") and exc.end_lineno is not None:
                exc.end_lineno -= 1

            # Convert line/offset to absolute position in original source
            abs_offset = None
            if exc.lineno is not None and exc.offset is not None and exc.lineno >= 1:
                lines = source.split("\n")
                if exc.lineno <= len(lines):
                    abs_offset = sum(len(lines[i]) + 1 for i in range(exc.lineno - 1)) + exc.offset

            kw_start = None
            if abs_offset is not None and abs_offset >= 2 and source[abs_offset - 2] == ".":
                kw_start = abs_offset - 1
            else:
                # Try end_offset (added in Python 3.10)
                end_lineno = getattr(exc, "end_lineno", None)
                end_offset = getattr(exc, "end_offset", None)
                if end_lineno is not None and end_offset is not None and end_lineno >= 1:
                    lines = source.split("\n")
                    if end_lineno <= len(lines):
                        abs_end = sum(len(lines[i]) + 1 for i in range(end_lineno - 1)) + end_offset
                        if (
                            abs_end >= 1
                            and abs_end - 1 < len(source)
                            and source[abs_end - 1] == "."
                        ):
                            kw_start = abs_end

            if kw_start is not None:
                kw_end = kw_start
                while kw_end < len(source) and (source[kw_end].isalnum() or source[kw_end] == "_"):
                    kw_end += 1
                keyword = source[kw_start:kw_end]

                if keyword in kwlist:
                    keyword_sub = keywords_renamed.get(keyword)
                    if not keyword_sub:
                        while True:
                            keyword_sub = secrets.choice(string.ascii_letters) + "".join(
                                secrets.choice(sub_chars) for _ in range(len(keyword) - 1)
                            )
                            if keyword_sub not in source:
                                break
                        keywords_renamed[keyword] = keyword_sub
                    source = source[:kw_start] + keyword_sub + source[kw_end:]
                    # Rebuild wrapped source if multi-line
                    working_source = f"(\n{source}\n)" if is_multiline else source
                    continue
            raise


def _validate_string_literals(node: ast.AST, source: str) -> None:
    """Validate that no unsupported string prefixes are used."""
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and getattr(child, "kind", None) == "u":
            raise ExpressionError(
                "Unicode string prefix u'...' is not supported. Use '...' or \"...\" instead.",
                expr=source,
                node=child,
            )
        if isinstance(child, ast.Constant) and isinstance(child.value, bytes):
            raise ExpressionError(
                "Byte strings (b'...') are not supported. Use '...' or \"...\" instead.",
                expr=source,
                node=child,
            )
        if isinstance(child, ast.Constant) and child.value is ...:
            raise ExpressionError(
                "Ellipsis (...) is not supported",
                expr=source,
                node=child,
            )


# The set of AST node types that the EXPR grammar allows.
_ALLOWED_AST_NODES = frozenset(
    {
        ast.Expression,  # Root wrapper from ast.parse(mode="eval")
        ast.IfExp,  # x if cond else y
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.Not,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.Subscript,
        ast.Slice,
        ast.Call,
        ast.Attribute,
        ast.Name,
        ast.Load,  # Context node (always present)
        ast.Store,  # Context node for comprehension targets
        ast.Constant,
        ast.List,
        ast.ListComp,
        ast.comprehension,
    }
)

# Descriptive names for rejected node types
_REJECTED_NODE_DESCRIPTIONS: dict[type, str] = {
    ast.Lambda: "Lambda expressions are not supported",
    ast.Dict: "Dict literals are not supported",
    ast.Set: "Set literals are not supported",
    ast.SetComp: "Set comprehensions are not supported",
    ast.DictComp: "Dict comprehensions are not supported",
    ast.GeneratorExp: "Generator expressions are not supported; use a list comprehension",
    ast.Tuple: "Tuple literals are not supported; use a list",
    ast.NamedExpr: "Walrus operator (:=) is not supported",
    ast.Starred: "Star unpacking is not supported",
    ast.JoinedStr: "f-strings are not supported; use string concatenation",
    ast.FormattedValue: "f-strings are not supported; use string concatenation",
    ast.Await: "Await expressions are not supported",
    ast.BitAnd: "Bitwise AND (&) is not supported",
    ast.BitOr: "Bitwise OR (|) is not supported",
    ast.BitXor: "Bitwise XOR (^) is not supported",
    ast.Invert: "Bitwise NOT (~) is not supported",
    ast.LShift: "Left shift (<<) is not supported",
    ast.RShift: "Right shift (>>) is not supported",
    ast.MatMult: "Matrix multiply (@) is not supported",
    ast.Is: "'is' operator is not supported; use '=='",
    ast.IsNot: "'is not' operator is not supported; use '!='",
    ast.keyword: "Keyword arguments are not supported",
}


def _validate_allowed_ast_nodes(node: ast.AST, source: str) -> None:
    """Validate that the AST only contains node types allowed by the EXPR grammar."""
    for child in ast.walk(node):
        node_type = type(child)
        if node_type not in _ALLOWED_AST_NODES:
            desc = _REJECTED_NODE_DESCRIPTIONS.get(node_type)
            if desc is None:
                desc = f"{node_type.__name__} is not supported"
            raise ExpressionError(
                desc, expr=source, node=child if isinstance(child, ast.expr) else None
            )

    # Additional structural checks that can't be caught by node type alone
    for child in ast.walk(node):
        # Reject multiple generators in list comprehensions
        if isinstance(child, ast.ListComp) and len(child.generators) > 1:
            raise ExpressionError(
                "Multiple 'for' clauses in list comprehensions are not supported",
                expr=source,
                node=child,
            )
        # Reject multiple 'if' clauses in a single generator
        if isinstance(child, ast.comprehension) and len(child.ifs) > 1:
            raise ExpressionError(
                "Multiple 'if' clauses in a list comprehension are not supported; combine with 'and'",
                expr=source,
                node=child,
            )
        # Reject tuple unpacking in comprehension target
        if isinstance(child, ast.comprehension) and not isinstance(child.target, ast.Name):
            raise ExpressionError(
                "Tuple unpacking in list comprehension is not supported",
                expr=source,
                node=child.target if isinstance(child.target, ast.expr) else None,
            )
        # Reject loop variables that don't start with lowercase or underscore
        if isinstance(child, ast.comprehension) and isinstance(child.target, ast.Name):
            var_name = child.target.id
            if var_name and not (var_name[0].islower() or var_name[0] == "_"):
                raise ExpressionError(
                    f"Loop variable '{var_name}' must start with a lowercase letter or underscore",
                    expr=source,
                    node=child.target,
                )
        # Reject star args in calls
        if isinstance(child, ast.Call):
            for arg in child.args:
                if isinstance(arg, ast.Starred):
                    raise ExpressionError(
                        "Star arguments (*args) are not supported in function calls",
                        expr=source,
                        node=arg,
                    )


def normalize_json_literals(node: ast.AST) -> ast.AST:
    """Transform null/true/false to Python equivalents."""
    if isinstance(node, ast.Name):
        if node.id == "null":
            return ast.Constant(value=None)
        if node.id == "true":
            return ast.Constant(value=True)
        if node.id == "false":
            return ast.Constant(value=False)
    return node


def collect_symbol_references(node: ast.AST) -> set[str]:
    """Collect all symbol references (Name and Attribute chains) from an AST.

    Excludes loop variables defined in list comprehensions.
    """
    symbols: set[str] = set()
    local_vars: set[str] = set()  # Track loop variables

    def collect_name_path(n: ast.AST) -> Optional[str]:
        if isinstance(n, ast.Name):
            return n.id
        if isinstance(n, ast.Attribute):
            base = collect_name_path(n.value)
            if base is not None:
                return f"{base}.{n.attr}"
        return None

    def visit(n: ast.AST) -> None:
        n = normalize_json_literals(n)
        if isinstance(n, ast.Name):
            if n.id not in local_vars:
                symbols.add(n.id)
        elif isinstance(n, ast.Attribute):
            path = collect_name_path(n)
            if path:
                # Check if the base name is a local variable
                base = path.split(".")[0]
                if base not in local_vars:
                    symbols.add(path)
            else:
                visit(n.value)
        elif isinstance(n, ast.Expression):
            visit(n.body)
        elif isinstance(n, ast.BinOp):
            visit(n.left)
            visit(n.right)
        elif isinstance(n, ast.UnaryOp):
            visit(n.operand)
        elif isinstance(n, ast.Compare):
            visit(n.left)
            for comp in n.comparators:
                visit(comp)
        elif isinstance(n, ast.BoolOp):
            for v in n.values:
                visit(v)
        elif isinstance(n, ast.IfExp):
            visit(n.test)
            visit(n.body)
            visit(n.orelse)
        elif isinstance(n, ast.Call):
            # For method calls like x.upper(), visit the base (x) not the method name
            # For function calls like string(x), don't visit the function name
            if isinstance(n.func, ast.Attribute):
                visit(n.func.value)
            # else: n.func is ast.Name - don't visit it (it's a function name, not a variable)
            for arg in n.args:
                visit(arg)
        elif isinstance(n, ast.List):
            for elt in n.elts:
                visit(elt)
        elif isinstance(n, ast.ListComp):
            # First visit the iterables (before adding loop vars to scope)
            for gen in n.generators:
                visit(gen.iter)
            # Add loop variables to local scope
            for gen in n.generators:
                if isinstance(gen.target, ast.Name):
                    local_vars.add(gen.target.id)
            # Now visit element expression and filters (with loop vars in scope)
            visit(n.elt)
            for gen in n.generators:
                for if_ in gen.ifs:
                    visit(if_)
            # Remove loop variables from scope after comprehension
            for gen in n.generators:
                if isinstance(gen.target, ast.Name):
                    local_vars.discard(gen.target.id)
        elif isinstance(n, ast.Subscript):
            visit(n.value)
            if isinstance(n.slice, ast.Slice):
                if n.slice.lower:
                    visit(n.slice.lower)
                if n.slice.upper:
                    visit(n.slice.upper)
                if n.slice.step:
                    visit(n.slice.step)
            else:
                visit(n.slice)

    visit(node)
    return symbols


def collect_local_bindings(node: ast.AST, *, check_shadowing: bool = False) -> set[str]:
    """Collect all local variable names bound in list comprehensions.

    Args:
        node: The AST node to analyze
        check_shadowing: If True, raises ExpressionError if a nested comprehension
            shadows an outer comprehension's variable

    Returns:
        Set of all local variable names bound in comprehensions
    """
    all_bindings: set[str] = set()

    def visit(n: ast.AST, scope: set[str]) -> None:
        if isinstance(n, ast.ListComp):
            # Collect this comprehension's bindings
            comp_bindings: set[str] = set()
            for gen in n.generators:
                if isinstance(gen.target, ast.Name):
                    name = gen.target.id
                    if check_shadowing and name in scope:
                        raise ExpressionError(
                            f"List comprehension variable '{name}' shadows an outer comprehension variable"
                        )
                    comp_bindings.add(name)
                    all_bindings.add(name)

            # Visit nested elements with extended scope
            new_scope = scope | comp_bindings
            visit(n.elt, new_scope)
            for gen in n.generators:
                visit(gen.iter, scope)  # iter is evaluated in outer scope
                for if_ in gen.ifs:
                    visit(if_, new_scope)
        else:
            for child in ast.iter_child_nodes(n):
                visit(child, scope)

    visit(node, set())
    return all_bindings


def collect_called_functions(node: ast.AST) -> set[str]:
    """Collect all function and method names called in an AST."""
    calls: set[str] = set()

    def visit(n: ast.AST) -> None:
        n = normalize_json_literals(n)
        if isinstance(n, ast.Call):
            # Get the function/method name
            if isinstance(n.func, ast.Name):
                calls.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                calls.add(n.func.attr)
                visit(n.func.value)
            for arg in n.args:
                visit(arg)
        elif isinstance(n, ast.Expression):
            visit(n.body)
        elif isinstance(n, ast.BinOp):
            visit(n.left)
            visit(n.right)
        elif isinstance(n, ast.UnaryOp):
            visit(n.operand)
        elif isinstance(n, ast.Compare):
            visit(n.left)
            for comp in n.comparators:
                visit(comp)
        elif isinstance(n, ast.BoolOp):
            for v in n.values:
                visit(v)
        elif isinstance(n, ast.IfExp):
            visit(n.test)
            visit(n.body)
            visit(n.orelse)
        elif isinstance(n, ast.Attribute):
            visit(n.value)
        elif isinstance(n, ast.List):
            for elt in n.elts:
                visit(elt)
        elif isinstance(n, ast.ListComp):
            visit(n.elt)
            for gen in n.generators:
                visit(gen.iter)
                for if_ in gen.ifs:
                    visit(if_)
        elif isinstance(n, ast.Subscript):
            visit(n.value)
            if isinstance(n.slice, ast.Slice):
                if n.slice.lower:
                    visit(n.slice.lower)
                if n.slice.upper:
                    visit(n.slice.upper)
                if n.slice.step:
                    visit(n.slice.step)
            else:
                visit(n.slice)

    visit(node)
    return calls
