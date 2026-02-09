# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Comparison function implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import TypeCode
from .._value import ExprValue

if TYPE_CHECKING:
    from .._eval import Evaluator


def _values_equal(ev: "Evaluator", a: ExprValue, b: ExprValue) -> bool:
    """Recursive equality comparison for all types including lists."""
    at, bt = a.type.type_code, b.type.type_code

    # Same type comparisons
    if at == bt:
        if at == TypeCode.LIST:
            av, bv = a.to_expr_value_list(), b.to_expr_value_list()
            ev._count_operations(max(len(av), len(bv)))
            if len(av) != len(bv):
                return False
            return all(_values_equal(ev, x, y) for x, y in zip(av, bv))
        if at == TypeCode.BOOL:
            return a.item() == b.item()
        if at == TypeCode.INT:
            return a.item() == b.item()
        if at == TypeCode.FLOAT:
            return a.item() == b.item()
        if at == TypeCode.STRING:
            return a.item() == b.item()
        if at == TypeCode.PATH:
            return a.to_string() == b.to_string()
        if at == TypeCode.NULLTYPE:
            return True  # null == null
        if at == TypeCode.RANGE_EXPR:
            return a.item() == b.item()
        return False

    # string vs path: normalize the string as a path for comparison
    if at == TypeCode.STRING and bt == TypeCode.PATH:
        a_normalized = str(ev.pure_path(a.item()))
        return a_normalized == b.to_string()
    if at == TypeCode.PATH and bt == TypeCode.STRING:
        b_normalized = str(ev.pure_path(b.item()))
        return a.to_string() == b_normalized

    # int vs float
    if at == TypeCode.INT and bt == TypeCode.FLOAT:
        return float(a.item()) == b.item()
    if at == TypeCode.FLOAT and bt == TypeCode.INT:
        return a.item() == float(b.item())

    # list vs range_expr
    if at == TypeCode.LIST and bt == TypeCode.RANGE_EXPR:
        return _list_eq_range_expr(ev, a, b)
    if at == TypeCode.RANGE_EXPR and bt == TypeCode.LIST:
        return _list_eq_range_expr(ev, b, a)

    return False


def _list_eq_range_expr(ev: "Evaluator", lst: ExprValue, rng: ExprValue) -> bool:
    """Compare list to range_expr by expanding range_expr."""
    list_vals = lst.to_expr_value_list()
    range_vals = list(rng.item())
    ev._count_operations(max(len(list_vals), len(range_vals)))
    if len(list_vals) != len(range_vals):
        return False
    return all(_values_equal(ev, lv, ExprValue(rv)) for lv, rv in zip(list_vals, range_vals))


def _eq_generic(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(_values_equal(ev, a, b))


def _ne_generic(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(not _values_equal(ev, a, b))


def _value_compare(ev: "Evaluator", a: ExprValue, b: ExprValue) -> int:
    """Compare two values. Returns -1, 0, or 1. Raises on incompatible types."""
    at, bt = a.type.type_code, b.type.type_code

    # Recursive list comparison
    if at == TypeCode.LIST and bt == TypeCode.LIST:
        av, bv = a.to_expr_value_list(), b.to_expr_value_list()
        ev._count_operations(max(len(av), len(bv)))
        for x, y in zip(av, bv):
            cmp = _value_compare(ev, x, y)
            if cmp != 0:
                return cmp
        return len(av) - len(bv)

    # Same type scalar comparisons
    if at == bt:
        if at == TypeCode.INT:
            return (a.item() > b.item()) - (a.item() < b.item())
        if at == TypeCode.FLOAT:
            return (a.item() > b.item()) - (a.item() < b.item())
        if at == TypeCode.STRING:
            return (a.item() > b.item()) - (a.item() < b.item())
        if at == TypeCode.PATH:
            return (a.to_string() > b.to_string()) - (a.to_string() < b.to_string())
        if at == TypeCode.BOOL:
            return (a.item() > b.item()) - (a.item() < b.item())

    # int vs float
    if at == TypeCode.INT and bt == TypeCode.FLOAT:
        lf = float(a.item())
        return (lf > b.item()) - (lf < b.item())
    if at == TypeCode.FLOAT and bt == TypeCode.INT:
        rf = float(b.item())
        return (a.item() > rf) - (a.item() < rf)

    # string vs path: normalize the string as a path for comparison
    if at == TypeCode.STRING and bt == TypeCode.PATH:
        a_normalized = str(ev.pure_path(a.item()))
        b_str = b.to_string()
        return (a_normalized > b_str) - (a_normalized < b_str)
    if at == TypeCode.PATH and bt == TypeCode.STRING:
        a_str = a.to_string()
        b_normalized = str(ev.pure_path(b.item()))
        return (a_str > b_normalized) - (a_str < b_normalized)

    from .._errors import ExpressionTypeError

    raise ExpressionTypeError(f"Cannot compare {a.type} with {b.type}")


def _lt_generic(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(_value_compare(ev, a, b) < 0)


def _le_generic(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(_value_compare(ev, a, b) <= 0)


def _gt_generic(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(_value_compare(ev, a, b) > 0)


def _ge_generic(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(_value_compare(ev, a, b) >= 0)


def _not_bool(ev: Evaluator, a: ExprValue) -> ExprValue:
    return ExprValue(not a.item())
