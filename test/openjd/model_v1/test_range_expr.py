# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Behavior tests for the Rust-backed `IntRangeExpr` exposed from
`openjd.model._v1`.

The pure-Python reference's exhaustive parser/grammar coverage lives in
`test/openjd/model_v0/_internal/test_range_expr.py`; this file focuses on
behavior that is specific to the Rust binding's documented semantics.
"""

from openjd.model._v1 import IntRangeExpr


class TestIntRangeExpr_v1:  # noqa: N801
    def test_iteration_is_always_ascending(self) -> None:
        """`RangeExpr` values are always an increasing list of integers,
        regardless of input direction. The Rust `IntRange` normalises
        descending input to canonical ascending form, and iteration,
        indexing, and `Display` all operate on that canonical form.

        This is a documented behavior change versus the pure-Python
        reference (`openjd.model._range_expr.IntRangeExpr`), which
        preserves the user-supplied direction. See:

        - `specs/python-model-interface.md`
          "Behavior change: RangeExpr iteration is always ascending"
        - `openjd-rs/specs/expr/range-expr.md` "Internal Representation"
        """
        # Two-element descending range with negative step.
        r = IntRangeExpr.from_str("-1 - -2 : -1")
        assert list(r) == [-2, -1]
        # Indexing also operates on the canonical ascending form.
        assert r[0] == -2
        assert r[-1] == -1

        # Multi-element descending range normalises the same way.
        r2 = IntRangeExpr.from_str("10-1:-1")
        assert list(r2) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Descending with a larger step.
        r3 = IntRangeExpr.from_str("10-1:-3")
        assert list(r3) == [1, 4, 7, 10]

        # Membership and length are unaffected by direction —
        # `RangeExpr` equality and containment are set-based.
        assert 5 in r2
        assert 100 not in r2
        assert len(r2) == 10
