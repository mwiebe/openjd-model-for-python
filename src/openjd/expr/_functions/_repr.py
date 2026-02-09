# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Repr function implementations (repr_sh, repr_py, repr_json)."""

from __future__ import annotations

import json
import shlex

from .._types import TypeCode
from .._value import ExprValue

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


def _repr_sh_path(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    return ExprValue(shlex.quote(p_str))


def _repr_sh_list(ev: Evaluator, args: ExprValue) -> ExprValue:
    # Convert each element to string (handles both string and path types)
    items = args.to_expr_value_list()
    ev._count_operations(len(items))
    return ExprValue(shlex.join(v.to_string() for v in items))


def _repr_py_string(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.item()
    ev._count_string_ops(len(v_str))
    return ExprValue(repr(v_str))


def _repr_py_int(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(repr(v.item()))


def _repr_py_float(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(repr(v.item()))


def _repr_py_bool(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("True" if v.item() else "False")


def _repr_py_path(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.to_string()
    ev._count_string_ops(len(v_str))
    return ExprValue(repr(v_str))


def _repr_json_string(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.item()
    ev._count_string_ops(len(v_str))
    return ExprValue(json.dumps(v_str))


def _repr_json_int(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(json.dumps(v.item()))


def _repr_json_float(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(json.dumps(v.item()))


def _repr_json_bool(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("true" if v.item() else "false")


def _repr_json_null(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("null")


def _repr_json_path(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.to_string()
    ev._count_string_ops(len(v_str))
    return ExprValue(json.dumps(v_str))


def _repr_py_null(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("None")


def _repr_py_list(ev: Evaluator, v: ExprValue) -> ExprValue:
    ev._count_operations(len(v.to_expr_value_list()))
    return ExprValue(repr(_expr_value_to_py(v)))


def _repr_json_list(ev: Evaluator, v: ExprValue) -> ExprValue:
    ev._count_operations(len(v.to_expr_value_list()))
    return ExprValue(json.dumps(_expr_value_to_py(v)))


def _pwsh_quote_string(s: str) -> str:
    """Quote a string for PowerShell using single quotes with '' escaping."""
    return "'" + s.replace("'", "''") + "'"


def _pwsh_repr_value(v: ExprValue) -> str:
    """Convert any ExprValue to its PowerShell representation."""
    tc = v.type.type_code
    if tc == TypeCode.STRING:
        return _pwsh_quote_string(v.item())
    if tc == TypeCode.INT:
        return str(v.item())
    if tc == TypeCode.FLOAT:
        return str(v.item())
    if tc == TypeCode.BOOL:
        return "$true" if v.item() else "$false"
    if tc == TypeCode.PATH:
        return _pwsh_quote_string(str(v.to_string()))
    if tc == TypeCode.RANGE_EXPR:
        return _pwsh_quote_string(v.to_string())
    if tc == TypeCode.LIST:
        items = [_pwsh_repr_value(item) for item in v.to_expr_value_list()]
        return "@(" + ", ".join(items) + ")"
    if tc == TypeCode.NULLTYPE:
        return "$null"
    return _pwsh_quote_string(v.to_string())


def _repr_pwsh_string(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.item()
    ev._count_string_ops(len(v_str))
    return ExprValue(_pwsh_quote_string(v_str))


def _repr_pwsh_int(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(str(v.item()))


def _repr_pwsh_float(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(str(v.item()))


def _repr_pwsh_bool(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("$true" if v.item() else "$false")


def _repr_pwsh_path(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.to_string()
    ev._count_string_ops(len(v_str))
    return ExprValue(_pwsh_quote_string(str(v_str)))


def _repr_pwsh_range_expr(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(_pwsh_quote_string(v.to_string()))


def _repr_py_range_expr(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(repr(v.to_string()))


def _repr_json_range_expr(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(json.dumps(v.to_string()))


def _repr_pwsh_list(ev: Evaluator, v: ExprValue) -> ExprValue:
    item_list = v.to_expr_value_list()
    ev._count_operations(len(item_list))
    items = [_pwsh_repr_value(item) for item in item_list]
    return ExprValue("@(" + ", ".join(items) + ")")


# Inside double quotes, ^ and " need caret escaping, % needs doubling for .bat files
_CMD_SPECIAL = '^"'

# Characters that require the string to be quoted in CMD
_CMD_NEEDS_QUOTING = set(' \t\n\r&|<>^"()%!')


def _cmd_quote_string(s: str) -> str:
    """Quote a string for Windows CMD using double quotes with ^ escaping.

    Simple strings without special characters are returned unquoted.
    Empty strings are always quoted to preserve them as arguments.
    """
    if s and not any(c in _CMD_NEEDS_QUOTING for c in s):
        return s
    escaped = "".join(("^" + c if c in _CMD_SPECIAL else "%%" if c == "%" else c) for c in s)
    return '"' + escaped + '"'


def _repr_cmd_string(ev: Evaluator, v: ExprValue) -> ExprValue:
    v_str = v.item()
    ev._count_string_ops(len(v_str))
    return ExprValue(_cmd_quote_string(v_str))


def _repr_cmd_list(ev: Evaluator, v: ExprValue) -> ExprValue:
    item_list = v.to_expr_value_list()
    ev._count_operations(len(item_list))
    items = [_cmd_quote_string(item.item()) for item in item_list]
    return ExprValue(" ".join(items))


def _expr_value_to_py(v: ExprValue):
    """Convert ExprValue to Python native type for repr/json."""
    tc = v.type.type_code
    if tc == TypeCode.INT:
        return v.item()
    if tc == TypeCode.FLOAT:
        return v.item()
    if tc == TypeCode.STRING:
        return v.item()
    if tc == TypeCode.BOOL:
        return v.item()
    if tc == TypeCode.PATH:
        return v.to_string()
    if tc == TypeCode.RANGE_EXPR:
        return v.to_string()
    if tc == TypeCode.LIST:
        return [_expr_value_to_py(item) for item in v.to_expr_value_list()]
    if tc == TypeCode.NULLTYPE:
        return None
    raise TypeError(f"Cannot convert {v.type} to Python value")
