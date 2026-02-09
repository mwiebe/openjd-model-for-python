# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import JobListPathParameterDefinition


class TestJobListPathParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "LIST[PATH]"}, id="minimal required"),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "description": "list of paths"},
                id="description",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp/a", "/tmp/b"]}, id="default"
            ),
            pytest.param({"name": "Foo", "type": "LIST[PATH]", "minLength": 1}, id="min length"),
            pytest.param({"name": "Foo", "type": "LIST[PATH]", "maxLength": 10}, id="max length"),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "objectType": "FILE"}, id="object type FILE"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "objectType": "DIRECTORY"},
                id="object type DIRECTORY",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "dataFlow": "IN"}, id="data flow IN"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "dataFlow": "OUT"}, id="data flow OUT"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "item": {"minLength": 1}},
                id="item min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "item": {"maxLength": 100}},
                id="item max length",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[PATH]",
                    "userInterface": {"control": "CHOOSE_INPUT_FILE_LIST"},
                },
                id="user interface CHOOSE_INPUT_FILE_LIST",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "type": "LIST[PATH]",
                    "userInterface": {"control": "CHOOSE_DIRECTORY_LIST"},
                },
                id="user interface CHOOSE_DIRECTORY_LIST",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "userInterface": {"control": "HIDDEN"}},
                id="user interface HIDDEN",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        _parse_model(model=JobListPathParameterDefinition, obj=data)

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "Foo", "type": "PATH"}, id="wrong type"),
            pytest.param({"name": "Foo"}, id="missing type"),
            pytest.param({"type": "LIST[PATH]"}, id="missing name"),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "default": "not a list"},
                id="default not list",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "minLength": -1}, id="negative min length"
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "item": {"minLength": 0}},
                id="item min length zero",
            ),
            pytest.param(
                {"name": "Foo", "type": "LIST[PATH]", "item": {"minLength": 10, "maxLength": 5}},
                id="item min greater than max",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=JobListPathParameterDefinition, obj=data)
        assert len(excinfo.value.errors()) > 0

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                ["/tmp/a", "/tmp/b"],
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]"),
                id="simple list",
            ),
            pytest.param(
                [], JobListPathParameterDefinition(name="Foo", type="LIST[PATH]"), id="empty list"
            ),
            pytest.param(
                ["/tmp/a"],
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]", minLength=1),
                id="meets min",
            ),
            pytest.param(
                ["/tmp/a", "/tmp/b"],
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]", maxLength=5),
                id="meets max",
            ),
        ],
    )
    def test_check_constraints_noraise(
        self, value: Any, parameter: JobListPathParameterDefinition
    ) -> None:
        parameter._check_constraints(value)

    @pytest.mark.parametrize(
        "value,parameter",
        [
            pytest.param(
                None, JobListPathParameterDefinition(name="Foo", type="LIST[PATH]"), id="none"
            ),
            pytest.param(
                "not a list",
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]"),
                id="string",
            ),
            pytest.param(
                [1, 2],
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]"),
                id="list of ints",
            ),
            pytest.param(
                [],
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]", minLength=1),
                id="below min",
            ),
            pytest.param(
                ["/a", "/b", "/c"],
                JobListPathParameterDefinition(name="Foo", type="LIST[PATH]", maxLength=2),
                id="above max",
            ),
        ],
    )
    def test_check_constraints_raises(
        self, value: Any, parameter: JobListPathParameterDefinition
    ) -> None:
        with pytest.raises(ValueError):
            parameter._check_constraints(value)
