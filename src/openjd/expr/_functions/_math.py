# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Math function implementations."""

from __future__ import annotations

import math

from .._value import ExprValue
from .._errors import ExpressionError

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


def _abs_int(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(abs(x.item()))


def _abs_float(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(abs(x.item()))


def _min_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(min(a.item(), b.item()))


def _min_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(min(a.item(), b.item()))


def _max_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(max(a.item(), b.item()))


def _max_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    return ExprValue(max(a.item(), b.item()))


def _floor_int(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(x.item())


def _floor_float(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(math.floor(x.item()))


def _ceil_int(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(x.item())


def _ceil_float(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(math.ceil(x.item()))


def _round(ev: Evaluator, x: ExprValue) -> ExprValue:
    return ExprValue(round(x.item()))


def _pow_int(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    base, exp = a.item(), b.item()
    # Guard against computing enormous big integers before the bounds check in _create.
    # int64 can hold at most ~63 bits of magnitude, so any exponent > 63 with |base| > 1
    # will overflow (except 1**n and (-1)**n).
    if exp > 63 and base not in (0, 1, -1):
        raise ExpressionError("Integer overflow: result is outside the 64-bit signed range")
    try:
        result = base**exp
    except ZeroDivisionError:
        raise ExpressionError("Cannot raise zero to a negative power")
    return ExprValue(result)


def _pow_float(ev: Evaluator, a: ExprValue, b: ExprValue) -> ExprValue:
    try:
        result = a.item() ** b.item()
    except OverflowError:
        raise ExpressionError(
            f"Overflow computing {a.item()} ** {b.item()} (result too large for float)"
        )
    except ZeroDivisionError:
        raise ExpressionError("Cannot raise zero to a negative power")
    if isinstance(result, complex):
        raise ExpressionError(
            f"Cannot compute {a.item()} ** {b.item()} (would produce complex number)"
        )
    return ExprValue(result)


def _min_int3(ev: Evaluator, a: ExprValue, b: ExprValue, c: ExprValue) -> ExprValue:
    return ExprValue(min(a.item(), b.item(), c.item()))


def _min_float3(ev: Evaluator, a: ExprValue, b: ExprValue, c: ExprValue) -> ExprValue:
    return ExprValue(min(a.item(), b.item(), c.item()))


def _max_int3(ev: Evaluator, a: ExprValue, b: ExprValue, c: ExprValue) -> ExprValue:
    return ExprValue(max(a.item(), b.item(), c.item()))


def _max_float3(ev: Evaluator, a: ExprValue, b: ExprValue, c: ExprValue) -> ExprValue:
    return ExprValue(max(a.item(), b.item(), c.item()))


def _round_ndigits(ev: Evaluator, x: ExprValue, ndigits: ExprValue) -> ExprValue:
    n = ndigits.item()
    result = round(x.item(), n)
    if n > 0:
        # Preserve trailing zeros to match requested decimal places
        return ExprValue.from_float(result, f"{result:.{n}f}")
    else:
        # Non-positive ndigits rounds to ones/tens/hundreds — returns int
        return ExprValue(int(result))


def _round_int_ndigits(ev: Evaluator, x: ExprValue, ndigits: ExprValue) -> ExprValue:
    return ExprValue(round(x.item(), ndigits.item()))
