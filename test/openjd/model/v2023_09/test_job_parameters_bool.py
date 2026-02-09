# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobBoolParameterDefinition


class TestJobBoolParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "BOOL"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "description": "some text"}, id="description"
            ),
            pytest.param({"name": "Foo", "type": "BOOL", "default": True}, id="default true"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": False}, id="default false"),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "default": "true"}, id="default string true"
            ),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "default": "false"}, id="default string false"
            ),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "default": "yes"}, id="default string yes"
            ),
            pytest.param({"name": "Foo", "type": "BOOL", "default": "no"}, id="default string no"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": "on"}, id="default string on"),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "default": "off"}, id="default string off"
            ),
            pytest.param({"name": "Foo", "type": "BOOL", "default": "1"}, id="default string 1"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": "0"}, id="default string 0"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": 1}, id="default int 1"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": 0}, id="default int 0"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": 1.0}, id="default float 1.0"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": 0.0}, id="default float 0.0"),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "userInterface": {"control": "CHECK_BOX"}},
                id="user interface CHECK_BOX",
            ),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "BOOL",
                    "userInterface": {
                        "control": "CHECK_BOX",
                        "label": "Enable",
                        "groupLabel": "Options",
                    },
                    "default": False,
                    "description": "Enable feature",
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobBoolParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "STRING"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "BOOL"}, id="missing name"),
            pytest.param({"name": 12, "type": "BOOL"}, id="name not a string"),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "default": "maybe"}, id="default invalid string"
            ),
            pytest.param({"name": "Foo", "type": "BOOL", "default": 2}, id="default int 2"),
            pytest.param({"name": "Foo", "type": "BOOL", "default": 0.5}, id="default float 0.5"),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "BOOL", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobBoolParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "default_input,expected",
        [
            pytest.param(True, True, id="bool true"),
            pytest.param(False, False, id="bool false"),
            pytest.param(1, True, id="int 1"),
            pytest.param(0, False, id="int 0"),
            pytest.param(1.0, True, id="float 1.0"),
            pytest.param(0.0, False, id="float 0.0"),
            pytest.param("true", True, id="string true"),
            pytest.param("false", False, id="string false"),
            pytest.param("YES", True, id="string YES"),
            pytest.param("NO", False, id="string NO"),
            pytest.param("on", True, id="string on"),
            pytest.param("off", False, id="string off"),
            pytest.param("1", True, id="string 1"),
            pytest.param("0", False, id="string 0"),
        ],
    )
    def test_default_coercion(self, default_input: Any, expected: bool) -> None:
        result = _parse_model(
            model=JobBoolParameterDefinition,
            obj={"name": "Foo", "type": "BOOL", "default": default_input},
        )
        assert result.default is expected
        assert isinstance(result.default, bool)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(True, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="bool true"),
            pytest.param(
                False, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="bool false"
            ),
            pytest.param(
                "true", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string true"
            ),
            pytest.param(
                "false", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string false"
            ),
            pytest.param(
                "True", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string True"
            ),
            pytest.param(
                "FALSE", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string FALSE"
            ),
            pytest.param(
                "yes", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string yes"
            ),
            pytest.param("no", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string no"),
            pytest.param(
                "YES", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string YES"
            ),
            pytest.param("NO", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string NO"),
            pytest.param("on", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string on"),
            pytest.param(
                "off", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string off"
            ),
            pytest.param("1", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string 1"),
            pytest.param("0", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="string 0"),
            pytest.param(1, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="int 1"),
            pytest.param(0, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="int 0"),
            pytest.param(1.0, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="float 1.0"),
            pytest.param(0.0, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="float 0.0"),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobBoolParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(None, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="none type"),
            pytest.param(2, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="int 2"),
            pytest.param(-1, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="int -1"),
            pytest.param(0.5, JobBoolParameterDefinition(name="Foo", type="BOOL"), id="float 0.5"),
            pytest.param(
                "invalid", JobBoolParameterDefinition(name="Foo", type="BOOL"), id="invalid string"
            ),
            pytest.param(
                list(), JobBoolParameterDefinition(name="Foo", type="BOOL"), id="list type"
            ),
            pytest.param(
                dict(), JobBoolParameterDefinition(name="Foo", type="BOOL"), id="dict type"
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobBoolParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
