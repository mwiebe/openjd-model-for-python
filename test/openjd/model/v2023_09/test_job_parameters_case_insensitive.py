# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobTemplate, JobParameterType
from openjd.model.v2023_09._model import ModelParsingContext


class TestJobParameterTypeCaseInsensitivity:
    """Tests for case-insensitive job parameter type names and RFC 7 types.

    - Base types (STRING, INT, FLOAT, PATH) work without EXPR in uppercase only
    - RFC 7 types (BOOL, RANGE_EXPR, LIST[*]) require EXPR extension
    - Case-insensitivity for all types requires EXPR extension
    """

    # Base types that work without EXPR (uppercase only)
    BASE_TYPES = [
        ("STRING", JobParameterType.STRING),
        ("INT", JobParameterType.INT),
        ("FLOAT", JobParameterType.FLOAT),
        ("PATH", JobParameterType.PATH),
    ]

    # RFC 7 types that require EXPR extension
    RFC7_TYPES = [
        ("BOOL", JobParameterType.BOOL),
        ("RANGE_EXPR", JobParameterType.RANGE_EXPR),
        ("LIST[STRING]", JobParameterType.LIST_STRING),
        ("LIST[INT]", JobParameterType.LIST_INT),
        ("LIST[FLOAT]", JobParameterType.LIST_FLOAT),
        ("LIST[PATH]", JobParameterType.LIST_PATH),
        ("LIST[BOOL]", JobParameterType.LIST_BOOL),
        ("LIST[LIST[INT]]", JobParameterType.LIST_LIST_INT),
    ]

    # Case variations for all types (lowercase/mixed case require EXPR)
    CASE_VARIATIONS = [
        ("string", "STRING"),
        ("String", "STRING"),
        ("int", "INT"),
        ("Int", "INT"),
        ("float", "FLOAT"),
        ("Float", "FLOAT"),
        ("path", "PATH"),
        ("Path", "PATH"),
        ("bool", "BOOL"),
        ("Bool", "BOOL"),
        ("range_expr", "RANGE_EXPR"),
        ("Range_Expr", "RANGE_EXPR"),
        ("list[string]", "LIST[STRING]"),
        ("List[String]", "LIST[STRING]"),
        ("list[int]", "LIST[INT]"),
        ("List[Int]", "LIST[INT]"),
        ("list[float]", "LIST[FLOAT]"),
        ("List[Float]", "LIST[FLOAT]"),
        ("list[path]", "LIST[PATH]"),
        ("List[Path]", "LIST[PATH]"),
        ("list[bool]", "LIST[BOOL]"),
        ("List[Bool]", "LIST[BOOL]"),
        ("list[list[int]]", "LIST[LIST[INT]]"),
        ("List[List[Int]]", "LIST[LIST[INT]]"),
    ]

    @pytest.mark.parametrize("type_str,expected", BASE_TYPES, ids=[t for t, _ in BASE_TYPES])
    def test_base_types_work_without_expr(self, type_str: str, expected: JobParameterType) -> None:
        """Base types (STRING, INT, FLOAT, PATH) should work without EXPR extension."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": [{"name": "Param", "type": type_str}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        result = _parse_model(model=JobTemplate, obj=template)
        assert result.parameterDefinitions is not None
        assert result.parameterDefinitions[0].type == expected

    @pytest.mark.parametrize("type_str,expected", RFC7_TYPES, ids=[t for t, _ in RFC7_TYPES])
    def test_rfc7_types_fail_without_expr(self, type_str: str, expected: JobParameterType) -> None:
        """RFC 7 types should fail without EXPR extension."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": [{"name": "Param", "type": type_str}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        with pytest.raises(ValidationError) as exc_info:
            _parse_model(model=JobTemplate, obj=template)
        assert "requires the EXPR extension" in str(exc_info.value)

    @pytest.mark.parametrize("type_str,expected", RFC7_TYPES, ids=[t for t, _ in RFC7_TYPES])
    def test_rfc7_types_work_with_expr(self, type_str: str, expected: JobParameterType) -> None:
        """RFC 7 types should work with EXPR extension."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [{"name": "Param", "type": type_str}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        ctx = ModelParsingContext(supported_extensions={"EXPR"})
        result = _parse_model(model=JobTemplate, obj=template, context=ctx)
        assert result.parameterDefinitions is not None
        assert result.parameterDefinitions[0].type == expected

    @pytest.mark.parametrize("type_str,upper", CASE_VARIATIONS, ids=[t for t, _ in CASE_VARIATIONS])
    def test_non_uppercase_types_fail_without_expr(self, type_str: str, upper: str) -> None:
        """Non-uppercase types should fail without EXPR extension."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": [{"name": "Param", "type": type_str}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        with pytest.raises(ValidationError) as exc_info:
            _parse_model(model=JobTemplate, obj=template)
        assert "requires the EXPR extension" in str(exc_info.value)

    @pytest.mark.parametrize("type_str,upper", CASE_VARIATIONS, ids=[t for t, _ in CASE_VARIATIONS])
    def test_non_uppercase_types_work_with_expr(self, type_str: str, upper: str) -> None:
        """Non-uppercase types should work with EXPR extension."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [{"name": "Param", "type": type_str}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        ctx = ModelParsingContext(supported_extensions={"EXPR"})
        result = _parse_model(model=JobTemplate, obj=template, context=ctx)
        # Verify it parsed to the correct uppercase enum
        assert result.parameterDefinitions is not None
        assert result.parameterDefinitions[0].type.value == upper

    def test_error_message_for_rfc7_type(self) -> None:
        """Error message for RFC 7 type should mention EXPR extension."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": [{"name": "Param", "type": "BOOL"}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        with pytest.raises(ValidationError) as exc_info:
            _parse_model(model=JobTemplate, obj=template)
        error_str = str(exc_info.value)
        assert "BOOL" in error_str
        assert "EXPR" in error_str

    def test_error_message_for_case_insensitive(self) -> None:
        """Error message for case-insensitive type should suggest uppercase."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "parameterDefinitions": [{"name": "Param", "type": "string"}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        with pytest.raises(ValidationError) as exc_info:
            _parse_model(model=JobTemplate, obj=template)
        error_str = str(exc_info.value)
        assert "STRING" in error_str  # Suggests uppercase
        assert "EXPR" in error_str  # Suggests extension
