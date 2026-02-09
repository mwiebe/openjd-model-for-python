# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import patch

import pytest

from openjd.model import ExpressionError, TokenError
from openjd.expr import SymbolTable, ExprValue, ExprType
from openjd.expr._path_mapping import PathFormat
from openjd.model._format_strings._expression import InterpolationExpression
from openjd.model._format_strings import _expression
from openjd.model.v2023_09 import ModelParsingContext as ModelParsingContext_v2023_09

STRING = ExprType.STRING
INT = ExprType.INT
FLOAT = ExprType.FLOAT
PATH = ExprType.PATH
BOOL = ExprType.BOOL
RANGE_EXPR = ExprType.RANGE_EXPR


class TestInterpolationExpression:
    def test_init_builds_expr_tree(self):
        with patch.object(_expression, "parse_format_string_expr") as mock:
            # WHEN
            context = ModelParsingContext_v2023_09()
            InterpolationExpression("Foo.Bar", context=context)

            # THEN
            mock.assert_called_once_with("Foo.Bar", context=context)

    def test_init_reraises_parse_error(self):
        # GIVEN
        expr = ".."

        # THEN
        with pytest.raises((TokenError, ExpressionError)):
            InterpolationExpression(expr, context=ModelParsingContext_v2023_09())

    def test_init_reraises_tokenizer_error(self):
        # GIVEN
        expr = "!!"

        # THEN
        with pytest.raises((TokenError, ExpressionError)):
            InterpolationExpression(expr, context=ModelParsingContext_v2023_09())

    def test_validate_success(self) -> None:
        # GIVEN
        symbols = set(("Test.Name",))
        expr = InterpolationExpression("Test.Name", context=ModelParsingContext_v2023_09())

        # THEN
        expr.validate_symbol_refs(symbols=symbols)  # Does not raise

    @pytest.mark.parametrize(
        "symbols, expr, error_matches",
        [
            pytest.param(
                set(),
                "Test.Foo",
                "Variable Test.Foo does not exist at this location.",
                id="empty set",
            ),
            pytest.param(
                set(("Test.Foo", "Test.Boo", "Test.Another")),
                "Tst.Foo",
                "Variable Tst.Foo does not exist at this location. Did you mean: Test.Foo",
                id="one candidate",
            ),
            pytest.param(
                set(("Test.Foo", "Test.Boo", "Test.Another")),
                "Test.Zoo",
                "Variable Test.Zoo does not exist at this location. Did you mean one of: Test.Boo, Test.Foo",
                id="two candidates",
            ),
        ],
    )
    def test_validate_error(self, symbols: set[str], expr: str, error_matches: str) -> None:
        # GIVEN
        test = InterpolationExpression(expr, context=ModelParsingContext_v2023_09())

        # THEN
        with pytest.raises(ValueError, match=error_matches):
            test.validate_symbol_refs(symbols=symbols)

    def test_evaluate_success(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"
        expr = InterpolationExpression("Test.Name", context=ModelParsingContext_v2023_09())

        # WHEN
        result = expr.evaluate(symtab=symtab)

        # THEN
        assert result == "value"

    def test_evaluate_fails(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = "value"

        # WHEN
        expr = InterpolationExpression("Test.Fail", context=ModelParsingContext_v2023_09())

        # THEN
        with pytest.raises(ExpressionError) as exc:
            expr.evaluate(symtab=symtab)

        assert "Test.Fail" in str(exc), "Name should be in validation error"

    def test_evaluate_badtype(self):
        # GIVEN
        symtab = SymbolTable()
        symtab["Test.Name"] = {"foo": "bar"}
        expr = InterpolationExpression("Test.Name", context=ModelParsingContext_v2023_09())

        # THEN
        with pytest.raises(ExpressionError):
            expr.evaluate(symtab=symtab)


class TestExprValueConversion:
    """Tests for _to_expr_value type conversion in ExprNode."""

    def _make_expr_node(self, expr_str: str):
        """Create an ExprNode from an expression string."""
        from openjd.model._format_strings._parser import ExprNode
        from openjd.expr import parse_expression

        parsed = parse_expression(expr_str)
        return ExprNode(parsed)

    def test_int_parameter_converts_to_int(self):
        """INT parameters should be converted to integer ExprValues."""
        symtab = SymbolTable({"Param.Count": ExprValue("42", type=INT)})
        node = self._make_expr_node("Param.Count + 1")
        result = node.evaluate(symtab=symtab)
        assert result == "43"

    def test_float_parameter_preserves_original_string(self):
        """FLOAT parameters should preserve original string representation."""
        symtab = SymbolTable({"Param.Value": ExprValue("3.500", type=FLOAT)})
        node = self._make_expr_node("Param.Value")
        result = node.evaluate(symtab=symtab)
        assert result == "3.500"

    def test_float_parameter_arithmetic_loses_precision(self):
        """FLOAT arithmetic should produce normalized float output."""
        symtab = SymbolTable({"Param.Value": ExprValue("3.500", type=FLOAT)})
        node = self._make_expr_node("Param.Value + 0")
        result = node.evaluate(symtab=symtab)
        assert result == "3.5"

    def test_path_parameter_converts_to_path(self, tmp_path):
        """PATH parameters should be converted to Path ExprValues."""
        import sys

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        test_file = tmp_path / "test.txt"
        symtab = SymbolTable(
            {"Param.File": ExprValue(str(test_file), type=PATH, path_format=host_pf)}
        )
        node = self._make_expr_node("Param.File.parent")
        result = node.evaluate(symtab=symtab)
        assert result == str(tmp_path)

    def test_chunk_int_parameter_becomes_range_expr(self):
        """CHUNK_INT parameters should become range_expr type."""
        symtab = SymbolTable({"Task.Param.Frame": ExprValue("1-10", type=RANGE_EXPR)})
        # When coerced to string, range_expr produces canonical form
        node = self._make_expr_node("Task.Param.Frame")
        result = node.evaluate(symtab=symtab)
        assert result == "1-10"

    def test_chunk_int_can_be_indexed(self):
        """CHUNK_INT range_expr can be indexed to get individual values."""
        symtab = SymbolTable({"Task.Param.Frame": ExprValue("1-5", type=RANGE_EXPR)})
        node = self._make_expr_node("Task.Param.Frame[0]")
        result = node.evaluate(symtab=symtab)
        assert result == "1"

    def test_string_parameter_remains_string(self):
        """STRING parameters should remain as strings."""
        symtab = SymbolTable({"Param.Name": ExprValue("hello", type=STRING)})
        node = self._make_expr_node("Param.Name")
        result = node.evaluate(symtab=symtab)
        assert result == "hello"

    def test_bool_parameter_converts_to_bool(self):
        """BOOL parameters should be converted to boolean ExprValues."""
        symtab = SymbolTable({"Param.UseGpu": ExprValue("true", type=BOOL)})
        node = self._make_expr_node("'--gpu' if Param.UseGpu else ''")
        result = node.evaluate(symtab=symtab)
        assert result == "--gpu"

    def test_bool_parameter_false(self):
        """BOOL parameters with false value."""
        symtab = SymbolTable({"Param.UseGpu": ExprValue("false", type=BOOL)})
        node = self._make_expr_node("'--gpu' if Param.UseGpu else ''")
        result = node.evaluate(symtab=symtab)
        assert result == ""

    def test_range_expr_parameter_converts_to_range_expr(self):
        """RANGE_EXPR parameters should be converted to range_expr ExprValues."""
        symtab = SymbolTable({"Param.FrameRange": ExprValue("1-100", type=RANGE_EXPR)})
        node = self._make_expr_node("Param.FrameRange")
        result = node.evaluate(symtab=symtab)
        assert result == "1-100"

    def test_range_expr_parameter_can_be_indexed(self):
        """RANGE_EXPR parameters can be indexed."""
        symtab = SymbolTable({"Param.FrameRange": ExprValue("1-5", type=RANGE_EXPR)})
        node = self._make_expr_node("Param.FrameRange[0]")
        result = node.evaluate(symtab=symtab)
        assert result == "1"

    def test_range_expr_parameter_len(self):
        """RANGE_EXPR parameters support len()."""
        symtab = SymbolTable({"Param.FrameRange": ExprValue("1-10", type=RANGE_EXPR)})
        node = self._make_expr_node("len(Param.FrameRange)")
        result = node.evaluate(symtab=symtab)
        assert result == "10"
