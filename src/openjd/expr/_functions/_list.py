# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""List function implementations."""

from __future__ import annotations

from .._types import ExprType, TypeCode
from .._value import ExprValue
from .._errors import ExpressionError
from ._comparison import _values_equal

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


def _contains(ev: Evaluator, lst: ExprValue, item: ExprValue) -> ExprValue:
    """Check if item is in list."""
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    for v in items:
        if _values_equal(ev, v, item):
            return ExprValue(True)
    return ExprValue(False)


def _not_contains(ev: Evaluator, lst: ExprValue, item: ExprValue) -> ExprValue:
    """Check if item is not in list."""
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    for v in items:
        if _values_equal(ev, v, item):
            return ExprValue(False)
    return ExprValue(True)


def _any(ev: Evaluator, values: ExprValue) -> ExprValue:
    items = values.to_expr_value_list()
    ev._count_operations(len(items))
    return ExprValue(any(v.item() for v in items))


def _any_empty(ev: Evaluator, values: ExprValue) -> ExprValue:
    return ExprValue(False)


def _all(ev: Evaluator, values: ExprValue) -> ExprValue:
    items = values.to_expr_value_list()
    ev._count_operations(len(items))
    return ExprValue(all(v.item() for v in items))


def _all_empty(ev: Evaluator, values: ExprValue) -> ExprValue:
    return ExprValue(True)


def _len_list(ev: Evaluator, lst: ExprValue) -> ExprValue:
    return ExprValue(len(lst.to_expr_value_list()))


def _min_list_empty(ev: Evaluator, lst: ExprValue) -> ExprValue:
    raise ExpressionError("min() requires a non-empty list")


