# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for target type propagation rules (RFC 0005).

These tests verify that operators evaluate operands unconstrained,
allowing arithmetic on numeric types even when the target type is string.
"""

from typing import Optional

from openjd.expr import SymbolTable
from openjd.expr._eval import Evaluator, ast_parse_keyword_context
from openjd.expr._types import ExprType, TypeCode
from openjd.expr._functions import get_default_library

STRING = ExprType.STRING
LIST_INT = ExprType.LIST_INT


def _eval_with_target(expr: str, symtab: SymbolTable, target_type: Optional[ExprType]):
    """Evaluate expression with a specific target type."""
    ast_node = ast_parse_keyword_context(expr)
    evaluator = Evaluator([symtab], get_default_library())
    return evaluator.evaluate(ast_node, target_type)


class TestArithmeticInStringContext:
    """Tests that arithmetic works when target type is STRING.

    This was a bug where INT parameters were coerced to string before
    arithmetic operations when the expression was in a string context.
    """

    def test_subtraction_with_string_target(self) -> None:
        """Param.Count - 1 should work even when target is STRING."""
        symtab = SymbolTable({"Param.Count": 100})
        result = _eval_with_target("Param.Count - 1", symtab, STRING)
        assert result.to_string() == "99"

    def test_addition_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.A": 10, "Param.B": 20})
        result = _eval_with_target("Param.A + Param.B", symtab, STRING)
        assert result.to_string() == "30"

    def test_multiplication_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.X": 7})
        result = _eval_with_target("Param.X * 6", symtab, STRING)
        assert result.to_string() == "42"

    def test_division_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.N": 10})
        result = _eval_with_target("Param.N / 4", symtab, STRING)
        assert result.to_string() == "2.5"

    def test_floor_division_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.N": 10})
        result = _eval_with_target("Param.N // 3", symtab, STRING)
        assert result.to_string() == "3"

    def test_modulo_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.N": 10})
        result = _eval_with_target("Param.N % 3", symtab, STRING)
        assert result.to_string() == "1"

    def test_complex_expression_with_string_target(self) -> None:
        """Complex arithmetic like range expressions use."""
        symtab = SymbolTable({"Param.ImageCount": 100, "Param.ChunkSize": 10})
        result = _eval_with_target("(Param.ImageCount - 1) // Param.ChunkSize", symtab, STRING)
        assert result.to_string() == "9"

    def test_nested_arithmetic_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.Start": 0, "Param.End": 100, "Param.Step": 10})
        result = _eval_with_target("(Param.End - Param.Start) // Param.Step", symtab, STRING)
        assert result.to_string() == "10"


class TestArithmeticInRangeContext:
    """Tests for arithmetic in range expression context (STRING | LIST_INT)."""

    def test_subtraction_in_range_context(self) -> None:
        symtab = SymbolTable({"Param.End": 100})
        target = ExprType(TypeCode.UNION, [STRING, LIST_INT])
        result = _eval_with_target("Param.End - 1", symtab, target)
        assert result.to_string() == "99"

    def test_floor_division_in_range_context(self) -> None:
        symtab = SymbolTable({"Param.Total": 100, "Param.Chunk": 10})
        target = ExprType(TypeCode.UNION, [STRING, LIST_INT])
        result = _eval_with_target("(Param.Total - 1) // Param.Chunk", symtab, target)
        assert result.to_string() == "9"


class TestComparisonInStringContext:
    """Tests that comparisons work when target type is STRING."""

    def test_less_than_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.A": 5, "Param.B": 10})
        result = _eval_with_target("Param.A < Param.B", symtab, STRING)
        assert result.to_string() == "true"

    def test_equality_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.X": 42})
        result = _eval_with_target("Param.X == 42", symtab, STRING)
        assert result.to_string() == "true"


class TestUnaryOpInStringContext:
    """Tests that unary operators work when target type is STRING."""

    def test_negation_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.N": 42})
        result = _eval_with_target("-Param.N", symtab, STRING)
        assert result.to_string() == "-42"

    def test_not_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.Flag": True})
        result = _eval_with_target("not Param.Flag", symtab, STRING)
        assert result.to_string() == "false"


class TestConditionalInStringContext:
    """Tests that conditional expressions propagate target types correctly."""

    def test_conditional_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.Quality": "high"})
        result = _eval_with_target("100 if Param.Quality == 'high' else 50", symtab, STRING)
        assert result.to_string() == "100"

    def test_conditional_arithmetic_with_string_target(self) -> None:
        symtab = SymbolTable({"Param.N": 10, "Param.Flag": True})
        result = _eval_with_target("Param.N * 2 if Param.Flag else Param.N", symtab, STRING)
        assert result.to_string() == "20"
