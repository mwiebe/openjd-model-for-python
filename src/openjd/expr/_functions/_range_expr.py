# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Rangeexpr function implementations."""

from __future__ import annotations

from .._types import ExprType
from .._value import ExprValue
from .._errors import ExpressionError
from .._range_expr import RangeExpr

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


def _getitem_range_expr(ev: Evaluator, r: ExprValue, index: ExprValue) -> ExprValue:
    rng = r.item()
    idx = index.item()
    length = len(rng)
    if idx < 0:
        idx = length + idx
    if idx < 0 or idx >= length:
        raise ExpressionError(
            f"Index {index.item()} out of bounds for range_expr of length {length}"
        )
    return ExprValue(rng[idx])


def _slice_range_expr(
    ev: Evaluator,
    r: ExprValue,
    start: ExprValue,
    stop: ExprValue,
    step: ExprValue,
) -> ExprValue:
    """Slice a range_expr using Python slice semantics, returns list[int]."""
    start_val = start.item() if not start.is_null else None
    stop_val = stop.item() if not stop.is_null else None
    step_val = step.item() if not step.is_null else None
    if step_val == 0:
        raise ExpressionError("slice step cannot be zero")
    items = list(r.item())[start_val:stop_val:step_val]
    return ExprValue._from_list([ExprValue(i) for i in items], ExprType.INT)


def _len_range_expr(ev: Evaluator, r: ExprValue) -> ExprValue:
    return ExprValue(len(r.item()))


def _min_range_expr(ev: Evaluator, r: ExprValue) -> ExprValue:
    rng = r.item()
    if len(rng) == 0:
        raise ExpressionError("min() requires a non-empty range_expr")
    return ExprValue(rng.start)


def _max_range_expr(ev: Evaluator, r: ExprValue) -> ExprValue:
    rng = r.item()
    if len(rng) == 0:
        raise ExpressionError("max() requires a non-empty range_expr")
    return ExprValue(rng.end)


def _sum_range_expr(ev: Evaluator, r: ExprValue) -> ExprValue:
    return ExprValue(sum(r.item()))


def _string_from_range_expr(ev: Evaluator, r: ExprValue) -> ExprValue:
    return ExprValue(str(r.item()))


def _list_from_range_expr(ev: Evaluator, r: ExprValue) -> ExprValue:
    rng = r.item()
    ev._count_operations(len(rng))
    values = [ExprValue(i) for i in rng]
    return ExprValue._create(ExprType.LIST_INT, list_value=values)


def _range_expr_from_string(ev: Evaluator, s: ExprValue) -> ExprValue:
    try:
        rng = RangeExpr.from_str(s.item())
        return ExprValue._create(ExprType.RANGE_EXPR, range_expr_value=rng)
    except ValueError as e:
        raise ExpressionError(f"Invalid range expression: {e}")


def _range_expr_from_list(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = list(lst.item())
    if not items:
        raise ExpressionError("range_expr requires at least one value")
    rng = RangeExpr.from_list(items)
    return ExprValue._create(ExprType.RANGE_EXPR, range_expr_value=rng)


def _contains_range_expr(ev: Evaluator, r: ExprValue, item: ExprValue) -> ExprValue:
    """Check if item is in range_expr."""
    return ExprValue(item.item() in r.item())


def _not_contains_range_expr(ev: Evaluator, r: ExprValue, item: ExprValue) -> ExprValue:
    """Check if item is not in range_expr."""
    return ExprValue(item.item() not in r.item())
