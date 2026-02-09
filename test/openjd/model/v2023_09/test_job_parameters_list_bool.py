# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobListBoolParameterDefinition


class TestJobListBoolParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "LIST[BOOL]"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "description": "list of bools"},
                id="description",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": [True, False]}, id="default"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": [1, 0]}, id="default int 1/0"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": ["yes", "no"]},
                id="default string yes/no",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": ["on", "off"]},
                id="default string on/off",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": [True, 1, "yes", 0.0, "off"]},
                id="default mixed types",
            ),
            pytest.param({"name": "Foo", "type": "LIST[BOOL]", "minLength": 1}, id="min length"),
            pytest.param({"name": "Foo", "type": "LIST[BOOL]", "maxLength": 10}, id="max length"),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "minLength": 1, "maxLength": 10},
                id="min and max length",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[BOOL]",
                    "userInterface": {"control": "CHECK_BOX_LIST"},
                },
                id="user interface CHECK_BOX_LIST",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[BOOL]",
                    "userInterface": {
                        "control": "CHECK_BOX_LIST",
                        "label": "Flags",
                        "groupLabel": "Options",
                    },
                    "default": [True, False, True],
                    "minLength": 1,
                    "maxLength": 10,
                    "description": "A list of boolean flags",
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobListBoolParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "BOOL"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "LIST[BOOL]"}, id="missing name"),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": "not a list"},
                id="default not list",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": ["maybe"]},
                id="default invalid string item",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "default": [2]},
                id="default invalid int item",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "minLength": -1}, id="negative min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "maxLength": 0}, id="zero max length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "minLength": 10, "maxLength": 5},
                id="min greater than max",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[BOOL]", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobListBoolParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "default_input,expected",
        [
            pytest.param([True, False], [True, False], id="bool list"),
            pytest.param([1, 0], [True, False], id="int list"),
            pytest.param([1.0, 0.0], [True, False], id="float list"),
            pytest.param(["yes", "no"], [True, False], id="string yes/no"),
            pytest.param(["on", "off"], [True, False], id="string on/off"),
            pytest.param(
                [True, 1, "yes", 0.0, "off"], [True, True, True, False, False], id="mixed"
            ),
            pytest.param([], [], id="empty"),
        ],
    )
    def test_default_coercion(self, default_input: Any, expected: list[bool]) -> None:
        result = _parse_model(
            model=JobListBoolParameterDefinition,
            obj={"name": "Foo", "type": "LIST[BOOL]", "default": default_input},
        )
        assert result.default == expected
        assert all(isinstance(v, bool) for v in result.default)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                [True, False],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="simple list",
            ),
            pytest.param(
                [], JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"), id="empty list"
            ),
            pytest.param(
                [True],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]", minLength=1),
                id="meets min",
            ),
            pytest.param(
                [True, False],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]", maxLength=5),
                id="meets max",
            ),
            pytest.param(
                ["true", "false"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="string true/false",
            ),
            pytest.param(
                ["yes", "no"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="string yes/no",
            ),
            pytest.param(
                ["on", "off"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="string on/off",
            ),
            pytest.param(
                ["1", "0"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="string 1/0",
            ),
            pytest.param(
                ["YES", "NO", "True", "FALSE"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="mixed case strings",
            ),
            pytest.param(
                [True, "yes", "0", False],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="mixed bool and strings",
            ),
            pytest.param(
                [1, 0],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="int 1/0",
            ),
            pytest.param(
                [1.0, 0.0],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="float 1.0/0.0",
            ),
            pytest.param(
                [1, 0, 1, 1, 0, 0, 0, 1],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="compact int array",
            ),
            pytest.param(
                [True, 1, "yes", 0.0, "off"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="mixed all types",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobListBoolParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"), id="none"
            ),
            pytest.param(
                "not a list",
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="string",
            ),
            pytest.param(
                ["invalid", "strings"],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="list of invalid strings",
            ),
            pytest.param(
                [2, 3],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="list of invalid ints",
            ),
            pytest.param(
                [0.5, 1.5],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]"),
                id="list of invalid floats",
            ),
            pytest.param(
                [],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]", minLength=1),
                id="below min",
            ),
            pytest.param(
                [True, False, True],
                JobListBoolParameterDefinition(name="Foo", type="LIST[BOOL]", maxLength=2),
                id="above max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobListBoolParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
