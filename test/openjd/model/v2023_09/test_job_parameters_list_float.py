# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobListFloatParameterDefinition


class TestJobListFloatParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "LIST[FLOAT]"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "description": "list of floats"},
                id="description",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "default": [1.0, 2.5, 3.5]}, id="default"
            ),
            pytest.param({"name": "Foo", "type": "LIST[FLOAT]", "minLength": 1}, id="min length"),
            pytest.param({"name": "Foo", "type": "LIST[FLOAT]", "maxLength": 10}, id="max length"),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "item": {"minValue": 0.0}},
                id="item min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "item": {"maxValue": 100.0}},
                id="item max value",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "item": {"allowedValues": [1.0, 2.0, 3.0]}},
                id="item allowed values",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[FLOAT]",
                    "userInterface": {"control": "SPIN_BOX_LIST"},
                },
                id="user interface SPIN_BOX_LIST",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobListFloatParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "FLOAT"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "LIST[FLOAT]"}, id="missing name"),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "default": "not a list"},
                id="default not list",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "minLength": -1}, id="negative min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[FLOAT]", "item": {"minValue": 10.0, "maxValue": 5.0}},
                id="item min greater than max",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobListFloatParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                [1.0, 2.5],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]"),
                id="simple list",
            ),
            pytest.param(
                [], JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]"), id="empty list"
            ),
            pytest.param(
                [1.0],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]", minLength=1),
                id="meets min",
            ),
            pytest.param(
                [1.0, 2.0],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]", maxLength=5),
                id="meets max",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobListFloatParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]"), id="none"
            ),
            pytest.param(
                "not a list",
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]"),
                id="string",
            ),
            pytest.param(
                ["a", "b"],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]"),
                id="list of strings",
            ),
            pytest.param(
                [True, False],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]"),
                id="list of bools",
            ),
            pytest.param(
                [],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]", minLength=1),
                id="below min",
            ),
            pytest.param(
                [1.0, 2.0, 3.0],
                JobListFloatParameterDefinition(name="Foo", type="LIST[FLOAT]", maxLength=2),
                id="above max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobListFloatParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
