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

import pytest

from openjd.expr import RangeExpr, SymbolTable


@pytest.mark.xfail(reason="Bindings SymbolTable.keys returns a list; spec advertises a set")
def test_symbol_table_keys_is_set():
    """`SymbolTable.keys` is documented as `set` of top-level keys (spec)."""
    st = SymbolTable({"a": 1, "b": 2})
    assert isinstance(st.keys, set)


@pytest.mark.xfail(reason="Bindings RangeExpr is not hashable; reference is")
def test_range_expr_is_hashable():
    r = RangeExpr("1-10")
    {r}  # raises if unhashable
