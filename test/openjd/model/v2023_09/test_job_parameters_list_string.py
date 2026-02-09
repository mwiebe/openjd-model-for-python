# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobListStringParameterDefinition


class TestJobListStringParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "LIST[STRING]"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "description": "list of strings"},
                id="description",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "default": ["a", "b"]}, id="default"
            ),
            pytest.param({"name": "Foo", "type": "LIST[STRING]", "minLength": 1}, id="min length"),
            pytest.param({"name": "Foo", "type": "LIST[STRING]", "maxLength": 10}, id="max length"),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "minLength": 1, "maxLength": 10},
                id="min and max length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "item": {"minLength": 1}},
                id="item min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "item": {"maxLength": 100}},
                id="item max length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "item": {"allowedValues": ["a", "b"]}},
                id="item allowed values",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[STRING]",
                    "userInterface": {"control": "LINE_EDIT_LIST"},
                },
                id="user interface LINE_EDIT_LIST",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobListStringParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "STRING"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "LIST[STRING]"}, id="missing name"),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "default": "not a list"},
                id="default not list",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "minLength": -1}, id="negative min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "maxLength": 0}, id="zero max length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "minLength": 10, "maxLength": 5},
                id="min greater than max",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "item": {"minLength": 0}},
                id="item min length zero",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[STRING]", "item": {"minLength": 10, "maxLength": 5}},
                id="item min greater than max",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobListStringParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                ["a", "b"],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]"),
                id="simple list",
            ),
            pytest.param(
                [],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]"),
                id="empty list",
            ),
            pytest.param(
                ["a"],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]", minLength=1),
                id="meets min",
            ),
            pytest.param(
                ["a", "b"],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]", maxLength=5),
                id="meets max",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobListStringParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobListStringParameterDefinition(name="Foo", type="LIST[STRING]"), id="none"
            ),
            pytest.param(
                "not a list",
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]"),
                id="string",
            ),
            pytest.param(
                [1, 2],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]"),
                id="list of ints",
            ),
            pytest.param(
                [],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]", minLength=1),
                id="below min",
            ),
            pytest.param(
                ["a", "b", "c"],
                JobListStringParameterDefinition(name="Foo", type="LIST[STRING]", maxLength=2),
                id="above max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobListStringParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
