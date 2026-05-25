# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Failing tests demonstrating behavioural gaps between the Rust-backed
``openjd.expr`` bindings and the pure-Python reference implementation.

Every test here is expected to *fail* against the current bindings and is
marked ``xfail``. As gaps are resolved the corresponding tests are moved
to the appropriate home in this directory (e.g. pickle tests to
``test_pickle.py``, path-mapping tests to ``test_path_mapping.py``);
this file is being driven to zero.

Cross-reference:
    reports/expr-bindings-quality-evaluation-report.md
"""

from __future__ import annotations

import pytest

from openjd.expr import (
    ExprType,
    ExprValue,
    ExpressionTypeError,
    PathFormat,
    TypeCode,
)


# ── Hashability of PathFormat ───────────────────────────────────────


@pytest.mark.xfail(
    reason="PathFormat is not hashable on the binding (missing `hash` in "
    "#[pyclass(...)] config in rust-bindings/src/expr/path_format.rs); "
    "TypeCode and ExprRevision both are. Inconsistency in the public "
    "binding API: every other enum-shaped pyclass in openjd.expr is "
    "hashable.",
    strict=True,
)
def test_path_format_is_hashable() -> None:
    # Every enum-shaped pyclass in `openjd.expr` should be hashable so it
    # can be used as a dict key, set member, or pickled in a structure
    # that implies hash equality. `TypeCode` and `ExprRevision` already
    # are; only `PathFormat` is missing.
    h = hash(PathFormat.POSIX)
    # Same enum singleton hashes equal.
    assert h == hash(PathFormat.POSIX)
    # Usable as set member.
    assert PathFormat.POSIX in {PathFormat.POSIX}


# ── ExprValue.unresolved item/str raises ────────────────────────────


@pytest.mark.xfail(
    reason="ExprValue.unresolved(T).item() returns None on the binding; "
    "the pure-Python reference raises ExpressionTypeError "
    '("value is not known"). Surface: rust-bindings/src/expr/expr_value.rs::'
    "expr_value_to_py — the ExprValue::Unresolved arm collapses to py.None(); "
    "the spec is silent but the reference behaviour is the contract for any "
    "consumer porting from openjd.model.v0.",
    strict=True,
)
def test_unresolved_item_raises() -> None:
    # Reference: ExprValue.unresolved(ExprType.INT).item() raises
    # ExpressionTypeError("…value is not known").
    with pytest.raises(ExpressionTypeError, match="value is not known"):
        ExprValue.unresolved(ExprType("int")).item()


@pytest.mark.xfail(
    reason="See test_unresolved_item_raises — binding's __str__ returns "
    "'<unresolved[int]>' (delegated to ExprValue::to_display_string in the "
    "underlying crate) instead of raising ExpressionTypeError as the "
    "reference does.",
    strict=True,
)
def test_unresolved_str_raises() -> None:
    # Reference: stringifying an unresolved value raises
    # ExpressionTypeError. Binding silently returns
    # '<unresolved[int]>'.
    with pytest.raises(ExpressionTypeError, match="value is not known"):
        str(ExprValue.unresolved(ExprType("int")))


# ── ExprValue list construction error class ─────────────────────────


@pytest.mark.xfail(
    reason="Binding raises ValueError ('make_list expected int element, "
    "got string'); reference raises TypeError('incompatible types'). "
    "Surface: rust-bindings/src/expr/expr_value.rs — ExprValue::make_list "
    "errors map through PyValueError, but TypeError is the correct error "
    "class for type-incompatible list elements (Python convention and "
    "reference contract).",
    strict=True,
)
def test_mixed_type_list_raises_type_error() -> None:
    # Reference: ExprValue([1, "hello"]) raises
    # TypeError("incompatible types").
    with pytest.raises(TypeError, match="incompatible types"):
        ExprValue([1, "hello"])


@pytest.mark.xfail(
    reason="Binding raises ValueError ('Cannot create list from unresolved "
    "elements'); reference raises TypeError('Cannot construct a list "
    "containing unresolved values'). Same surface and same root cause as "
    "test_mixed_type_list_raises_type_error.",
    strict=True,
)
def test_list_with_unresolved_raises_type_error() -> None:
    # Reference: TypeError. Binding: ValueError.
    with pytest.raises(TypeError, match="unresolved"):
        ExprValue([ExprValue.unresolved(ExprType("int")), 42])


# ── ExprType(UNRESOLVED) without exactly one type param ─────────────


@pytest.mark.xfail(
    reason="Binding accepts ExprType(TypeCode.UNRESOLVED) with zero or many "
    "type params; reference raises ValueError('exactly one type parameter'). "
    "The binding's ExprType::new in rust-bindings/src/expr/expr_type.rs does "
    "not enforce arity constraints — defers fully to the underlying Rust "
    "crate's ExprType::new which in turn allows non-canonical shapes.",
    strict=True,
)
def test_unresolved_type_requires_exactly_one_param() -> None:
    # Reference: ExprType(TypeCode.UNRESOLVED) with no params is invalid.
    with pytest.raises(ValueError, match="exactly one type parameter"):
        ExprType(TypeCode.UNRESOLVED)
    with pytest.raises(ValueError, match="exactly one type parameter"):
        ExprType(TypeCode.UNRESOLVED, [])
    with pytest.raises(ValueError, match="exactly one type parameter"):
        ExprType(TypeCode.UNRESOLVED, [ExprType("int"), ExprType("string")])
