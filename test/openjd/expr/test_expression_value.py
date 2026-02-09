# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from decimal import Decimal

import pytest

from openjd.expr import ExprValue
from openjd.expr._path_mapping import PathFormat


class TestFromFloat:
    def test_from_float_basic(self) -> None:
        v = ExprValue(3.14)
        assert v.item() == 3.14
        assert v.to_string() == "3.14"

    def test_from_float_with_original_str(self) -> None:
        v = ExprValue.from_float(3.14, "3.140")
        assert v.item() == 3.14
        assert v.to_string() == "3.140"

    def test_from_float_decimal(self) -> None:
        v = ExprValue(Decimal("3.140"))
        assert v.item() == 3.14
        assert v.to_string() == "3.140"

    def test_from_float_decimal_trailing_zeros(self) -> None:
        v = ExprValue(Decimal("1.000"))
        assert v.item() == 1.0
        assert v.to_string() == "1.000"

    def test_from_float_decimal_no_trailing_zeros(self) -> None:
        v = ExprValue(Decimal("2.5"))
        assert v.item() == 2.5
        assert v.to_string() == "2.5"


class TestFromList:
    def test_list_string(self) -> None:
        v = ExprValue(["a", "b", "c"])
        assert len(v.item()) == 3
        assert v.item()[0] == "a"

    def test_list_int(self) -> None:
        v = ExprValue([1, 2, 3])
        assert len(v.item()) == 3
        assert v.item()[0] == 1

    def test_list_bool(self) -> None:
        v = ExprValue([True, False, True])
        assert len(v.item()) == 3
        assert v.item()[0] is True
        assert v.item()[1] is False

    def test_list_list_int(self) -> None:
        v = ExprValue([[1, 2], [3, 4, 5]])
        assert len(v.item()) == 2
        assert len(v.item()[0]) == 2
        assert v.item()[0][0] == 1
        assert len(v.item()[1]) == 3


class TestExprValueConstruction:
    def test_from_value_bool(self) -> None:
        v = ExprValue(True)
        assert v.item() is True

    def test_from_value_int(self) -> None:
        v = ExprValue(42)
        assert v.item() == 42

    def test_from_value_float(self) -> None:
        v = ExprValue(3.14)
        assert v.item() == 3.14

    def test_from_value_decimal(self) -> None:
        v = ExprValue(Decimal("3.140"))
        assert v.item() == 3.14
        assert v.to_string() == "3.140"

    def test_from_value_string(self) -> None:
        v = ExprValue("hello")
        assert v.item() == "hello"

    def test_from_value_none(self) -> None:
        v = ExprValue(None)
        assert v.is_null

    def test_from_value_list(self) -> None:
        v = ExprValue([1, 2, 3])
        assert len(v.item()) == 3
        assert v.item()[0] == 1

    def test_from_value_list_decimal(self) -> None:
        v = ExprValue([Decimal("1.100"), Decimal("2.200")])
        assert v.item() == [1.1, 2.2]

    def test_from_value_list_mixed_float_decimal(self) -> None:
        v = ExprValue([1.5, Decimal("2.500")])
        assert v.item() == [1.5, 2.5]

    def test_from_value_nested_list(self) -> None:
        v = ExprValue([[1, 2], [3]])
        assert v.item() == [[1, 2], [3]]

    def test_from_value_unsupported_type(self) -> None:
        with pytest.raises(TypeError, match="Cannot convert"):
            ExprValue(object())


class TestExprValueTypeCoercionWithString:
    """Test ExprValue construction with type= as a string."""

    def test_string_to_int(self) -> None:
        v = ExprValue("42", type="int")
        assert v.item() == 42

    def test_string_to_float(self) -> None:
        v = ExprValue("3.14", type="float")
        assert v.item() == 3.14

    def test_string_to_bool_true(self) -> None:
        v = ExprValue("true", type="bool")
        assert v.item() is True

    def test_string_to_bool_false(self) -> None:
        v = ExprValue("false", type="bool")
        assert v.item() is False

    def test_string_to_path(self) -> None:
        v = ExprValue("/tmp/file.txt", type="path", path_format=PathFormat.POSIX)
        assert v.to_string() == "/tmp/file.txt"
        assert v.item() == "/tmp/file.txt"

    def test_string_to_range_expr(self) -> None:
        v = ExprValue("1-5", type="range_expr")
        assert list(v.item()) == [1, 2, 3, 4, 5]

    def test_list_with_string_type(self) -> None:
        v = ExprValue([1, 2, 3], type="list[int]")
        assert v.item() == [1, 2, 3]

    def test_list_string_with_string_type(self) -> None:
        v = ExprValue(["a", "b"], type="list[string]")
        assert v.item() == ["a", "b"]

    def test_nested_list_with_string_type(self) -> None:
        v = ExprValue([[1, 2], [3]], type="list[list[int]]")
        assert v.item() == [[1, 2], [3]]

    def test_int_to_float_coercion(self) -> None:
        v = ExprValue(42, type="float")
        assert v.item() == 42.0


