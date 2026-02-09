# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Type conversion function implementations."""

from __future__ import annotations


from .._value import ExprValue
from .._errors import ExpressionError

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


def _string_from_int(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(str(v.item()))


def _string_from_float(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(v.to_string())


def _string_from_bool(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("true" if v.item() else "false")


def _string_from_path(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(v.to_string())


def _string_from_null(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue("null")


def _string_identity(ev: Evaluator, v: ExprValue) -> ExprValue:
    return v


def _string_from_list(ev: Evaluator, v: ExprValue) -> ExprValue:
    """Convert list to JSON string representation."""
    return ExprValue(v.to_string())


def _int_identity(ev: Evaluator, v: ExprValue) -> ExprValue:
    return v


def _int_from_string(ev: Evaluator, s: ExprValue) -> ExprValue:
    try:
        return ExprValue(int(s.item()))
    except ValueError:
        raise ExpressionError(f"Cannot convert '{s.item()}' to int")


def _int_from_float(ev: Evaluator, f: ExprValue) -> ExprValue:
    if f.item() != int(f.item()):
        raise ExpressionError(f"Cannot convert {f.item()} to int without loss")
    return ExprValue(int(f.item()))


def _float_identity(ev: Evaluator, v: ExprValue) -> ExprValue:
    return v


def _float_from_string(ev: Evaluator, s: ExprValue) -> ExprValue:
    try:
        return ExprValue(float(s.item()))
    except ValueError:
        raise ExpressionError(f"Cannot convert '{s.item()}' to float")


def _float_from_int(ev: Evaluator, i: ExprValue) -> ExprValue:
    return ExprValue(float(i.item()))


def _bool_identity(ev: Evaluator, v: ExprValue) -> ExprValue:
    return v


def _bool_from_null(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(False)


def _bool_from_int(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(v.item() != 0)


def _bool_from_float(ev: Evaluator, v: ExprValue) -> ExprValue:
    return ExprValue(v.item() != 0.0)


_BOOL_TRUE_STRINGS = frozenset(["1", "true", "on", "yes"])
_BOOL_FALSE_STRINGS = frozenset(["0", "false", "off", "no"])


def _bool_from_string(ev: Evaluator, v: ExprValue) -> ExprValue:
    s = v.item().lower()
    if s in _BOOL_TRUE_STRINGS:
        return ExprValue(True)
    if s in _BOOL_FALSE_STRINGS:
        return ExprValue(False)
    raise ExpressionError(
        f"Cannot convert '{v.item()}' to bool. "
        f"Expected one of: 1, true, on, yes, 0, false, off, no"
    )


def _bool_from_path(ev: Evaluator, v: ExprValue) -> ExprValue:
    raise ExpressionError("Cannot convert path to bool")


def _bool_from_list(ev: Evaluator, v: ExprValue) -> ExprValue:
    raise ExpressionError("Cannot convert list to bool")


def _fail(ev: Evaluator, message: ExprValue) -> ExprValue:
    """Fail with an error message."""
    raise ExpressionError(message.item())
