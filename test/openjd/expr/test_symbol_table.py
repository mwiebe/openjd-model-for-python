# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
from typing import cast

import pytest

import sys

from openjd.expr import ExprValue, SymbolTable, TypeCode
from openjd.expr import PathFormat

HOST_PATH_FORMAT = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX


class TestSymbolTable:
    def test_construct_empty(self) -> None:
        # WHEN
        symtab = SymbolTable()

        # THEN
        assert "Param" not in symtab

    def test_construct_from_dict_simple(self) -> None:
        # GIVEN
        source = {"Param.Frame": 42, "Param.Name": "test"}

        # WHEN
        symtab = SymbolTable(source)

        # THEN
        assert "Param" in symtab
        param = cast(SymbolTable, symtab["Param"])
        assert cast(ExprValue, param["Frame"]).item() == 42
        assert cast(ExprValue, param["Name"]).item() == "test"

    def test_construct_from_dict_with_path(self, tmp_path) -> None:
        # GIVEN
        input_file = tmp_path / "projects" / "render.exr"
        source = {
            "Param.InputFile": ExprValue(str(input_file), type="path", path_format=HOST_PATH_FORMAT)
        }

        # WHEN
        symtab = SymbolTable(source)

        # THEN
        param = cast(SymbolTable, symtab["Param"])
        assert str(cast(ExprValue, param["InputFile"])) == str(input_file)

    def test_construct_from_dict_nested(self) -> None:
        # GIVEN
        source = {"Param": {"Frame": 100, "Name": "nested"}}

        # WHEN
        symtab = SymbolTable(source)

        # THEN
        param = cast(SymbolTable, symtab["Param"])
        assert cast(ExprValue, param["Frame"]).item() == 100
        assert cast(ExprValue, param["Name"]).item() == "nested"

    def test_construct_from_symtab(self) -> None:
        # GIVEN
        original = SymbolTable({"Param.Frame": 42})

        # WHEN
        copy = SymbolTable(original)

        # THEN
        param = cast(SymbolTable, copy["Param"])
        assert cast(ExprValue, param["Frame"]).item() == 42

    def test_setitem_dotted_path(self) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        symtab["Task.Param.Index"] = 5

        # THEN
        task = cast(SymbolTable, symtab["Task"])
        param = cast(SymbolTable, task["Param"])
        assert cast(ExprValue, param["Index"]).item() == 5

    def test_setitem_creates_intermediate_tables(self) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        symtab["A.B.C.D"] = "deep"

        # THEN
        a = cast(SymbolTable, symtab["A"])
        b = cast(SymbolTable, a["B"])
        c = cast(SymbolTable, b["C"])
        assert cast(ExprValue, c["D"]).item() == "deep"

    @pytest.mark.parametrize(
        "value,expected_type",
        [
            pytest.param(True, TypeCode.BOOL, id="bool"),
            pytest.param(42, TypeCode.INT, id="int"),
            pytest.param(3.14, TypeCode.FLOAT, id="float"),
            pytest.param("hello", TypeCode.STRING, id="string"),
            pytest.param(None, TypeCode.NULLTYPE, id="none"),
        ],
    )
    def test_auto_conversion(self, value, expected_type: TypeCode) -> None:
        # GIVEN
        symtab = SymbolTable()

        # WHEN
        symtab["Test"] = value

        # THEN
        result = symtab["Test"]
        assert isinstance(result, ExprValue)
        assert result.type.type_code == expected_type

    def test_auto_conversion_rejects_purepath(self) -> None:
        symtab = SymbolTable()
        with pytest.raises(TypeError, match="Cannot convert"):
            symtab["Test"] = Path("/tmp")

    def test_setitem_expression_value_passthrough(self) -> None:
        # GIVEN
        symtab = SymbolTable()
        ev = ExprValue(999)

        # WHEN
        symtab["Test"] = ev

        # THEN
        assert symtab["Test"] == ev

    def test_get_existing(self) -> None:
        # GIVEN
        symtab = SymbolTable({"Param.X": 1})

        # WHEN/THEN
        assert symtab.get("Param") is not None
        assert symtab.get("Missing") is None

    def test_construct_from_dict_with_purepath_rejects(self, tmp_path) -> None:
        """PurePath values should be rejected by SymbolTable."""
        output_dir = tmp_path / "projects" / "output"
        with pytest.raises(TypeError, match="Cannot convert"):
            SymbolTable({"Param.Dir": output_dir})

    def test_keys_returns_set_of_top_level_names(self) -> None:
        """``SymbolTable.keys`` returns a ``set`` of top-level symbol names,
        as documented in ``specs/python-expr-interface.md``. Nested keys
        roll up under their root namespace."""
        symtab = SymbolTable({"Param.Frame": 1, "Param.Name": "x", "Task.Index": 0})

        assert symtab.keys == {"Param", "Task"}
        assert isinstance(symtab.keys, set)

    def test_keys_empty_table(self) -> None:
        assert SymbolTable().keys == set()


class TestDottedPathLookup:
    """Test dotted path lookup in __getitem__, __contains__, and get."""

    def test_getitem_dotted(self) -> None:
        st = SymbolTable({"Param.X": 42})
        assert st["Param.X"] == ExprValue(42)

    def test_getitem_dotted_deep(self) -> None:
        st = SymbolTable({"A.B.C": "hello"})
        assert st["A.B.C"] == ExprValue("hello")

    def test_getitem_dotted_missing_raises(self) -> None:
        st = SymbolTable({"Param.X": 42})
        with pytest.raises(KeyError):
            st["Param.Y"]

    def test_contains_dotted(self) -> None:
        st = SymbolTable({"Param.X": 42, "Param.Y": "hi"})
        assert "Param.X" in st
        assert "Param.Y" in st
        assert "Param.Z" not in st

    def test_get_dotted(self) -> None:
        st = SymbolTable({"Param.X": 42})
        assert st.get("Param.X") == ExprValue(42)
        assert st.get("Param.Y") is None

    def test_simple_key_still_works(self) -> None:
        st = SymbolTable({"X": 42})
        assert "X" in st
        assert st["X"] == ExprValue(42)
        assert st.get("X") == ExprValue(42)

    def test_getitem_returns_subtable(self) -> None:
        st = SymbolTable({"Param.X": 42, "Param.Y": "hi"})
        param = st["Param"]
        assert isinstance(param, SymbolTable)

    def test_contains_namespace(self) -> None:
        st = SymbolTable({"Param.X": 42})
        assert "Param" in st
        assert "Param.X" in st
        assert "Other" not in st
