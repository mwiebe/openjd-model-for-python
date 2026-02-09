# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for slicing operations (RFC 0005/0006)."""

import pytest

from openjd.expr import evaluate_expression
from openjd.expr._errors import ExpressionError, ExpressionTypeError


class TestListSlicing:
    """Tests for list slicing."""

    def test_basic_slice(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][1:4]")
        assert result.to_string() == "[2, 3, 4]"

    def test_slice_from_start(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][:3]")
        assert result.to_string() == "[1, 2, 3]"

    def test_slice_to_end(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][2:]")
        assert result.to_string() == "[3, 4, 5]"

    def test_slice_with_step(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][::2]")
        assert result.to_string() == "[1, 3, 5]"

    def test_slice_reverse(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][::-1]")
        assert result.to_string() == "[5, 4, 3, 2, 1]"

    def test_slice_negative_start(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][-3:]")
        assert result.to_string() == "[3, 4, 5]"

    def test_slice_negative_stop(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][1:-1]")
        assert result.to_string() == "[2, 3, 4]"

    def test_slice_empty_result(self):
        result = evaluate_expression("[1, 2, 3][5:10]")
        assert result.to_string() == "[]"

    def test_slice_step_zero_error(self):
        with pytest.raises(ExpressionError, match="step cannot be zero"):
            evaluate_expression("[1, 2, 3][::0]")


class TestStringSlicing:
    """Tests for string slicing."""

    def test_basic_slice(self):
        result = evaluate_expression('"hello"[1:4]')
        assert result.to_string() == "ell"

    def test_slice_from_start(self):
        result = evaluate_expression('"hello"[:3]')
        assert result.to_string() == "hel"

    def test_slice_to_end(self):
        result = evaluate_expression('"hello"[2:]')
        assert result.to_string() == "llo"

    def test_slice_reverse(self):
        result = evaluate_expression('"hello"[::-1]')
        assert result.to_string() == "olleh"

    def test_slice_with_step(self):
        result = evaluate_expression('"abcdefg"[::2]')
        assert result.to_string() == "aceg"

    def test_single_index(self):
        result = evaluate_expression('"hello"[0]')
        assert result.to_string() == "h"

    def test_negative_index(self):
        result = evaluate_expression('"hello"[-1]')
        assert result.to_string() == "o"

    def test_index_out_of_bounds(self):
        with pytest.raises(ExpressionError, match="out of bounds"):
            evaluate_expression('"hello"[10]')


class TestRangeExprSlicing:
    """Tests for range_expr slicing."""

    def test_basic_slice(self):
        result = evaluate_expression('range_expr("1-10")[2:5]')
        assert result.to_string() == "[3, 4, 5]"

    def test_slice_with_step(self):
        result = evaluate_expression('range_expr("1-10")[::2]')
        assert result.to_string() == "[1, 3, 5, 7, 9]"

    def test_slice_reverse(self):
        result = evaluate_expression('range_expr("1-5")[::-1]')
        assert result.to_string() == "[5, 4, 3, 2, 1]"

    def test_slice_negative_indices(self):
        result = evaluate_expression('range_expr("1-10")[-3:]')
        assert result.to_string() == "[8, 9, 10]"


class TestPathSlicing:
    """Tests confirming path is NOT subscriptable (matching Python pathlib behavior)."""

    def test_path_index_not_supported(self):
        with pytest.raises(ExpressionTypeError, match="Cannot subscript type path"):
            evaluate_expression('path("/a/b/c")[0]')

    def test_path_slice_not_supported(self):
        with pytest.raises(ExpressionTypeError, match="No matching signature"):
            evaluate_expression('path("/a/b/c")[1:3]')


class TestSlicingWithExpressions:
    """Tests for slicing with expression bounds."""

    def test_slice_with_variable_bounds(self):
        from openjd.expr import SymbolTable

        symtab = SymbolTable({"start": 1, "end": 4})
        result = evaluate_expression("[1, 2, 3, 4, 5][start:end]", values=symtab)
        assert result.to_string() == "[2, 3, 4]"

    def test_chained_slice(self):
        result = evaluate_expression("[1, 2, 3, 4, 5][1:4][::2]")
        assert result.to_string() == "[2, 4]"

    def test_slice_on_split_result(self):
        result = evaluate_expression('"a;b;c;d;e".split(";")[:3]')
        assert result.to_string() == '["a", "b", "c"]'
