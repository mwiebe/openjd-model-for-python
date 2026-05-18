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
    # Profile types — pass to FunctionLibrary.for_profile(...) and to
    # evaluate_expression / ParsedExpression.evaluate / FormatString.resolve*
    # via the `profile=` kwarg. Mirror openjd_expr's profile module:
    # https://github.com/OpenJobDescription/openjd-rs/blob/main/crates/openjd-expr/src/profile.rs
    ExprProfile,
    ExprRevision,
    ExprExtension,
    HostContext,
)


# Note: the `__module__` / `__name__` / `__qualname__` of the Rust-backed
# exceptions (ExpressionError, FormatStringValidationError, etc.) are set by
# the `_openjd_rs` module init in Rust to their canonical user-facing values
# (e.g. `openjd.expr.ExpressionError`). No Python-side fix-up needed.

__all__ = [
    # Types
    "ExprType",
    "TypeCode",
    "ExprValue",
    "SymbolTable",
    "FunctionLibrary",
    "ParsedExpression",
    "PathMappingRule",
    "PathFormat",
    "RangeExpr",
    "FormatString",
    # Profile
    "ExprProfile",
    "ExprRevision",
    "ExprExtension",
    "HostContext",
    # Functions
    "get_default_library",
    "evaluate_expression",
    "parse_expression",
    "evaluate_let_bindings",
    "escape_format_string",
    # Errors
    "ExpressionError",
    "ExpressionTypeError",
    "RangeExprError",
    "FormatStringValidationError",
    # Constants
    "DEFAULT_MEMORY_LIMIT",
    "DEFAULT_OPERATION_LIMIT",
]
