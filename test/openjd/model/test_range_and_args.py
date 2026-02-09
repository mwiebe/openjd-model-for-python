# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for null skipping and list flattening in range fields and args."""

import pytest
from openjd.model import decode_job_template, create_job, ParameterValue
from openjd.model.v2023_09 import ModelParsingContext
from openjd.expr import SymbolTable
from openjd.model._format_strings import FormatString
from openjd.expr import get_default_library


def make_range_template(range_expr, param_type="INT", params=None, extensions=None):
    """Create a minimal job template with a task parameter range."""
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "Test",
        "steps": [
            {
                "name": "Test",
                "parameterSpace": {
                    "taskParameterDefinitions": [
                        {"name": "X", "type": param_type, "range": range_expr}
                    ]
                },
                "script": {"actions": {"onRun": {"command": "echo", "args": ["{{Task.Param.X}}"]}}},
            }
        ],
    }
    if extensions:
        template["extensions"] = extensions
    if params:
        template["parameterDefinitions"] = params
    return template


def get_range(template_dict, param_values=None, extensions=None):
    """Decode template, create job, and return the range values."""
    template = decode_job_template(template=template_dict, supported_extensions=extensions)
    pv = {k: ParameterValue(type=v[0], value=v[1]) for k, v in (param_values or {}).items()}
    job = create_job(job_template=template, job_parameter_values=pv)
    return list(job.steps[0].parameterSpace.taskParameterDefinitions["X"].range)


def eval_expr(expr, symbols=None):
    """Evaluate a format string expression with EXPR extension."""
    context = ModelParsingContext(supported_extensions=["EXPR"])
    fs = FormatString(expr, context=context)
    symtab = SymbolTable(symbols) if symbols else SymbolTable()
    return fs.resolve(symtab=symtab, library=get_default_library())


