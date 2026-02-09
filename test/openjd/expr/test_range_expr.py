# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for range expressions."""

import pytest
from openjd.expr import evaluate_expression, SymbolTable, ExpressionError, TypeCode
from openjd.model import IntRangeExpr


class TestRangeExpr:
    def test_range_expr_from_string(self) -> None:
        result = evaluate_expression("range_expr('1-10')")
        assert result.type.type_code == TypeCode.RANGE_EXPR
        assert len(result.item()) == 10

    def test_range_expr_len(self) -> None:
        assert evaluate_expression("len(range_expr('1-10'))").item() == 10

    def test_range_expr_subscript_positive(self) -> None:
        assert evaluate_expression("range_expr('1-10')[0]").item() == 1
        assert evaluate_expression("range_expr('1-10')[9]").item() == 10

    def test_range_expr_subscript_negative(self) -> None:
        assert evaluate_expression("range_expr('1-10')[-1]").item() == 10
        assert evaluate_expression("range_expr('1-10')[-2]").item() == 9

    def test_range_expr_subscript_out_of_bounds(self) -> None:
        with pytest.raises(ExpressionError, match="out of bounds"):
            evaluate_expression("range_expr('1-10')[100]")

    def test_range_expr_to_list(self) -> None:
        result = evaluate_expression("list(range_expr('1-5'))")
        assert result.item() == [1, 2, 3, 4, 5]

    def test_range_expr_to_string(self) -> None:
        assert evaluate_expression("string(range_expr('1-5,10-15'))").item() == "1-5,10-15"

    def test_range_expr_with_step(self) -> None:
        result = evaluate_expression("list(range_expr('1-10:2'))")
        assert result.item() == [1, 3, 5, 7, 9]

    def test_range_expr_from_symtab(self) -> None:
        from openjd.model import IntRangeExpr

        symtab = SymbolTable({"Param.Frames": IntRangeExpr.from_str("1-100:10")})
        assert evaluate_expression("Param.Frames[0]", values=symtab).item() == 1
        assert evaluate_expression("len(Param.Frames)", values=symtab).item() == 10

    def test_range_expr_invalid_string(self) -> None:
        with pytest.raises(ExpressionError, match="Unexpected 'n'"):
            evaluate_expression("range_expr('not-a-range')")

    def test_range_expr_empty_string(self) -> None:
        with pytest.raises(ExpressionError, match="Empty expression"):
            evaluate_expression("range_expr('')")

    def test_range_expr_from_list(self) -> None:
        result = evaluate_expression("range_expr([1, 2, 3])")
        assert result.item() == IntRangeExpr.from_str("1-3")

    def test_range_expr_from_list_non_contiguous(self) -> None:
        result = evaluate_expression("range_expr([1, 3, 5, 10])")
        assert list(result.item()) == [1, 3, 5, 10]

    def test_range_expr_from_list_duplicates(self) -> None:
        result = evaluate_expression("string(range_expr([1, 1, 1]))")
        assert result.item() == "1"

    def test_range_expr_from_list_reverse(self) -> None:
        result = evaluate_expression("string(range_expr([9, 8, 7, 6]))")
        assert result.item() == "6-9"

    def test_range_expr_empty_list(self) -> None:
        with pytest.raises(ExpressionError, match="requires at least one value"):
            evaluate_expression("range_expr([])")

    def test_range_expr_in_comprehension(self) -> None:
        result = evaluate_expression("[x * 2 for x in range_expr('1-5')]")
        assert result.item() == [2, 4, 6, 8, 10]

    def test_range_expr_in_comprehension_with_filter(self) -> None:
        result = evaluate_expression("[x for x in range_expr('1-10') if x > 5]")
        assert result.item() == [6, 7, 8, 9, 10]

    def test_range_expr_in_comprehension_from_symtab(self) -> None:
        from openjd.model import IntRangeExpr

        symtab = SymbolTable({"Frames": IntRangeExpr.from_str("1-100:10")})
        result = evaluate_expression("[f + 1000 for f in Frames]", values=symtab)
        assert result.item() == list(range(1001, 1100, 10))

    def test_range_expr_min(self) -> None:
        assert evaluate_expression("min(range_expr('5-10'))").item() == 5
        assert evaluate_expression("min(range_expr('10-5:-1'))").item() == 5
        assert evaluate_expression("min(range_expr('1,5,10,3'))").item() == 1

    def test_range_expr_max(self) -> None:
        assert evaluate_expression("max(range_expr('5-10'))").item() == 10
        assert evaluate_expression("max(range_expr('10-5:-1'))").item() == 10
        assert evaluate_expression("max(range_expr('1,5,10,3'))").item() == 10

    def test_range_expr_sum(self) -> None:
        assert evaluate_expression("sum(range_expr('1-5'))").item() == 15
        assert evaluate_expression("sum(range_expr('1-10:2'))").item() == 25  # 1+3+5+7+9

    def test_range_expr_min_max_from_symtab(self) -> None:
        from openjd.model import IntRangeExpr

        symtab = SymbolTable({"Frames": IntRangeExpr.from_str("10-50:5")})
        assert evaluate_expression("min(Frames)", values=symtab).item() == 10
        assert evaluate_expression("max(Frames)", values=symtab).item() == 50