def _min_list_int(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = lst.to_expr_value_list()
    if not items:
        raise ExpressionError("min() requires a non-empty list")
    ev._count_operations(len(items))
    return ExprValue(min(v.item() for v in items))


def _min_list_float(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = lst.to_expr_value_list()
    if not items:
        raise ExpressionError("min() requires a non-empty list")
    ev._count_operations(len(items))
    return ExprValue(min(v.item() for v in items))


def _max_list_empty(ev: Evaluator, lst: ExprValue) -> ExprValue:
    raise ExpressionError("max() requires a non-empty list")


def _max_list_int(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = lst.to_expr_value_list()
    if not items:
        raise ExpressionError("max() requires a non-empty list")
    ev._count_operations(len(items))
    return ExprValue(max(v.item() for v in items))


def _max_list_float(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = lst.to_expr_value_list()
    if not items:
        raise ExpressionError("max() requires a non-empty list")
    ev._count_operations(len(items))
    return ExprValue(max(v.item() for v in items))


def _sum_list_int(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    return ExprValue(sum(v.item() for v in items))


def _sum_list_float(ev: Evaluator, lst: ExprValue) -> ExprValue:
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    return ExprValue(sum(v.item() for v in items))


def _sum_list_empty(ev: Evaluator, lst: ExprValue) -> ExprValue:
    return ExprValue(0)


def _join_paths(ev: Evaluator, items: ExprValue, sep: ExprValue) -> ExprValue:
    item_list = items.to_expr_value_list()
    ev._count_operations(len(item_list))
    strings = [v.to_string() for v in item_list]
    return ExprValue(sep.item().join(strings))


def _flatten(ev: Evaluator, lst: ExprValue) -> ExprValue:
    """Flatten a list of lists into a single list."""
    result: list[ExprValue] = []
    # lst.type is list[list[T]], so type_params[0] is list[T]
    inner_type = lst.type.type_params[0] if lst.type.type_params else None
    if inner_type is None or not inner_type.type_params:
        raise ExpressionError("flatten requires a list of lists")

    outer = lst.to_expr_value_list()
    ev._count_operations(len(outer))
    for inner_list in outer:
        inner = inner_list.to_expr_value_list()
        ev._count_operations(len(inner))
        result.extend(inner)

    # Determine the element type of the flattened list (T from list[T])
    element_type = inner_type.type_params[0]
    return ExprValue._create(ExprType(TypeCode.LIST, [element_type]), list_value=result)


def _flatten_identity(ev: Evaluator, lst: ExprValue) -> ExprValue:
    """Identity flatten for already-flat lists."""
    return lst


def _getitem_list(ev: Evaluator, lst: ExprValue, index: ExprValue) -> ExprValue:
    """Get item from list by index."""
    idx = index.item()
    items = lst.to_expr_value_list()
    if idx < 0:
        idx = len(items) + idx
    if idx < 0 or idx >= len(items):
        raise ExpressionError(f"Index {index.item()} out of bounds for list of length {len(items)}")
    return items[idx]


def _slice_list(
    ev: Evaluator,
    lst: ExprValue,
    start: ExprValue,
    stop: ExprValue,
    step: ExprValue,
) -> ExprValue:
    """Slice a list using Python slice semantics."""
    start_val = start.item() if not start.is_null else None
    stop_val = stop.item() if not stop.is_null else None
    step_val = step.item() if not step.is_null else None
    if step_val == 0:
        raise ExpressionError("slice step cannot be zero")
    sliced = lst.to_expr_value_list()[start_val:stop_val:step_val]
    elem_type = lst.type.type_params[0] if lst.type.type_params else ExprType.NULLTYPE
    return ExprValue._from_list(sliced, elem_type)


def _range_check_size(ev: Evaluator, r: range) -> None:
    """Check if range result would exceed memory limit."""
    count = len(r)
    if count <= 0:
        return
    import sys

    int_size = ExprValue(0).memory_size()
    list_overhead = sys.getsizeof([])
    result_size = count * int_size + list_overhead
    if ev._current_memory + result_size > ev.memory_limit:
        raise ExpressionError(
            f"range() would exceed memory limit "
            f"({ev._current_memory + result_size} > {ev.memory_limit} bytes)"
        )


def _range_stop(ev: Evaluator, stop: ExprValue) -> ExprValue:
    """Generate list of integers from 0 to stop-1."""
    r = range(stop.item())
    _range_check_size(ev, r)
    ev._count_operations(len(r))
    result = [ExprValue(i) for i in r]
    return ExprValue._from_list(result, ExprType.INT)


def _range_start_stop(ev: Evaluator, start: ExprValue, stop: ExprValue) -> ExprValue:
    """Generate list of integers from start to stop-1."""
    r = range(start.item(), stop.item())
    _range_check_size(ev, r)
    ev._count_operations(len(r))
    result = [ExprValue(i) for i in r]
    return ExprValue._from_list(result, ExprType.INT)


def _range_start_stop_step(
    ev: Evaluator, start: ExprValue, stop: ExprValue, step: ExprValue
) -> ExprValue:
    """Generate list of integers from start to stop-1 with step."""
    if step.item() == 0:
        raise ExpressionError("range() step argument must not be zero")
    r = range(start.item(), stop.item(), step.item())
    _range_check_size(ev, r)
    ev._count_operations(len(r))
    result = [ExprValue(i) for i in r]
    return ExprValue._from_list(result, ExprType.INT)


def _add_list(ev: Evaluator, left: ExprValue, right: ExprValue) -> ExprValue:
    """Concatenate two lists with type coercion."""
    from .._types import ExprType, TypeCode
    from .._errors import ExpressionTypeError

    # Count iterations for both lists
    left_items = left.to_expr_value_list()
    right_items = right.to_expr_value_list()
    ev._count_operations(len(left_items) + len(right_items))

    # Check memory limit before concatenation
    result_size = left.memory_size() + right.memory_size()
    if ev._current_memory + result_size > ev.memory_limit:
        raise ExpressionError(
            f"List concatenation would exceed memory limit "
            f"({ev._current_memory + result_size} > {ev.memory_limit} bytes)"
        )

    left_elem = left.type.type_params[0] if left.type.type_params else None
    right_elem = right.type.type_params[0] if right.type.type_params else None

    # Handle empty lists (list[?])
    if left_elem and left_elem.type_code == TypeCode.NULLTYPE:
        return ExprValue._from_list(right.to_expr_value_list()[:], right_elem or ExprType.NULLTYPE)
    if right_elem and right_elem.type_code == TypeCode.NULLTYPE:
        return ExprValue._from_list(left.to_expr_value_list()[:], left_elem or ExprType.NULLTYPE)

    # Same element type - simple concat
    if left_elem == right_elem and left_elem is not None:
        return ExprValue._from_list(
            left.to_expr_value_list() + right.to_expr_value_list(), left_elem
        )

    # Type coercion: int + float -> float
    if left_elem and right_elem:
        if left_elem.type_code == TypeCode.INT and right_elem.type_code == TypeCode.FLOAT:
            coerced_left = [ExprValue(float(v.item())) for v in left.to_expr_value_list()]
            return ExprValue._from_list(coerced_left + right.to_expr_value_list(), ExprType.FLOAT)
        if left_elem.type_code == TypeCode.FLOAT and right_elem.type_code == TypeCode.INT:
            coerced_right = [ExprValue(float(v.item())) for v in right.to_expr_value_list()]
            return ExprValue._from_list(left.to_expr_value_list() + coerced_right, ExprType.FLOAT)

        # Type coercion: path + string -> string
        if left_elem.type_code == TypeCode.PATH and right_elem.type_code == TypeCode.STRING:
            coerced_left = [ExprValue(str(v.item())) for v in left.to_expr_value_list()]
            return ExprValue._from_list(coerced_left + right.to_expr_value_list(), ExprType.STRING)
        if left_elem.type_code == TypeCode.STRING and right_elem.type_code == TypeCode.PATH:
            coerced_right = [ExprValue(str(v.item())) for v in right.to_expr_value_list()]
            return ExprValue._from_list(left.to_expr_value_list() + coerced_right, ExprType.STRING)

        # Incompatible types
        raise ExpressionTypeError(f"Cannot concatenate list[{left_elem}] with list[{right_elem}]")

    # Fallback - use whichever element type is available
    elem_type = left_elem or right_elem or ExprType.NULLTYPE
    return ExprValue._from_list(left.to_expr_value_list() + right.to_expr_value_list(), elem_type)


def _range_expr_to_list(r: ExprValue) -> ExprValue:
    """Convert range_expr to list[int]."""
    return ExprValue._from_list([ExprValue(i) for i in r.item()], ExprType.INT)


def _add_range_expr_list(ev: Evaluator, left: ExprValue, right: ExprValue) -> ExprValue:
    """Concatenate range_expr + list."""
    return _add_list(ev, _range_expr_to_list(left), right)


def _add_list_range_expr(ev: Evaluator, left: ExprValue, right: ExprValue) -> ExprValue:
    """Concatenate list + range_expr."""
    return _add_list(ev, left, _range_expr_to_list(right))


def _add_range_expr_range_expr(ev: Evaluator, left: ExprValue, right: ExprValue) -> ExprValue:
    """Concatenate range_expr + range_expr."""
    return _add_list(ev, _range_expr_to_list(left), _range_expr_to_list(right))


def _sorted(ev: Evaluator, lst: ExprValue) -> ExprValue:
    """Return a new list with elements sorted in ascending order."""
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    sorted_items = sorted(items, key=lambda v: v.item())
    elem_type = lst.type.type_params[0] if lst.type.type_params else ExprType.NULLTYPE
    return ExprValue._from_list(sorted_items, elem_type)


def _reversed(ev: Evaluator, lst: ExprValue) -> ExprValue:
    """Return a new list with elements in reverse order."""
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    reversed_items = list(reversed(items))
    elem_type = lst.type.type_params[0] if lst.type.type_params else ExprType.NULLTYPE
    return ExprValue._from_list(reversed_items, elem_type)


def _hashable_key(v: ExprValue) -> object:
    """Convert an ExprValue to a hashable key for set-based deduplication."""
    if v.type.type_code == TypeCode.LIST:
        return tuple(_hashable_key(e) for e in v.to_expr_value_list())
    if v.type.type_code == TypeCode.PATH:
        return v.to_string()
    if v.type.type_code == TypeCode.RANGE_EXPR:
        return v.to_string()
    return v.item()


def _unique(ev: Evaluator, lst: ExprValue) -> ExprValue:
    """Return a new list with duplicates removed, preserving first occurrence order."""
    items = lst.to_expr_value_list()
    ev._count_operations(len(items))
    seen: set[object] = set()
    result: list[ExprValue] = []
    for item in items:
        key = _hashable_key(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    elem_type = lst.type.type_params[0] if lst.type.type_params else ExprType.NULLTYPE
    return ExprValue._from_list(result, elem_type)