class TestRangeNullSkipping:
    """Test null skipping in task parameter range fields."""

    @pytest.mark.parametrize(
        "include,expected",
        [
            ("true", [1, 2, 5, 10]),
            ("false", [1, 2, 10]),
        ],
    )
    def test_int_null_skipping(self, include, expected):
        template = make_range_template(
            [1, 2, "{{ 5 if Param.Include == 'true' else null }}", 10],
            params=[{"name": "Include", "type": "STRING", "default": "true"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"Include": ("STRING", include)}, ["EXPR"]) == expected

    @pytest.mark.parametrize(
        "include,expected",
        [
            ("true", ["a", "b", "c"]),
            ("false", ["a", "c"]),
        ],
    )
    def test_string_null_skipping(self, include, expected):
        template = make_range_template(
            ["a", "{{ 'b' if Param.Include == 'true' else null }}", "c"],
            param_type="STRING",
            params=[{"name": "Include", "type": "STRING", "default": "false"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"Include": ("STRING", include)}, ["EXPR"]) == expected


class TestRangeListFlattening:
    """Test list flattening in task parameter range fields."""

    def test_int_list_flattening(self):
        template = make_range_template([1, "{{ [2, 3, 4] }}", 10], extensions=["EXPR"])
        assert get_range(template, extensions=["EXPR"]) == [1, 2, 3, 4, 10]

    def test_string_list_flattening(self):
        template = make_range_template(
            ["a", "{{ ['b', 'c'] }}", "d"], param_type="STRING", extensions=["EXPR"]
        )
        assert get_range(template, extensions=["EXPR"]) == ["a", "b", "c", "d"]


class TestRangeCombined:
    """Test combined null skipping and list flattening."""

    @pytest.mark.parametrize(
        "include,expected",
        [
            ("true", [1, 2, 3, 10]),
            ("false", [1, 10]),
        ],
    )
    def test_null_and_list_combined(self, include, expected):
        template = make_range_template(
            [1, "{{ [2, 3] if Param.IncludeMiddle == 'true' else null }}", 10],
            params=[{"name": "IncludeMiddle", "type": "STRING", "default": "false"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"IncludeMiddle": ("STRING", include)}, ["EXPR"]) == expected


class TestArgsNullSkipping:
    """Test null skipping in action args via FormatString.resolve()."""

    @pytest.mark.parametrize("expr", ["{{ null }}", "{{ None }}"])
    def test_null_expressions_return_is_null(self, expr):
        assert eval_expr(expr).is_null

    def test_non_null_expression(self):
        result = eval_expr("done")
        assert not result.is_null
        assert result.to_string() == "done"

    @pytest.mark.parametrize(
        "verbose,is_null,value",
        [
            (True, False, "--verbose"),
            (False, True, None),
        ],
    )
    def test_conditional_null_args(self, verbose, is_null, value):
        result = eval_expr(
            "{{ '--verbose' if Param.Verbose else null }}", {"Param.Verbose": verbose}
        )
        assert result.is_null == is_null
        if not is_null:
            assert result.to_string() == value


class TestArgsListFlattening:
    """Test list flattening in action args via FormatString.resolve()."""

    def test_list_args_returned(self):
        from openjd.expr import TypeCode

        result = eval_expr("{{ ['--quality', '5'] }}")
        assert result.type.type_code == TypeCode.LIST
        assert [str(p) for p in result.item()] == ["--quality", "5"]

    @pytest.mark.parametrize(
        "quality,is_null,expected",
        [
            ("5", False, ["--quality", "5"]),
            ("", True, None),
        ],
    )
    def test_conditional_list_args(self, quality, is_null, expected):
        from openjd.expr import TypeCode

        result = eval_expr(
            "{{ ['--quality', Param.Quality] if Param.Quality != '' else null }}",
            {"Param.Quality": quality},
        )
        assert result.is_null == is_null
        if not is_null:
            assert result.type.type_code == TypeCode.LIST
            assert [str(p) for p in result.item()] == expected


class TestArgsScalarCoercion:
    """Test scalar coercion in interpolated args."""

    def test_int_coerced_to_string_in_interpolation(self):
        context = ModelParsingContext(supported_extensions=["EXPR"])
        fs = FormatString("Frame {{ Param.Frame }}", context=context)
        symtab = SymbolTable({"Param.Frame": 42})
        assert fs.resolve(symtab=symtab).to_string() == "Frame 42"

    def test_list_in_interpolation_converts_to_string(self):
        """Lists in string interpolation are converted to string representation."""
        context = ModelParsingContext(supported_extensions=["EXPR"])
        fs = FormatString("prefix {{ [1, 2, 3] }}", context=context)
        result = fs.resolve(symtab=SymbolTable())
        assert result.to_string() == "prefix [1, 2, 3]"


class TestRangeWithoutExprExtension:
    """Test range field resolution without EXPR extension."""

    def test_range_without_expr_extension(self):
        template = make_range_template(
            "{{Param.Start}}-10",
            params=[{"name": "Start", "type": "INT", "default": "1"}],
        )
        assert get_range(template, {"Start": ("INT", "1")}) == list(range(1, 11))


class TestRangeArithmeticWithIntParams:
    """Test arithmetic in range expressions with INT parameters."""

    def test_subtraction_in_range_expression(self):
        template = make_range_template(
            "0-{{Param.End - 1}}",
            params=[{"name": "End", "type": "INT", "default": "10"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"End": ("INT", "10")}, ["EXPR"]) == list(range(0, 10))

    def test_floor_division_in_range_expression(self):
        template = make_range_template(
            "0-{{(Param.Total - 1) // Param.Chunk}}",
            params=[
                {"name": "Total", "type": "INT", "default": "100"},
                {"name": "Chunk", "type": "INT", "default": "10"},
            ],
            extensions=["EXPR"],
        )
        params = {"Total": ("INT", "100"), "Chunk": ("INT", "10")}
        assert get_range(template, params, ["EXPR"]) == list(range(0, 10))

    def test_complex_arithmetic_in_range_step(self):
        template = make_range_template(
            "{{Param.Start}}-{{Param.End - 1}}:{{Param.ChunkSize}}",
            params=[
                {"name": "Start", "type": "INT", "default": "0"},
                {"name": "End", "type": "INT", "default": "100"},
                {"name": "ChunkSize", "type": "INT", "default": "10"},
            ],
            extensions=["EXPR"],
        )
        params = {"Start": ("INT", "0"), "End": ("INT", "100"), "ChunkSize": ("INT", "10")}
        assert get_range(template, params, ["EXPR"]) == list(range(0, 100, 10))


class TestPathParameterTypes:
    """Test that PATH parameters have correct types."""

    def test_rawparam_path_is_string(self):
        template = make_range_template(
            "{{ [RawParam.InputFile.upper()] }}",
            param_type="STRING",
            params=[{"name": "InputFile", "type": "PATH"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"InputFile": ("PATH", "scene.exr")}, ["EXPR"]) == ["SCENE.EXR"]


class TestNonPathParameterTypes:
    """Test that non-PATH parameters have same type for Param and RawParam."""

    def test_int_param_and_rawparam_support_arithmetic(self):
        template = make_range_template(
            "{{Param.Count * 2}}-{{RawParam.Count + 5}}:-1",
            params=[{"name": "Count", "type": "INT", "default": "10"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"Count": ("INT", "10")}, ["EXPR"]) == list(range(20, 14, -1))

    def test_float_param_and_rawparam_support_arithmetic(self):
        template = make_range_template(
            "{{ [Param.Scale * 2, RawParam.Scale + 0.5] }}",
            param_type="FLOAT",
            params=[{"name": "Scale", "type": "FLOAT", "default": "2.5"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"Scale": ("FLOAT", "2.5")}, ["EXPR"]) == [5.0, 3.0]

    def test_string_param_and_rawparam_are_string_type(self):
        template = make_range_template(
            "{{ [Param.Name.upper(), RawParam.Name.upper()] }}",
            param_type="STRING",
            params=[{"name": "Name", "type": "STRING", "default": "test"}],
            extensions=["EXPR"],
        )
        assert get_range(template, {"Name": ("STRING", "hello")}, ["EXPR"]) == ["HELLO", "HELLO"]
