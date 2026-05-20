# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for target-type propagation rules.

Mirrors ``crates/openjd-expr/tests/integration/test_target_type_propagation.rs``
in the ``openjd-rs`` workspace and exercises the contract described in
RFC 0005 § "Operators evaluate operands unconstrained".

Two rules are covered:

1. **Union member match.** When ``target_type`` is a union and the
   evaluated value already matches one of the members, the value is
   returned unchanged with that member's type.
2. **Operand-unconstrained arithmetic.** When ``target_type`` is set,
   operators evaluate their operands without that constraint applied,
   then coerce the result. Specifically, ``Param.Count - 1`` with
   ``target_type='string'`` evaluates the subtraction in numeric
   context and stringifies the result, instead of trying to subtract
   two strings.

Both behaviours were tracked as gaps in
``reports/expr-bindings-quality-evaluation-report.md`` and resolved
crate-side in ``openjd-rs`` (see report Recommendations #1 and #2).
"""

from openjd.expr import ExprType, evaluate_expression


class TestTargetTypeUnionMembership:
    """A value already in a union member type is returned unchanged."""

    def test_string_in_int_or_string(self) -> None:
        v = evaluate_expression("'42'", target_type=ExprType("int | string"))
        assert v.type == ExprType("string")
        assert v.item() == "42"


class TestTargetTypeOperandsUnconstrained:
    """Operators evaluate operands without the target-type constraint."""

    def test_arithmetic_with_string_target(self) -> None:
        """``Param.Count - 1`` with ``target_type='string'`` evaluates the
        subtraction numerically and coerces the result, rather than
        attempting to subtract two strings."""
        result = evaluate_expression(
            "Param.Count - 1",
            values={"Param.Count": 100},
            target_type=ExprType("string"),
        )
        assert result.item() == "99"
