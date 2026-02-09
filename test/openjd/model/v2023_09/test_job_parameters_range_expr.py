# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobRangeExprParameterDefinition


class TestJobRangeExprParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "RANGE_EXPR"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "description": "frame range"},
                id="description",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-100"}, id="default simple range"
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-100:10"},
                id="default skip range",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1,3,5,7"}, id="default list"
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-10,20-30:2"}, id="default mixed"
            ),
            pytest.param({"name": "Foo", "type": "RANGE_EXPR", "minLength": 1}, id="min length"),
            pytest.param({"name": "Foo", "type": "RANGE_EXPR", "maxLength": 100}, id="max length"),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "minLength": 1, "maxLength": 100},
                id="min and max length",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "minLength": 5, "maxLength": 5},
                id="min equals max",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-100", "minLength": 5},
                id="default meets min",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-100", "maxLength": 10},
                id="default meets max",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "userInterface": {"control": "LINE_EDIT"}},
                id="user interface LINE_EDIT",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "RANGE_EXPR",
                    "userInterface": {
                        "control": "LINE_EDIT",
                        "label": "Frames",
                        "groupLabel": "Range",
                    },
                    "default": "1-100",
                    "minLength": 1,
                    "maxLength": 1024,
                    "description": "Frame range to render",
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobRangeExprParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "STRING"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "RANGE_EXPR"}, id="missing name"),
            pytest.param({"name": 12, "type": "RANGE_EXPR"}, id="name not a string"),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "invalid"}, id="invalid default"
            ),
            pytest.param({"name": "Foo", "type": "RANGE_EXPR", "default": ""}, id="empty default"),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": 123}, id="default not string"
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "minLength": 0}, id="min length zero"
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "maxLength": 0}, id="max length zero"
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "minLength": 10, "maxLength": 5},
                id="min greater than max",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-10", "minLength": 10},
                id="default shorter than min",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "default": "1-100", "maxLength": 3},
                id="default longer than max",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "userInterface": {"control": "UNSUPPORTED"}},
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "RANGE_EXPR", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobRangeExprParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                "1-100",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="simple range",
            ),
            pytest.param(
                "1-100:10",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="skip range",
            ),
            pytest.param(
                "1,3,5,7", JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"), id="list"
            ),
            pytest.param(
                "1-10,20-30:2",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="mixed",
            ),
            pytest.param(
                "1",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="single value",
            ),
            pytest.param(
                "-5-5",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="negative range",
            ),
            pytest.param(
                "1-100",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR", minLength=5),
                id="meets min length",
            ),
            pytest.param(
                "1-100",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR", maxLength=10),
                id="meets max length",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobRangeExprParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"), id="none type"
            ),
            pytest.param(
                123, JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"), id="int type"
            ),
            pytest.param(
                "invalid",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="invalid string",
            ),
            pytest.param(
                "",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="empty string",
            ),
            pytest.param(
                "1.5-2.5",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="float range",
            ),
            pytest.param(
                list(),
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="list type",
            ),
            pytest.param(
                dict(),
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR"),
                id="dict type",
            ),
            pytest.param(
                "1-10",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR", minLength=10),
                id="shorter than min",
            ),
            pytest.param(
                "1-100",
                JobRangeExprParameterDefinition(name="Foo", type="RANGE_EXPR", maxLength=3),
                id="longer than max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobRangeExprParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
