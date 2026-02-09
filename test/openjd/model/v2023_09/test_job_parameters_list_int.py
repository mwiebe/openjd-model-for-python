# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobListIntParameterDefinition


class TestJobListIntParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "LIST[INT]"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "description": "list of ints"},
                id="description",
            ),
            pytest.param({"name": "Foo", "type": "LIST[INT]", "default": [1, 2, 3]}, id="default"),
            pytest.param({"name": "Foo", "type": "LIST[INT]", "minLength": 1}, id="min length"),
            pytest.param({"name": "Foo", "type": "LIST[INT]", "maxLength": 10}, id="max length"),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "item": {"minValue": 0}}, id="item min value"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "item": {"maxValue": 100}}, id="item max value"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "item": {"allowedValues": [1, 2, 3]}},
                id="item allowed values",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "userInterface": {"control": "SPIN_BOX_LIST"}},
                id="user interface SPIN_BOX_LIST",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobListIntParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "INT"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "LIST[INT]"}, id="missing name"),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "default": "not a list"}, id="default not list"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "minLength": -1}, id="negative min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[INT]", "item": {"minValue": 10, "maxValue": 5}},
                id="item min greater than max",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobListIntParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                [1, 2, 3],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]"),
                id="simple list",
            ),
            pytest.param(
                [], JobListIntParameterDefinition(name="Foo", type="LIST[INT]"), id="empty list"
            ),
            pytest.param(
                [1],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]", minLength=1),
                id="meets min",
            ),
            pytest.param(
                [1, 2],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]", maxLength=5),
                id="meets max",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobListIntParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobListIntParameterDefinition(name="Foo", type="LIST[INT]"), id="none"
            ),
            pytest.param(
                "not a list",
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]"),
                id="string",
            ),
            pytest.param(
                ["a", "b"],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]"),
                id="list of strings",
            ),
            pytest.param(
                [True, False],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]"),
                id="list of bools",
            ),
            pytest.param(
                [],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]", minLength=1),
                id="below min",
            ),
            pytest.param(
                [1, 2, 3],
                JobListIntParameterDefinition(name="Foo", type="LIST[INT]", maxLength=2),
                id="above max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobListIntParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
