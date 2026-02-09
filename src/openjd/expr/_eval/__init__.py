# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Expression parsing and evaluation."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from ._parse import (
    ast_parse_keyword_context,
    normalize_json_literals,
    collect_symbol_references,
    collect_called_functions,
    collect_local_bindings,
)
from ._evaluator import Evaluator, DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT
from ._parsed_expression import ParsedExpression
from .._errors import ExpressionError
from .._types import ExprType
from .._value import ExprValue
from .._symbol_table import SymbolTable
from .._functions import FunctionLibrary, get_default_library

if TYPE_CHECKING:
    from .._path_mapping import PathFormat

__all__ = [
    "ast_parse_keyword_context",
    "normalize_json_literals",
    "collect_symbol_references",
    "collect_called_functions",
    "Evaluator",
    "ParsedExpression",
    "DEFAULT_MEMORY_LIMIT",
    "DEFAULT_OPERATION_LIMIT",
]


def parse_expression(
    expr: str,
) -> ParsedExpression:
    """Parse an expression and return a ParsedExpression with symbol references.

    Args:
        expr: The expression string to parse

    Returns:
        ParsedExpression with the AST and set of accessed symbols

    Raises:
        ExpressionError: If the expression has a syntax error
    """
    expr_stripped = expr.strip()
    try:
        ast_node = ast_parse_keyword_context(expr_stripped)
    except SyntaxError as e:
        msg = f"Syntax error: {e.msg or 'invalid syntax'}"
        col = (e.offset - 1) if e.offset is not None else None
        raise ExpressionError(msg, expr=expr_stripped, lineno=e.lineno, col_offset=col)

    accessed_symbols = collect_symbol_references(ast_node)
    called_functions = collect_called_functions(ast_node)
    local_bindings = collect_local_bindings(ast_node, check_shadowing=True)
    return ParsedExpression(
        expr_stripped, ast_node, accessed_symbols, called_functions, local_bindings
    )


def evaluate_expression(
    expr: str,
    *,
    values: Optional[SymbolTable | dict[str, Any]] = None,
    library: Optional[FunctionLibrary] = None,
    target_type: Optional[ExprType] = None,
    memory_limit: Optional[int] = None,
    operation_limit: Optional[int] = None,
    path_format: Optional["PathFormat"] = None,
) -> ExprValue:
    """Evaluate an expression string and return the result.

    Args:
        expr: The expression string to evaluate
        values: Symbol table or dict with variable bindings
        library: Function library (uses default if not provided)
        target_type: Optional expected result type for coercion (can be union)
        memory_limit: Maximum memory (bytes) for intermediate values during evaluation.
            Defaults to 100 million bytes.
        operation_limit: Maximum number of operations during evaluation.
            Defaults to 10 million. Each function call counts as 1 operation,
            and iterating through a list adds the number of elements.
        path_format: Controls `path` type behavior:
            - PathFormat.POSIX: Behave like Python's PurePosixPath
            - PathFormat.WINDOWS: Behave like Python's PureWindowsPath
            - None: Behave like Python's PurePath (system native)

    Returns:
        ExprValue containing the evaluated result

    Raises:
        ExpressionError: If the expression is invalid or evaluation fails
    """
    expr_stripped = expr.strip()
    try:
        ast_node = ast_parse_keyword_context(expr_stripped)
    except SyntaxError as e:
        msg = f"Syntax error: {e.msg or 'invalid syntax'}"
        col = (e.offset - 1) if e.offset is not None else None
        raise ExpressionError(msg, expr=expr_stripped, lineno=e.lineno, col_offset=col)

    if values is not None:
        if isinstance(values, dict):
            symtab = SymbolTable(values)
        else:
            symtab = values
        symtabs = [symtab]
    else:
        symtabs = []
    lib = library or get_default_library()
    evaluator = Evaluator(
        symtabs,
        lib,
        expr=expr_stripped,
        memory_limit=memory_limit,
        operation_limit=operation_limit,
        path_format=path_format,
    )
    return evaluator.evaluate(ast_node, target_type)
