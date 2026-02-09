# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobListListIntParameterDefinition


class TestJobListListIntParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "LIST[LIST[INT]]"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "description": "adjacency list"},
                id="description",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "default": [[1, 2], [3]]}, id="default"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "default": []}, id="default empty"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "default": [[]]},
                id="default with empty inner",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "minLength": 1}, id="min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "maxLength": 10}, id="max length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "minLength": 1, "maxLength": 10},
                id="min and max length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "item": {"minLength": 1}},
                id="item min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "item": {"maxLength": 5}},
                id="item max length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "item": {"item": {"minValue": 0}}},
                id="item item min value",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "item": {"item": {"maxValue": 100}}},
                id="item item max value",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[LIST[INT]]",
                    "item": {"item": {"allowedValues": [1, 2, 3]}},
                },
                id="item item allowed values",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[LIST[INT]]",
                    "userInterface": {
                        "control": "HIDDEN",
                        "label": "Dependencies",
                        "groupLabel": "Graph",
                    },
                    "default": [[1, 2], [0], []],
                    "minLength": 1,
                    "maxLength": 100,
                    "item": {
                        "minLength": 0,
                        "maxLength": 10,
                        "item": {"minValue": 0, "maxValue": 99},
                    },
                    "description": "Task dependency adjacency list",
                },
                id="all fields",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobListListIntParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "LIST[INT]"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "LIST[LIST[INT]]"}, id="missing name"),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "default": "not a list"},
                id="default not list",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "default": [1, 2, 3]},
                id="default not nested list",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "minLength": -1},
                id="negative min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "maxLength": 0}, id="zero max length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "minLength": 10, "maxLength": 5},
                id="min greater than max",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "item": {"minLength": -1}},
                id="item negative min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "item": {"maxLength": 0}},
                id="item zero max length",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[LIST[INT]]",
                    "item": {"minLength": 10, "maxLength": 5},
                },
                id="item min greater than max",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[LIST[INT]]",
                    "item": {"item": {"minValue": 10, "maxValue": 5}},
                },
                id="item item min greater than max",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[LIST[INT]]",
                    "userInterface": {"control": "UNSUPPORTED"},
                },
                id="unsupported user interface control",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "userInterface": {"label": ""}},
                id="user interface label too short",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[LIST[INT]]", "userInterface": {"label": "a" * 65}},
                id="user interface label too long",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobListListIntParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                [[1, 2], [3]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="simple nested list",
            ),
            pytest.param(
                [],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="empty outer list",
            ),
            pytest.param(
                [[]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="empty inner list",
            ),
            pytest.param(
                [[1]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]", minLength=1),
                id="meets outer min",
            ),
            pytest.param(
                [[1], [2]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]", maxLength=5),
                id="meets outer max",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobListListIntParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None,
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="none",
            ),
            pytest.param(
                "not a list",
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="string",
            ),
            pytest.param(
                [1, 2, 3],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="flat list of ints",
            ),
            pytest.param(
                [["a", "b"]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="nested list of strings",
            ),
            pytest.param(
                [[True, False]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]"),
                id="nested list of bools",
            ),
            pytest.param(
                [],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]", minLength=1),
                id="below outer min",
            ),
            pytest.param(
                [[1], [2], [3]],
                JobListListIntParameterDefinition(name="Foo", type="LIST[LIST[INT]]", maxLength=2),
                id="above outer max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobListListIntParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                [[]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"minLength": 1}
                ),
                id="inner list below min length",
            ),
            pytest.param(
                [[1, 2, 3]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"maxLength": 2}
                ),
                id="inner list above max length",
            ),
            pytest.param(
                [[-1]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"item": {"minValue": 0}}
                ),
                id="item below min value",
            ),
            pytest.param(
                [[101]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"item": {"maxValue": 100}}
                ),
                id="item above max value",
            ),
            pytest.param(
                [[4]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"item": {"allowedValues": [1, 2, 3]}}
                ),
                id="item not in allowed values",
            ),
        ],
    )
    def test_check_constraints_item_raises(
        self, value: Any, parameter: JobListListIntParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                [[1]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"minLength": 1}
                ),
                id="inner list meets min length",
            ),
            pytest.param(
                [[1, 2]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"maxLength": 2}
                ),
                id="inner list meets max length",
            ),
            pytest.param(
                [[0, 50, 100]],
                JobListListIntParameterDefinition(
                    name="Foo",
                    type="LIST[LIST[INT]]",
                    item={"item": {"minValue": 0, "maxValue": 100}},
                ),
                id="items within value range",
            ),
            pytest.param(
                [[1, 2, 3]],
                JobListListIntParameterDefinition(
                    name="Foo", type="LIST[LIST[INT]]", item={"item": {"allowedValues": [1, 2, 3]}}
                ),
                id="items in allowed values",
            ),
        ],
    )
    def test_check_constraints_item_noraise(
        self, value: Any, parameter: JobListListIntParameterDefinition
    ) -> None:
        parameter._check_constraints(value)