class TestExprValueRepr:
    """Test ExprValue __repr__ output."""

    def test_repr_int(self) -> None:
        assert repr(ExprValue(42)) == "ExprValue(42)"

    def test_repr_float(self) -> None:
        assert repr(ExprValue(3.14)) == "ExprValue(3.14)"

    def test_repr_float_with_preserved_decimals(self) -> None:
        assert repr(ExprValue(Decimal("3.50"))) == "ExprValue('3.50', type='float')"

    def test_repr_float_with_trailing_zeros(self) -> None:
        assert repr(ExprValue(Decimal("1.000"))) == "ExprValue('1.000', type='float')"

    def test_repr_float_from_float_with_string(self) -> None:
        assert repr(ExprValue.from_float(2.5, "2.500")) == "ExprValue('2.500', type='float')"

    def test_repr_bool_true(self) -> None:
        assert repr(ExprValue(True)) == "ExprValue(True)"

    def test_repr_bool_false(self) -> None:
        assert repr(ExprValue(False)) == "ExprValue(False)"

    def test_repr_string(self) -> None:
        assert repr(ExprValue("hello")) == "ExprValue('hello')"

    def test_repr_none(self) -> None:
        assert repr(ExprValue(None)) == "ExprValue(None)"

    def test_repr_list_int(self) -> None:
        assert repr(ExprValue([1, 2, 3])) == "ExprValue([1, 2, 3], type='list[int]')"

    def test_repr_list_string(self) -> None:
        assert repr(ExprValue(["a", "b"])) == "ExprValue(['a', 'b'], type='list[string]')"

    def test_repr_list_nested(self) -> None:
        assert repr(ExprValue([[1, 2], [3]])) == "ExprValue([[1, 2], [3]], type='list[list[int]]')"

    def test_repr_path(self) -> None:
        assert (
            repr(ExprValue("/tmp/file", type="path", path_format=PathFormat.POSIX))
            == "ExprValue('/tmp/file', type='path', path_format=PathFormat.POSIX)"
        )

    def test_repr_range_expr(self) -> None:
        assert repr(ExprValue("1-5", type="range_expr")) == "ExprValue('1-5', type='range_expr')"

    def test_repr_empty_list_path(self) -> None:
        v = ExprValue([], type="list[path]")
        assert repr(v) == "ExprValue([], type='list[path]')"
        assert eval(repr(v)) == v

    def test_repr_empty_list_list_path(self) -> None:
        v = ExprValue([], type="list[list[path]]")
        assert repr(v) == "ExprValue([], type='list[list[path]]')"
        assert eval(repr(v)) == v

    @pytest.mark.parametrize("pf", [PathFormat.POSIX, PathFormat.WINDOWS])
    def test_repr_list_path_with_format(self, pf: PathFormat) -> None:
        import re

        v = ExprValue(["/a", "/b"], type="list[path]", path_format=pf)
        r = repr(v)
        assert re.match(
            r"ExprValue\(\['(/|\\\\)a', '(/|\\\\)b'\], type='list\[path\]', "
            rf"path_format=PathFormat\.{pf.name}\)",
            r,
        )
        assert eval(r) == v

    @pytest.mark.parametrize("pf", [PathFormat.POSIX, PathFormat.WINDOWS])
    def test_repr_list_list_path_with_format(self, pf: PathFormat) -> None:
        import re

        v = ExprValue([["/a"], ["/b"]], type="list[list[path]]", path_format=pf)
        r = repr(v)
        assert re.match(
            r"ExprValue\(\[\['(/|\\\\)a'\], \['(/|\\\\)b'\]\], type='list\[list\[path\]\]', "
            rf"path_format=PathFormat\.{pf.name}\)",
            r,
        )
        assert eval(r) == v
