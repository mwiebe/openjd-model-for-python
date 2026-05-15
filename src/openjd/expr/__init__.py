# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenJD Expression Language — Rust-backed implementation."""

from openjd._openjd_rs import (
    evaluate_let_bindings,
    ExprType,
    ExprValue,
    SymbolTable,
    FunctionLibrary,
    get_default_library,
    evaluate_expression,
    parse_expression,
    ParsedExpression,
    ExpressionError,
    ExpressionTypeError,
    PathMappingRule,
    PathFormat,
    RangeExpr,
    RangeExprError,
    FormatString,
    FormatStringValidationError,
    escape_format_string,
    TypeCode,
    DEFAULT_MEMORY_LIMIT,
    DEFAULT_OPERATION_LIMIT,
)


# Note: the `__module__` / `__name__` / `__qualname__` of the Rust-backed
# exceptions (ExpressionError, FormatStringValidationError, etc.) are set by
# the `_openjd_rs` module init in Rust to their canonical user-facing values
# (e.g. `openjd.expr.ExpressionError`). No Python-side fix-up needed.

__all__ = [
    "ExprType",
    "TypeCode",
    "ExprValue",
    "SymbolTable",
    "FunctionLibrary",
    "get_default_library",
    "evaluate_expression",
    "parse_expression",
    "ParsedExpression",
    "ExpressionError",
    "ExpressionTypeError",
    "PathMappingRule",
    "PathFormat",
    "RangeExpr",
    "RangeExprError",
    "FormatString",
    "FormatStringValidationError",
    "escape_format_string",
    "evaluate_let_bindings",
    "DEFAULT_MEMORY_LIMIT",
    "DEFAULT_OPERATION_LIMIT",
]
