# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Arithmetic function implementations."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .._value import ExprValue
from .._errors import ExpressionError
from .._uri_path import is_uri, uri_join

if TYPE_CHECKING:
    from .._eval import Evaluator


def _add_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(a.item() + b.item())


def _add_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(a.item() + b.item())


def _add_string(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    result_size = a.memory_size() + b.memory_size()
    if ev._current_memory + result_size > ev.memory_limit:
        raise ExpressionError(
            f"String concatenation would exceed memory limit "
            f"({ev._current_memory + result_size} > {ev.memory_limit} bytes)"
        )
    ev._count_string_ops(len(a.item()) + len(b.item()))
    return ExprValue(a.item() + b.item())


def _add_path_string(ev: Evaluator, p: ExprValue, s: ExprValue) -> ExprValue:
    p_str = p.to_string()
    s_str = s.item()
    ev._count_string_ops(len(p_str) + len(s_str))
    return ev.make_path_value(p_str + s_str)


def _add_string_range_expr(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    a_str = a.item()
    b_str = b.to_string()
    ev._count_string_ops(len(a_str) + len(b_str))
    return ExprValue(a_str + b_str)


def _add_range_expr_string(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    a_str = a.to_string()
    b_str = b.item()
    ev._count_string_ops(len(a_str) + len(b_str))
    return ExprValue(a_str + b_str)


def _sub_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(a.item() - b.item())


def _sub_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(a.item() - b.item())


def _mul_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(a.item() * b.item())


def _mul_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(a.item() * b.item())


def _mul_string(ev: Evaluator, s: ExprValue, n: ExprValue) -> ExprValue:
    count = n.item()
    if count <= 0:
        return ExprValue("")
    # Check before allocating
    result_size = sys.getsizeof(s._string_value) * count
    if ev._current_memory + result_size > ev.memory_limit:
        raise ExpressionError(
            f"String repetition would exceed memory limit "
            f"({ev._current_memory + result_size} > {ev.memory_limit} bytes)"
        )
    ev._count_string_ops(len(s.item()) * count)
    return ExprValue(s.item() * count)


def _mul_list(ev: Evaluator, lst: ExprValue, n: ExprValue) -> ExprValue:
    count = n.item()
    if count <= 0:
        return ExprValue._from_list([], lst.type.type_params[0])
    # Check before allocating
    result_size = lst.memory_size() * count
    if ev._current_memory + result_size > ev.memory_limit:
        raise ExpressionError(
            f"List repetition would exceed memory limit "
            f"({ev._current_memory + result_size} > {ev.memory_limit} bytes)"
        )
    items = lst.to_expr_value_list()
    ev._count_operations(len(items) * count)
    return ExprValue._from_list(items * count, lst.type.type_params[0])


def _truediv_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    if b.item() == 0:
        raise ExpressionError("Division by zero")
    return ExprValue(a.item() / b.item())


def _truediv_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    if b.item() == 0:
        raise ExpressionError("Division by zero")
    return ExprValue(a.item() / b.item())


def _path_join(ev: Evaluator, p: ExprValue, child: ExprValue) -> ExprValue:
    s = p.to_string()
    child_str = child.to_string()
    ev._count_string_ops(len(s) + len(child_str))
    if is_uri(s):
        if is_uri(child_str):
            return ev.make_path_value(child_str)
        child_path = ev.pure_path(child_str)
        if child_path.is_absolute():
            return ev.make_path_value(str(child_path))
        return ev.make_path_value(uri_join(s, list(child_path.parts)))
    joined = ev.pure_path(s) / child_str
    return ev.make_path_value(str(joined))


def _floordiv_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    if b.item() == 0:
        raise ExpressionError("Division by zero")
    return ExprValue(a.item() // b.item())


def _floordiv_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    if b.item() == 0:
        raise ExpressionError("Division by zero")
    return ExprValue(int(a.item() // b.item()))


def _mod_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    if b.item() == 0:
        raise ExpressionError("Modulo by zero")
    return ExprValue(a.item() % b.item())


def _mod_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    if b.item() == 0:
        raise ExpressionError("Modulo by zero")
    return ExprValue(a.item() % b.item())


def _neg_int(ev: Evaluator, a: ExprValue) -> ExprValue:
    return ExprValue(-a.item())


def _neg_float(ev: Evaluator, a: ExprValue) -> ExprValue:
    return ExprValue(-a.item())


def _pos_int(ev: Evaluator, a: ExprValue) -> ExprValue:
    return ExprValue(+a.item())


def _pos_float(ev: Evaluator, a: ExprValue) -> ExprValue:
    return ExprValue(+a.item())
