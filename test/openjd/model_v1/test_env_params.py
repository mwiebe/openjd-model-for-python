# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""ENV_PARAMS (RFC 0010, draft) through the Rust-backed ``openjd.model._v1``.

ENV_PARAMS exists only on the Rust path: the pure-Python ``openjd.model``
does not implement it and keeps rejecting it (see
``TestLegacyPathUnchanged``).

The conformance files under ``env_params_conformance/`` are copied from
openjd-specifications (``conformance-tests/2023-09/ENV_PARAMS/jobs/``). When
the specification checkout is present at ``OPENJD_SPECIFICATIONS_DIR`` (or the
sibling ``../openjd-specifications-ep``), ``TestConformanceTemplates`` also
decodes every ENV_PARAMS template test of that suite.
"""

from __future__ import annotations

import json
import os
import pickle
import re
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from openjd.expr import PathFormat, SerializedSymbolTable
from openjd.model._v1 import (
    check_environment_templates,
    create_job,
    create_job_with_environment_templates,
    decode_environment_template,
    decode_job_template,
)
from openjd.model._v1.errors import DecodeValidationError, ModelValidationError
from openjd.model._v1.job import (
    CreatedJob,
    DiscardedHostRequirement,
    Document,
    EnvironmentParameterValues,
    EnvironmentRef,
    HostRequirementKind,
)
from openjd.model._v1.types import CallerLimits, ModelExtension, ModelProfile, ValidationContext

_EXTS = ["ENV_PARAMS", "EXPR"]
_ALL_EXTS = ["TASK_CHUNKING", "REDACTED_ENV_VARS", "FEATURE_BUNDLE_1", "EXPR", "WRAP_ACTIONS"] + [
    "ENV_PARAMS"
]
_HERE = Path(__file__).parent
_CONFORMANCE_COPIES = _HERE / "env_params_conformance"


def _echo(*args: str) -> dict[str, Any]:
    return {"actions": {"onRun": {"command": "echo", "args": list(args)}}}


# Two Job Environments: an ON_REQUEST one whose Steps supply values, and an
# ALWAYS one whose default comes from a Job Parameter and that its own
# ``enableIf`` disables when the value is empty (the conda-env-params shape).
_TEMPLATE: dict[str, Any] = {
    "specificationVersion": "jobtemplate-2023-09",
    "extensions": _EXTS,
    "name": "EnvParamsJob",
    "parameterDefinitions": [{"name": "DefaultTool", "type": "STRING", "default": ""}],
    "jobEnvironments": [
        {
            "name": "Tool",
            "activation": "ON_REQUEST",
            "envParameterDefinitions": [
                {"name": "Flavor", "type": "STRING"},
                {"name": "Count", "type": "INT", "default": 1},
            ],
            "variables": {
                "TOOL_FLAVOR": "{{Env.Param.Flavor}}",
                "TOOL_COUNT": "{{Env.Param.Count}}",
            },
        },
        {
            "name": "Optional",
            "envParameterDefinitions": [
                {"name": "Packages", "type": "STRING", "default": "{{Param.DefaultTool}}"}
            ],
            "enableIf": "Env.Param.Packages != ''",
            "variables": {"OPTIONAL_PACKAGES": "{{Env.Param.Packages}}"},
        },
    ],
    "steps": [
        {
            "name": "Red",
            "dependencies": [
                {"environment": "Tool", "parameters": {"Flavor": "red", "Count": 2}},
                {"environment": "Optional", "parameters": {"Packages": "pkg-a"}},
            ],
            "script": _echo("red"),
        },
        {
            "name": "Blue",
            "dependencies": [{"environment": "Tool", "parameters": {"Flavor": "blue"}}],
            "script": _echo("blue"),
        },
        {
            "name": "Plain",
            "dependencies": [{"dependsOn": "Red"}, {"step": "Blue"}],
            "script": _echo("plain"),
        },
    ],
}

_CONDA_ENV_TEMPLATE: dict[str, Any] = {
    "specificationVersion": "environment-2023-09",
    "extensions": _EXTS,
    "parameterDefinitions": [{"name": "CondaChannels", "type": "STRING", "default": "conda-forge"}],
    "environment": {
        "name": "Conda",
        "envParameterDefinitions": [
            {"name": "Packages", "type": "STRING", "default": ""},
            {"name": "Channels", "type": "STRING", "default": "{{Param.CondaChannels}}"},
        ],
        "variables": {"CONDA_PACKAGES": "{{Env.Param.Packages}}"},
    },
}


def _job_template(template: dict[str, Any] = _TEMPLATE) -> Any:
    return decode_job_template(template=template, supported_extensions=_EXTS)


def _values(p: EnvironmentParameterValues) -> list[dict[str, Any]]:
    return json.loads(p.values.to_json_str())


class TestExtension:
    def test_env_params_member(self) -> None:
        assert ModelExtension.ENV_PARAMS.as_str() == "ENV_PARAMS"
        assert ModelExtension.from_str("ENV_PARAMS") == ModelExtension.ENV_PARAMS
        assert repr(ModelExtension.ENV_PARAMS) == "ModelExtension.ENV_PARAMS"

    def test_pickle(self) -> None:
        assert pickle.loads(pickle.dumps(ModelExtension.ENV_PARAMS)) == ModelExtension.ENV_PARAMS

    def test_profile_reports_it(self) -> None:
        jt = _job_template()
        assert jt.profile.has_extension(ModelExtension.ENV_PARAMS)


class TestDecode:
    def test_job_template(self) -> None:
        jt = _job_template()
        env = jt.jobEnvironments[0]
        assert env.name == "Tool"
        deps = jt.steps[0].dependencies
        assert [(d.depends_on, d.environment, d.required) for d in deps] == [
            (None, "Tool", True),
            (None, "Optional", True),
        ]
        assert repr(deps[0]) == 'StepDependency(environment="Tool")'
        # ``step:`` is the ENV_PARAMS synonym of ``dependsOn``.
        plain = jt.steps[2].dependencies
        assert [d.depends_on for d in plain] == ["Red", "Blue"]
        assert [d.dependsOn for d in plain] == ["Red", "Blue"]
        assert repr(plain[1]) == 'StepDependency(dependsOn="Blue")'

    def test_extension_must_be_supported(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            decode_job_template(template=_TEMPLATE, supported_extensions=["EXPR"])
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "extensions:\n"
            "\tUnsupported extension names: ENV_PARAMS"
        )

    def test_environment_template(self) -> None:
        et = decode_environment_template(template=_CONDA_ENV_TEMPLATE, supported_extensions=_EXTS)
        assert et.environment.name == "Conda"

    def test_environment_entry_cannot_be_pickled(self) -> None:
        dep = _job_template().steps[0].dependencies[0]
        with pytest.raises(TypeError) as exc:
            pickle.dumps(dep)
        assert str(exc.value) == "cannot pickle an ENV_PARAMS 'environment:' StepDependency entry"

    def test_depends_on_entry_still_pickles(self) -> None:
        dep = _job_template().steps[2].dependencies[0]
        assert pickle.loads(pickle.dumps(dep)).depends_on == "Red"


class TestCreateJob:
    def test_step_environment_sets_and_values(self) -> None:
        job = create_job(job_template=_job_template(), job_parameter_values={})
        red, blue, plain = job.steps
        tool = EnvironmentRef(document=Document.job_template(), environment="Tool")

        # Red enters both (the full list, so ``None``); Blue only Tool, because
        # Optional's own ``enableIf`` is false for it (its value defaults to
        # the empty DefaultTool); Plain requests nothing and Tool is ON_REQUEST.
        assert red.environments is None
        assert blue.environments == [tool]
        assert plain.environments == []

        assert [(p.environment, _values(p)) for p in red.environment_parameters or []] == [
            (
                "Tool",
                [
                    {"name": "Count", "type": "int", "value": "2"},
                    {"name": "Flavor", "type": "string", "value": "red"},
                ],
            ),
            ("Optional", [{"name": "Packages", "type": "string", "value": "pkg-a"}]),
        ]
        assert [(p.environment, _values(p)) for p in blue.environment_parameters or []] == [
            (
                "Tool",
                [
                    {"name": "Count", "type": "int", "value": "1"},
                    {"name": "Flavor", "type": "string", "value": "blue"},
                ],
            )
        ]
        assert plain.environment_parameters is None
        assert all(p.document == Document.job_template() for p in red.environment_parameters or [])

    def test_enters_environment(self) -> None:
        red, blue, plain = create_job(job_template=_job_template(), job_parameter_values={}).steps
        assert red.enters_environment("Tool") and red.enters_environment("Optional")
        assert blue.enters_environment("Tool") and not blue.enters_environment("Optional")
        assert not plain.enters_environment("Tool")
        assert not blue.enters_environment("Tool", Document.environment_template(0))
        # ``environments is None`` means "every Job Environment", and
        # openjd-rs answers True for any name in that case, even one the Job
        # does not have. Callers iterate ``Job.job_environments``.
        assert red.enters_environment("NotAJobEnvironment")

    def test_environment_parameters_for(self) -> None:
        red = create_job(job_template=_job_template(), job_parameter_values={}).steps[0]
        tool = red.environment_parameters_for("Tool")
        assert tool is not None and tool.environment == "Tool"
        assert red.environment_parameters_for("Tool", Document.job_template()) == tool
        assert red.environment_parameters_for("Missing") is None
        assert red.environment_parameters_for("Tool", Document.environment_template(0)) is None

    def test_session_sharing_predicates(self) -> None:
        job = create_job(job_template=_job_template(), job_parameter_values={})
        red, blue, plain = job.steps
        again = create_job(job_template=_job_template(), job_parameter_values={}).steps[0]
        assert red.same_environments(again) and red.environment_values_equal(again)
        assert not red.same_environments(blue)
        assert not red.environment_values_equal(blue)
        assert plain.same_environments(plain)

    def test_floats_written_differently_are_not_equal(self) -> None:
        # Template Schemas §3.2.2: a FLOAT keeps the text it was written with,
        # so "3.10" and "3.1" are different values, while white space around
        # the number is not part of its text.
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["ENV_PARAMS", "EXPR"],
            "name": "J",
            "jobEnvironments": [
                {
                    "name": "Py",
                    "envParameterDefinitions": [{"name": "V", "type": "FLOAT"}],
                    "variables": {"V": "{{Env.Param.V}}"},
                }
            ],
            "steps": [
                {
                    "name": name,
                    "dependencies": [{"environment": "Py", "parameters": {"V": value}}],
                    "script": {"actions": {"onRun": {"command": "x"}}},
                }
                for name, value in (("A", "3.10"), ("B", "3.1"), ("C", " 3.10 "))
            ],
        }
        a, b, c = create_job(job_template=_job_template(template), job_parameter_values={}).steps
        assert not a.environment_values_equal(b)
        assert a.environment_values_equal(c)
        a_values, b_values = a.environment_parameters_for("Py"), b.environment_parameters_for("Py")
        assert a_values is not None and b_values is not None
        assert not a_values.values_equal(b_values)

    def test_job_parameter_default_flows_into_env_param_default(self) -> None:
        job = create_job(
            job_template=_job_template(), job_parameter_values={"DefaultTool": "pkg-b"}
        )
        blue = job.steps[1]
        assert blue.environments is None  # Optional is now enabled for Blue
        optional = blue.environment_parameters_for("Optional")
        assert optional is not None
        assert _values(optional) == [{"name": "Packages", "type": "string", "value": "pkg-b"}]

    def test_job_environments_keep_env_param_references(self) -> None:
        job = create_job(job_template=_job_template(), job_parameter_values={})
        assert job.job_environments is not None
        tool = job.job_environments[0]
        assert tool.variables == {
            "TOOL_FLAVOR": "{{Env.Param.Flavor}}",
            "TOOL_COUNT": "{{Env.Param.Count}}",
        }
        assert tool.resolved_symtab is not None
        assert tool.resolved_symtab.to_json_str() == "[]"

    def test_missing_required_value(self) -> None:
        template = dict(_TEMPLATE)
        template["steps"] = [
            {"name": "S", "dependencies": [{"environment": "Tool"}], "script": _echo("s")}
        ]
        # Constraint 7 for a Job Environment is decided from the Steps' entries
        # alone, so template validation reports it.
        with pytest.raises(ModelValidationError) as exc:
            _job_template(template)
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0]:\n"
            "\tmust supply, in an 'environment:' dependency, every parameter without a default "
            "of each Environment that applies to it (every jobEnvironments entry with activation "
            "ALWAYS, each one with activation BY_DEFAULT that the Step does not decline, and each "
            "one with activation ON_REQUEST that the Step requests; Template Schemas §3.2 "
            "constraint 7), whatever that Environment's own enableIf is; "
            "missing: 'Flavor' of Environment 'Tool'."
        )


# With no Environment Template attached, a job-creation error is reported for
# ``JobTemplate`` at paths relative to it (openjd-rs one-pass error shape).
_CONDA_REQUIRED_MISSING = (
    "1 validation error for JobTemplate\n"
    "steps[0] -> dependencies[0] -> environment:\n"
    "\tnames Environment 'Conda', which is not a jobEnvironments entry of the Job Template, "
    "and no Environment Template is attached. The entry is required; set 'required: false' "
    "if the Step can run without the Environment (Template Schemas §3.2.1 item 2)."
)


def _external_template() -> Any:
    return _job_template(
        {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": _EXTS,
            "name": "External",
            "steps": [
                {
                    "name": "A",
                    "dependencies": [
                        {"environment": "Conda", "parameters": {"Packages": "ffmpeg=7"}},
                        {"environment": "Docker", "required": False, "parameters": {"Image": "x"}},
                    ],
                    "script": _echo("A"),
                },
                {"name": "B", "dependencies": [{"dependsOn": "A"}], "script": _echo("B")},
            ],
        }
    )


class TestCreateJobWithEnvironmentTemplates:
    def test_attached_values_and_documents(self) -> None:
        et = decode_environment_template(template=_CONDA_ENV_TEMPLATE, supported_extensions=_EXTS)
        created = create_job_with_environment_templates(
            job_template=_external_template(),
            job_parameter_values={},
            environment_templates=[(et, "queue")],
        )
        assert isinstance(created, CreatedJob)
        queue = Document.environment_template(0, "queue")
        assert created.environment_documents == [queue]
        assert [e.name for e in created.job.job_environments or []] == ["Conda"]
        a, b = created.job.steps
        conda = a.environment_parameters_for("Conda", queue)
        assert conda is not None
        assert conda.document == queue
        assert _values(conda) == [
            {"name": "Channels", "type": "string", "value": "conda-forge"},
            {"name": "Packages", "type": "string", "value": "ffmpeg=7"},
        ]
        # The attachment is ALWAYS, so B enters it too, with the defaults.
        b_conda = b.environment_parameters_for("Conda", queue)
        assert b_conda is not None
        assert _values(b_conda) == [
            {"name": "Channels", "type": "string", "value": "conda-forge"},
            {"name": "Packages", "type": "string", "value": ""},
        ]
        assert created.warnings == [
            "JobTemplate -> steps[0] -> dependencies[1] -> environment: names Environment "
            "'Docker', which is not a jobEnvironments entry of the Job Template, and none of the "
            "attached Environment Templates (queue) defines it. The entry has 'required: false', "
            "so it has no effect."
        ]
        assert [(d.environments, d.step_environments) for d in created.disabled_environments] == [
            ([], []),
            ([], []),
        ]
        assert repr(created) == 'CreatedJob(job="External", environments=1)'

    def test_unlabeled_attachment(self) -> None:
        et = decode_environment_template(template=_CONDA_ENV_TEMPLATE, supported_extensions=_EXTS)
        created = create_job_with_environment_templates(
            job_template=_external_template(), job_parameter_values={}, environment_templates=[et]
        )
        assert created.environment_documents == [Document.environment_template(0)]
        assert "(EnvironmentTemplate[0])" in created.warnings[0]

    def test_label_is_part_of_the_document(self) -> None:
        et = decode_environment_template(template=_CONDA_ENV_TEMPLATE, supported_extensions=_EXTS)
        created = create_job_with_environment_templates(
            job_template=_external_template(),
            job_parameter_values={},
            environment_templates=[(et, "queue")],
        )
        a = created.job.steps[0]
        assert a.environment_parameters_for("Conda", created.environment_documents[0]) is not None
        assert a.environment_parameters_for("Conda", Document.environment_template(0)) is None
        # A enters every Job Environment (environments is None), so
        # enters_environment cannot tell the documents apart here.
        assert a.environments is None

    def test_disabled_environments_lists_enable_if_false(self) -> None:
        created = create_job_with_environment_templates(
            job_template=_job_template(), job_parameter_values={}
        )
        assert [[e.environment for e in d.environments] for d in created.disabled_environments] == [
            [],
            ["Optional"],
            ["Optional"],
        ]

    def test_required_entry_with_nothing_attached(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            create_job(job_template=_external_template(), job_parameter_values={})
        assert str(exc.value) == _CONDA_REQUIRED_MISSING

    def test_rejects_other_items(self) -> None:
        with pytest.raises(TypeError) as exc:
            create_job_with_environment_templates(
                job_template=_external_template(),
                job_parameter_values={},
                environment_templates=["not a template"],
            )
        assert str(exc.value) == (
            "environment_templates items must be EnvironmentTemplate or "
            "(EnvironmentTemplate, label) tuples"
        )

    def test_check_environment_templates(self) -> None:
        et = decode_environment_template(template=_CONDA_ENV_TEMPLATE, supported_extensions=_EXTS)
        warnings = check_environment_templates(
            job_template=_external_template(), environment_templates=[(et, "queue")]
        )
        assert warnings == [
            "JobTemplate -> steps[0] -> dependencies[1] -> environment: names Environment "
            "'Docker', which is not a jobEnvironments entry of the Job Template, and none of the "
            "attached Environment Templates (queue) defines it. The entry has 'required: false', "
            "so it has no effect."
        ]
        with pytest.raises(ModelValidationError) as exc:
            check_environment_templates(job_template=_external_template(), environment_templates=[])
        assert str(exc.value) == _CONDA_REQUIRED_MISSING


# An Environment Template written before ENV_PARAMS: ``Conda`` declares no
# parameters.
_OLD_CONDA_ENV_TEMPLATE: dict[str, Any] = {
    "specificationVersion": "environment-2023-09",
    "parameterDefinitions": [{"name": "CondaPackages", "type": "STRING", "default": ""}],
    "environment": {"name": "Conda", "script": {"actions": {"onEnter": {"command": "x"}}}},
}

_IGNORED_WARNING = (
    "JobTemplate -> steps[0] -> dependencies[0] -> parameters: Environment 'Conda' (queue) "
    "declares no parameters, and this entry has 'required: false', so its parameters are "
    "ignored: Channels, Packages. The Step's Sessions get no values from it (Template Schemas "
    "§3.2.1 item 1)."
)


def _entry_template(required: bool | None) -> Any:
    entry: dict[str, Any] = {
        "environment": "Conda",
        "parameters": {"Packages": "{{ Param.L[5] }}", "Channels": ["a", "b"]},
    }
    if required is not None:
        entry["required"] = required
    return _job_template(
        {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": _EXTS,
            "name": "Ignored",
            "parameterDefinitions": [{"name": "L", "type": "LIST[INT]", "default": [1]}],
            "steps": [{"name": "A", "dependencies": [entry], "script": _echo("A")}],
        }
    )


class TestIgnoredParameters:
    """Template Schemas §3.2.1 item 1: an attached Environment that declares no
    parameters ignores an enabled ``required: false`` entry's parameters, with a
    warning, and is still entered; ``required: true`` stays an error."""

    def _old(self) -> Any:
        return decode_environment_template(
            template=_OLD_CONDA_ENV_TEMPLATE, supported_extensions=_EXTS
        )

    def test_job_creation_warns_and_enters(self) -> None:
        created = create_job_with_environment_templates(
            job_template=_entry_template(False),
            job_parameter_values={},
            environment_templates=[(self._old(), "queue")],
        )
        # The values are not resolved or checked: the index out of range and
        # the list for what would be a STRING are not errors.
        assert created.warnings == [_IGNORED_WARNING]
        step = created.job.steps[0]
        assert step.environment_parameters is None
        assert step.enters_environment("Conda", Document.environment_template(0, "queue"))
        statuses = created.environment_statuses[0]
        assert [(e.name, e.status.name) for e in statuses.environments] == [("Conda", "ENTERED")]
        assert statuses.not_found == []

    def test_check_gives_the_same_warning(self) -> None:
        assert check_environment_templates(
            job_template=_entry_template(False), environment_templates=[(self._old(), "queue")]
        ) == [_IGNORED_WARNING]

    @pytest.mark.parametrize("required", [True, None])
    def test_a_required_entry_is_rejected(self, required: bool | None) -> None:
        expected = (
            "1 validation error for Submission\n"
            "JobTemplate -> steps[0] -> dependencies[0] -> parameters:\n"
            "\tEnvironment 'Conda' (queue) declares no parameters, so this entry must not supply "
            "any; it supplies Channels, Packages."
        )
        jt = _entry_template(required)
        with pytest.raises(ModelValidationError) as exc:
            check_environment_templates(
                job_template=jt, environment_templates=[(self._old(), "queue")]
            )
        assert str(exc.value) == expected
        with pytest.raises(ModelValidationError) as exc:
            create_job_with_environment_templates(
                job_template=jt,
                job_parameter_values={},
                environment_templates=[(self._old(), "queue")],
            )
        assert str(exc.value) == expected

    def test_an_ignored_entry_still_requests_an_on_request_environment(self) -> None:
        # An ENV_PARAMS Environment Template whose ON_REQUEST Environment
        # declares no parameters: Step A's ignored entry requests it, so A's
        # Sessions enter it; Step B makes no request, so it is not listed.
        lic = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "extensions": _EXTS,
                "environment": {
                    "name": "Lic",
                    "activation": "ON_REQUEST",
                    "script": {"actions": {"onEnter": {"command": "x"}}},
                },
            },
            supported_extensions=_EXTS,
        )
        jt = _job_template(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": _EXTS,
                "name": "Requested",
                "steps": [
                    {
                        "name": "A",
                        "dependencies": [
                            {"environment": "Lic", "required": False, "parameters": {"P": "x"}}
                        ],
                        "script": _echo("A"),
                    },
                    {"name": "B", "script": _echo("B")},
                ],
            }
        )
        warning = (
            "JobTemplate -> steps[0] -> dependencies[0] -> parameters: Environment 'Lic' (lic) "
            "declares no parameters, and this entry has 'required: false', so its parameters are "
            "ignored: P. The Step's Sessions get no values from it (Template Schemas §3.2.1 item 1)."
        )
        assert check_environment_templates(
            job_template=jt, environment_templates=[(lic, "lic")]
        ) == [warning]
        created = create_job_with_environment_templates(
            job_template=jt, job_parameter_values={}, environment_templates=[(lic, "lic")]
        )
        assert created.warnings == [warning]
        doc = Document.environment_template(0, "lic")
        a, b = created.job.steps
        assert a.enters_environment("Lic", doc)
        assert not b.enters_environment("Lic", doc)
        assert [(e.name, e.status.name) for e in created.environment_statuses[0].environments] == [
            ("Lic", "ENTERED")
        ]
        assert created.environment_statuses[1].environments == []


class TestValueTypes:
    def test_document(self) -> None:
        jt_doc = Document.job_template()
        env_doc = Document.environment_template(2, "queue")
        assert jt_doc.is_job_template and jt_doc.index is None and jt_doc.label is None
        assert not env_doc.is_job_template and env_doc.index == 2 and env_doc.label == "queue"
        assert str(jt_doc) == "JobTemplate"
        assert str(env_doc) == "queue"
        assert str(Document.environment_template(1)) == "EnvironmentTemplate[1]"
        assert repr(env_doc) == 'Document.environment_template(2, "queue")'
        assert len({jt_doc, Document.job_template(), env_doc}) == 2
        # The label is part of equality, as in openjd-rs.
        assert Document.environment_template(2) != env_doc
        for doc in (jt_doc, env_doc, Document.environment_template(1)):
            assert pickle.loads(pickle.dumps(doc)) == doc

    def test_environment_ref(self) -> None:
        ref = EnvironmentRef(document=Document.job_template(), environment="Tool")
        assert ref.environment == "Tool" and ref.document == Document.job_template()
        assert ref == EnvironmentRef(document=Document.job_template(), environment="Tool")
        assert hash(ref) == hash(
            EnvironmentRef(document=Document.job_template(), environment="Tool")
        )
        assert repr(ref) == 'EnvironmentRef(document=Document.job_template(), environment="Tool")'
        assert pickle.loads(pickle.dumps(ref)) == ref

    def test_environment_parameter_values_round_trip(self) -> None:
        red = create_job(job_template=_job_template(), job_parameter_values={}).steps[0]
        assert red.environment_parameters is not None
        tool = red.environment_parameters[0]
        text = tool.to_json_str()
        assert json.loads(text) == {
            "document": {"kind": "JobTemplate"},
            "environment": "Tool",
            "values": [
                {"name": "Count", "type": "int", "value": "2"},
                {"name": "Flavor", "type": "string", "value": "red"},
            ],
        }
        again = EnvironmentParameterValues.from_json_str(text)
        assert again == tool and again.values_equal(tool)
        assert pickle.loads(pickle.dumps(tool)) == tool
        assert repr(tool) == 'EnvironmentParameterValues(environment="Tool", document=JobTemplate)'

    def test_environment_parameter_values_constructor(self) -> None:
        values = SerializedSymbolTable.from_json_str(
            '[{"name":"Frames","type":"range_expr","value":"1-3"}]'
        )
        a = EnvironmentParameterValues(environment="E", values=values)
        b = EnvironmentParameterValues(
            environment="E",
            values=SerializedSymbolTable.from_json_str(
                '[{"name":"Frames","type":"range_expr","value":"1,2,3"}]'
            ),
            document=Document.environment_template(0),
        )
        assert a.document == Document.job_template()
        # RANGE_EXPR compares by the integers it denotes (§3.2.2).
        assert a.values_equal(b)
        assert a != b

    def test_from_json_str_rejects_malformed(self) -> None:
        with pytest.raises(ValueError) as exc:
            EnvironmentParameterValues.from_json_str("{}")
        assert str(exc.value) == (
            "Failed to parse EnvironmentParameterValues JSON: missing field `document` at line 1 "
            "column 2"
        )


class TestValidationContext:
    """openjd-rs a8f9f233 removed the ENV_PARAMS path policy from ValidationContext."""

    @pytest.mark.parametrize(
        "keyword, value",
        [("submission_path_format", PathFormat.WINDOWS), ("allow_uri_path_values", True)],
    )
    def test_removed_keyword_is_a_type_error(self, keyword: str, value: Any) -> None:
        profile = ModelProfile(extensions=[ModelExtension.ENV_PARAMS])
        with pytest.raises(TypeError) as exc:
            ValidationContext(profile, **{keyword: value})
        assert str(exc.value) == (
            f"ValidationContext.__new__() got an unexpected keyword argument '{keyword}'"
        )

    @pytest.mark.parametrize(
        "name",
        [
            "submission_path_format",
            "allow_uri_path_values",
            "with_submission_path_format",
            "with_allow_uri_path_values",
        ],
    )
    def test_removed_attribute(self, name: str) -> None:
        ctx = ValidationContext(ModelProfile(extensions=[ModelExtension.ENV_PARAMS]))
        assert not hasattr(ctx, name)

    def test_repr(self) -> None:
        ctx = ValidationContext(
            ModelProfile(extensions=[ModelExtension.ENV_PARAMS]),
            caller_limits=CallerLimits(max_step_count=3),
        )
        # CallerLimits' repr prints Rust's Option spelling (Some(3)); that is
        # older than this change.
        assert repr(ctx) == (
            "ValidationContext(profile=ModelProfile(revision=V2023_09, extensions=[ENV_PARAMS]), "
            "caller_limits=CallerLimits(max_step_count=Some(3), max_env_count=None, "
            "max_step_environment_entries=None, max_task_count=None, max_step_script_size=None, "
            "max_environment_size=None, max_template_size=None, max_resolved_arg_len=None, "
            "max_resolved_data_len=None, "
            "max_eval_memory_bytes=None, max_eval_operations=None))"
        )

    def test_create_job_with_environment_templates_applies_the_callers_limits(self) -> None:
        jt = _job_template(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": _EXTS,
                "name": "Limits",
                "steps": [{"name": "S", "script": _echo("sixteen-chars-xx")}],
            }
        )
        ctx = ValidationContext(jt.profile, caller_limits=CallerLimits(max_resolved_arg_len=5))
        with pytest.raises(ModelValidationError) as exc:
            create_job_with_environment_templates(
                job_template=jt, job_parameter_values={}, validation_context=ctx
            )
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> script -> actions -> onRun -> args[0]:\n"
            "\tis 16 characters, exceeding the maximum of 5."
        )
        # Without the limit the same Job is created.
        create_job_with_environment_templates(job_template=jt, job_parameter_values={})

    def test_create_job_with_environment_templates_uses_the_callers_profile(self) -> None:
        jt = _job_template()
        with pytest.raises(ModelValidationError) as exc:
            create_job_with_environment_templates(
                job_template=jt,
                job_parameter_values={},
                validation_context=ValidationContext(ModelProfile(extensions=[])),
            )
        assert str(exc.value) == (
            "create_job requires a context enabling every extension the template declares: "
            "missing ENV_PARAMS, EXPR. An application that does not support an extension "
            "should reject the template at decode via its supported-extensions list."
        )

    def test_profile_and_limits_still_round_trip(self) -> None:
        limits = CallerLimits(max_step_count=3)
        ctx = ValidationContext(
            ModelProfile(extensions=[ModelExtension.ENV_PARAMS]), caller_limits=limits
        )
        assert pickle.loads(pickle.dumps(ctx)) == ctx
        assert ctx != ValidationContext(ModelProfile(extensions=[ModelExtension.ENV_PARAMS]))


# Values of every form, written literally in an ``environment:`` entry. Spec
# af53020, Template Schemas §4.5 item 3: a PATH value is used as given, with no
# absolute, empty, path-format or URI check.
_AS_GIVEN = [
    "rel/dir",
    "relative\\dir",
    "C:dir",
    "\\dir",
    "\\\\server\\share",
    "C:\\proj",
    "C:/proj",
    "/abs",
    "",
    "s3://bucket/key",
]


def _entries_template(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Two Steps, ``A`` and ``C`` with no dependencies and ``B`` with ``entries``."""
    run = _echo("x")
    return {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": _EXTS,
        "name": "Entries",
        "steps": [
            {"name": "A", "script": run},
            {"name": "C", "script": run},
            {"name": "B", "dependencies": entries, "script": run},
        ],
    }


def _optional(n: int) -> list[dict[str, Any]]:
    return [{"environment": f"Env{i}", "required": False} for i in range(n)]


class TestMaxStepEnvironmentEntries:
    """``CallerLimits.max_step_environment_entries`` reaches template validation."""

    @staticmethod
    def _decode(entries: list[dict[str, Any]], limit: int | None) -> Any:
        return decode_job_template(
            template=_entries_template(entries),
            supported_extensions=_EXTS,
            caller_limits=CallerLimits(max_step_environment_entries=limit),
        )

    def test_at_the_limit_is_accepted(self) -> None:
        jt = self._decode(_optional(3), 3)
        assert len(jt.steps[2].dependencies) == 3

    def test_one_over_is_rejected_at_the_dependencies_path(self) -> None:
        with pytest.raises(ModelValidationError) as excinfo:
            self._decode(_optional(4), 3)
        assert str(excinfo.value).endswith(
            "steps[2] -> dependencies:\n"
            "\texceeds caller limit of 3 'environment' entries (4 entries)."
        )

    def test_none_imposes_no_limit(self) -> None:
        jt = self._decode(_optional(100), None)
        assert len(jt.steps[2].dependencies) == 100

    def test_step_entries_are_not_counted(self) -> None:
        entries = [{"dependsOn": "A"}, {"step": "C"}, *_optional(1)]
        jt = self._decode(entries, 1)
        assert len(jt.steps[2].dependencies) == 3

    def test_disabled_entries_are_counted(self) -> None:
        """An entry disabled by a literal ``false`` or by an expression counts."""
        entries = [
            *_optional(1),
            {"environment": "Off", "required": False, "enableIf": False},
            {"environment": "Expr", "required": False, "enableIf": "1 == 2"},
        ]
        with pytest.raises(ModelValidationError) as excinfo:
            self._decode(entries, 2)
        assert str(excinfo.value).endswith(
            "steps[2] -> dependencies:\n"
            "\texceeds caller limit of 2 'environment' entries (3 entries)."
        )

    def test_default_caller_limits_impose_no_limit(self) -> None:
        jt = decode_job_template(
            template=_entries_template(_optional(100)), supported_extensions=_EXTS
        )
        deps = jt.steps[2].dependencies
        assert deps is not None and len(deps) == 100


def _as_given_template(entry: dict[str, Any], lets: list[str] | None = None) -> Any:
    step: dict[str, Any] = {
        "name": "S",
        "dependencies": [{"environment": "Mnt", "parameters": entry}],
        "script": _echo("S"),
    }
    if lets is not None:
        step["let"] = lets
    return _job_template(
        {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": _EXTS,
            "name": "AsGiven",
            "parameterDefinitions": [
                {"name": "Dir", "type": "PATH", "default": "/unused"},
                {"name": "Mounts", "type": "LIST[PATH]", "default": ["/unused"]},
            ],
            "jobEnvironments": [
                {
                    "name": "Mnt",
                    "activation": "ON_REQUEST",
                    "envParameterDefinitions": [
                        {"name": "Dir", "type": "PATH", "default": "/unused"},
                        {"name": "Mounts", "type": "LIST[PATH]", "default": ["/unused"]},
                    ],
                    "variables": {"MNT_DIR": "{{Env.RawParam.Dir}}"},
                }
            ],
            "steps": [step],
        }
    )


def _mnt_values(jt: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    job = create_job(job_template=jt, job_parameter_values=params or {})
    mnt = job.steps[0].environment_parameters_for("Mnt")
    assert mnt is not None
    return {v["name"]: v["value"] for v in _values(mnt)}


class TestPathValuesAsGiven:
    @pytest.mark.parametrize("value", _AS_GIVEN)
    def test_literal_value_is_stored_unchanged(self, value: str) -> None:
        jt = _as_given_template({"Dir": value, "Mounts": [value, "/m"]})
        assert _mnt_values(jt) == {"Dir": value, "Mounts": [value, "/m"]}

    @pytest.mark.parametrize("value", [v for v in _AS_GIVEN if "://" not in v])
    def test_single_expression_keeps_its_text(self, value: str) -> None:
        # Job Parameters still refuse URIs (preprocess_job_parameters), so the
        # URI form is covered by the literal test only.
        jt = _as_given_template({"Dir": "{{RawParam.Dir}}", "Mounts": "{{RawParam.Mounts}}"})
        got = _mnt_values(jt, {"Dir": value, "Mounts": [value, "C:\\x"]})
        assert got == {"Dir": value, "Mounts": [value, "C:\\x"]}

    def test_a_uri_from_a_string_job_parameter_keeps_its_text(self) -> None:
        jt = _job_template(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": _EXTS,
                "name": "Uri",
                "parameterDefinitions": [{"name": "S", "type": "STRING"}],
                "jobEnvironments": [
                    {
                        "name": "Mnt",
                        "activation": "ON_REQUEST",
                        "envParameterDefinitions": [{"name": "Dir", "type": "PATH"}],
                        "variables": {"MNT_DIR": "{{Env.RawParam.Dir}}"},
                    }
                ],
                "steps": [
                    {
                        "name": "S",
                        "dependencies": [
                            {"environment": "Mnt", "parameters": {"Dir": "{{Param.S}}"}}
                        ],
                        "script": _echo("S"),
                    }
                ],
            }
        )
        assert _mnt_values(jt, {"S": "s3://bucket/key"}) == {"Dir": "s3://bucket/key"}

    def test_a_uri_job_parameter_is_still_refused(self) -> None:
        # The Job Parameter rule (preprocess_job_parameters) is unchanged.
        jt = _as_given_template({"Dir": "{{RawParam.Dir}}"})
        with pytest.raises(DecodeValidationError) as exc:
            create_job_with_environment_templates(
                job_template=jt, job_parameter_values={"Dir": "s3://bucket/key"}
            )
        assert str(exc.value) == (
            "Parameter 'Dir': URI path values are not permitted. Got 's3://bucket/key'"
        )

    def test_single_expression_list_with_backslash_elements(self) -> None:
        jt = _as_given_template({"Mounts": "{{RawParam.Mounts}}"})
        got = _mnt_values(jt, {"Mounts": ["C:\\a\\b", "rel\\x", "", "\\\\s\\h"]})
        assert got["Mounts"] == ["C:\\a\\b", "rel\\x", "", "\\\\s\\h"]

    @pytest.mark.parametrize(
        "value, joined",
        [
            ("C:\\proj", "C:\\proj/x"),
            ("\\\\server\\share", "\\\\server\\share/x"),
            ("rel", "rel/x"),
            ("/abs/", "/abs/x"),
        ],
    )
    def test_path_operations_use_posix_semantics(self, value: str, joined: str) -> None:
        jt = _as_given_template({"Dir": "{{path(RawParam.Dir) / 'x'}}"})
        assert _mnt_values(jt, {"Dir": value})["Dir"] == joined

    def test_a_step_let_binding_uses_posix_semantics(self) -> None:
        jt = _as_given_template(
            {"Dir": "{{joined}}"}, lets=["joined = path(RawParam.Dir) / 'y' / 'z'"]
        )
        assert _mnt_values(jt, {"Dir": "C:\\proj"})["Dir"] == "C:\\proj/y/z"

    @pytest.mark.parametrize("value", _AS_GIVEN)
    def test_create_job_with_environment_templates_agrees(self, value: str) -> None:
        jt = _as_given_template({"Dir": value, "Mounts": [value, "\\\\s\\h"]})
        created = create_job_with_environment_templates(job_template=jt, job_parameter_values={})
        mnt = created.job.steps[0].environment_parameters_for("Mnt")
        assert mnt is not None
        assert {v["name"]: v["value"] for v in _values(mnt)} == {
            "Dir": value,
            "Mounts": [value, "\\\\s\\h"],
        }

    @staticmethod
    def _min_length_template(entry: str) -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": _EXTS,
            "name": "C",
            "parameterDefinitions": [{"name": "Dir", "type": "PATH", "default": "/unused"}],
            "jobEnvironments": [
                {
                    "name": "Mnt",
                    "activation": "ON_REQUEST",
                    "envParameterDefinitions": [{"name": "Dir", "type": "PATH", "minLength": 3}],
                    "variables": {"MNT_DIR": "{{Env.RawParam.Dir}}"},
                }
            ],
            "steps": [
                {
                    "name": "S",
                    "dependencies": [{"environment": "Mnt", "parameters": {"Dir": entry}}],
                    "script": _echo("S"),
                }
            ],
        }

    def test_a_literal_still_meets_its_constraints(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            _job_template(self._min_length_template("a"))
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> dependencies[0] -> parameters -> Dir:\n"
            "\tParameter 'Dir': value length 1 is less than minimum 3"
        )

    def test_a_resolved_value_still_meets_its_constraints(self) -> None:
        jt = _job_template(self._min_length_template("{{RawParam.Dir}}"))
        with pytest.raises(ModelValidationError) as exc:
            create_job(job_template=jt, job_parameter_values={"Dir": "a"})
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> dependencies[0] -> parameters -> Dir:\n"
            "\tParameter 'Dir': value length 1 is less than minimum 3"
        )


_FB1 = ["ENV_PARAMS", "EXPR", "FEATURE_BUNDLE_1"]


def _discard_env(name: str, param: str) -> dict[str, Any]:
    """A BY_DEFAULT Job Environment whose attribute and amount resolve to
    null unless its parameter is supplied."""
    low = name.lower()
    # One name keeps upper-case letters, so a binding that changed its case
    # would be seen.
    amount_name = "amount.custom.Lic" if name == "Lic" else f"amount.custom.{low}"
    return {
        "name": name,
        "envParameterDefinitions": [{"name": param, "type": "INT", "default": 0}],
        "hostRequirements": {
            "attributes": [
                {
                    "name": f"attr.custom.{low}",
                    "anyOf": f"{{{{ ['v'] if Env.Param.{param} > 0 else None }}}}",
                }
            ],
            "amounts": [
                {
                    "name": amount_name,
                    "min": f"{{{{ Env.Param.{param} if Env.Param.{param} > 0 else None }}}}",
                }
            ],
        },
        "variables": {f"{name.upper()}_N": f"{{{{Env.Param.{param}}}}}"},
    }


class TestDiscardedHostRequirements:
    """CreatedJob.discarded_host_requirements (Template Schemas §3.3)."""

    @staticmethod
    def _created() -> CreatedJob:
        jt = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": _FB1,
                "name": "Discard",
                "parameterDefinitions": [{"name": "G", "type": "STRING", "default": ""}],
                "jobEnvironments": [_discard_env("Lic", "Seats"), _discard_env("Gpu", "Count")],
                "steps": [
                    {
                        # Supplies nothing: its own two requirements and both
                        # Environments' are discarded.
                        "name": "S",
                        "hostRequirements": {
                            "attributes": [
                                {
                                    "name": "attr.custom.a",
                                    "anyOf": "{{ [Param.G] if Param.G != '' else None }}",
                                }
                            ],
                            "amounts": [
                                {"name": "amount.custom.kept", "max": 2},
                                {
                                    "name": "amount.custom.own",
                                    "max": "{{ 1 if Param.G != '' else None }}",
                                },
                            ],
                        },
                        "script": _echo("S"),
                    },
                    {
                        # Supplies Seats, so only Gpu's are discarded.
                        "name": "T",
                        "dependencies": [{"environment": "Lic", "parameters": {"Seats": 3}}],
                        "script": _echo("T"),
                    },
                ],
            },
            supported_extensions=_FB1,
        )
        att = _discard_env("Att", "Size")
        # Its attribute is written with allOf, the other form §3.3 discards.
        att["hostRequirements"]["attributes"][0] = {
            "name": "attr.custom.att",
            "allOf": "{{ ['v'] if Env.Param.Size > 0 else None }}",
        }
        et = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "extensions": _FB1,
                "environment": att,
            },
            supported_extensions=_FB1,
        )
        return create_job_with_environment_templates(
            job_template=jt, job_parameter_values={}, environment_templates=[et]
        )

    def test_per_step_own_first_then_each_environment_in_job_order_amounts_first(
        self,
    ) -> None:
        created = self._created()
        att = EnvironmentRef(document=Document.environment_template(0), environment="Att")
        lic = EnvironmentRef(document=Document.job_template(), environment="Lic")
        gpu = EnvironmentRef(document=Document.job_template(), environment="Gpu")
        amount, attribute = HostRequirementKind.AMOUNT, HostRequirementKind.ATTRIBUTE
        assert [
            [(d.environment, d.kind, d.name) for d in step]
            for step in created.discarded_host_requirements
        ] == [
            [
                (None, amount, "amount.custom.own"),
                (None, attribute, "attr.custom.a"),
                (att, amount, "amount.custom.att"),
                (att, attribute, "attr.custom.att"),
                (lic, amount, "amount.custom.Lic"),
                (lic, attribute, "attr.custom.lic"),
                (gpu, amount, "amount.custom.gpu"),
                (gpu, attribute, "attr.custom.gpu"),
            ],
            [
                (att, amount, "amount.custom.att"),
                (att, attribute, "attr.custom.att"),
                (gpu, amount, "amount.custom.gpu"),
                (gpu, attribute, "attr.custom.gpu"),
            ],
        ]

    def test_a_resolved_requirement_is_kept_on_the_step(self) -> None:
        t = self._created().job.steps[1]
        assert t.host_requirements is not None
        assert [(a.name, a.min, a.max) for a in t.host_requirements.amounts or []] == [
            ("amount.custom.Lic", 3.0, None)
        ]
        assert [a.name for a in t.host_requirements.attributes or []] == ["attr.custom.lic"]

    def test_repr_and_equality(self) -> None:
        own, _, att, _, lic = self._created().discarded_host_requirements[0][:5]
        assert repr(own) == (
            "DiscardedHostRequirement(environment=None, kind=HostRequirementKind.AMOUNT, "
            'name="amount.custom.own")'
        )
        assert repr(lic) == (
            "DiscardedHostRequirement(environment=EnvironmentRef("
            'document=Document.job_template(), environment="Lic"), '
            'kind=HostRequirementKind.AMOUNT, name="amount.custom.Lic")'
        )
        assert repr(att) == (
            "DiscardedHostRequirement(environment=EnvironmentRef("
            'document=Document.environment_template(0), environment="Att"), '
            'kind=HostRequirementKind.AMOUNT, name="amount.custom.att")'
        )
        assert isinstance(own, DiscardedHostRequirement)
        assert own == self._created().discarded_host_requirements[0][0]
        assert own != lic

    def test_kind(self) -> None:
        amount, attribute = HostRequirementKind.AMOUNT, HostRequirementKind.ATTRIBUTE
        assert (amount.name, attribute.name) == ("AMOUNT", "ATTRIBUTE")
        assert (repr(amount), repr(attribute)) == (
            "HostRequirementKind.AMOUNT",
            "HostRequirementKind.ATTRIBUTE",
        )
        assert (amount == 0, attribute == 1) == (True, True)
        assert len({amount, attribute, HostRequirementKind.AMOUNT}) == 2
        assert hash(amount) == hash(HostRequirementKind.AMOUNT)
        for k in (amount, attribute):
            assert pickle.loads(pickle.dumps(k)) is k or pickle.loads(pickle.dumps(k)) == k
        assert amount != attribute

    def test_exported_from_the_job_module(self) -> None:
        import openjd.model._v1.job as job_module

        assert {"DiscardedHostRequirement", "HostRequirementKind"} <= set(job_module.__all__)

    def test_a_step_without_any_has_an_empty_list(self) -> None:
        jt = _job_template()
        created = create_job_with_environment_templates(job_template=jt, job_parameter_values={})
        assert created.discarded_host_requirements == [[] for _ in created.job.steps]


class TestLegacyPathUnchanged:
    def test_legacy_model_rejects_env_params(self) -> None:
        from openjd.model import DecodeValidationError as LegacyDecodeValidationError
        from openjd.model import decode_job_template as legacy_decode
        from openjd.model.v2023_09 import ExtensionName

        assert "ENV_PARAMS" not in {e.value for e in ExtensionName}
        with pytest.raises(LegacyDecodeValidationError) as exc:
            legacy_decode(template=_TEMPLATE, supported_extensions=_EXTS)
        assert re.match(
            r"\d+ validation errors for JobTemplate\nextensions:\n"
            r"\tUnsupported extension names: ENV_PARAMS\n",
            str(exc.value),
        ), str(exc.value)


def _specification_dir() -> Path | None:
    configured = os.environ.get("OPENJD_SPECIFICATIONS_DIR")
    candidates = [Path(configured)] if configured else []
    candidates.append(_HERE.parents[3] / "openjd-specifications-ep")
    for c in candidates:
        suite = c / "conformance-tests" / "2023-09" / "ENV_PARAMS"
        if suite.is_dir():
            return suite
    return None


_SUITE = _specification_dir()


def _suite_files(kind: str) -> list[Path]:
    if _SUITE is None:
        return []
    return sorted((_SUITE / kind).iterdir())


class TestConformanceCopies:
    """Job creation for the copied conformance job tests."""

    @staticmethod
    def _load(name: str) -> dict[str, Any]:
        return yaml.safe_load((_CONFORMANCE_COPIES / name).read_text())

    def _create(self, test: dict[str, Any]) -> CreatedJob:
        jt = decode_job_template(template=test["template"], supported_extensions=_ALL_EXTS)
        envs = [
            decode_environment_template(template=e, supported_extensions=_ALL_EXTS)
            for e in test.get("environments", [])
        ]
        return create_job_with_environment_templates(
            job_template=jt,
            job_parameter_values=dict(test.get("parameters", {})),
            environment_templates=envs,
        )

    def test_example_execution_per_step_values(self) -> None:
        created = self._create(self._load("3.2.2--example-execution-per-step-values.test.yaml"))
        doc = Document.environment_template(0)
        packages = []
        for step in created.job.steps:
            conda = step.environment_parameters_for("Conda", doc)
            assert conda is not None
            packages.append(
                {v["name"]: v["value"] for v in _values(conda)}["Packages"],
            )
        assert packages == ["ffmpeg=7", "colmap=3.11"]
        decode, solve = created.job.steps
        assert decode.same_environments(solve)
        assert not decode.environment_values_equal(solve)

    def test_enable_if_false_not_entered(self) -> None:
        created = self._create(self._load("3.2--enable-if-false-not-entered.test.yaml"))
        step = created.job.steps[0]
        assert step.environments == []
        assert not step.enters_environment("Lic")

    def test_external_required_missing(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            self._create(self._load("3.2.1--external-required-missing.invalid.test.yaml"))
        assert str(exc.value) == _CONDA_REQUIRED_MISSING

    @pytest.mark.parametrize(
        "name, expected",
        [
            (
                "4.5--list-path-mixed-formats.test.yaml",
                {"Dirs": ["/mnt/a", "D:\\b", "\\\\server\\share\\c", "rel/d"]},
            ),
            ("4.5--path-relative-windows-drive.test.yaml", {"Dir": "C:dir"}),
            ("4.5--relative-literal-path-default.test.yaml", {"Dir": "relative/dir"}),
            ("4.5--relative-path-value.test.yaml", {"Dir": "relative/dir"}),
        ],
    )
    def test_path_value_used_as_given(self, name: str, expected: dict[str, Any]) -> None:
        created = self._create(self._load(name))
        mnt = created.job.steps[0].environment_parameters_for(
            "Mnt", Document.environment_template(0)
        )
        assert mnt is not None
        assert {v["name"]: v["value"] for v in _values(mnt)} == expected


@pytest.mark.skipif(_SUITE is None, reason="openjd-specifications ENV_PARAMS suite not found")
class TestConformanceTemplates:
    """Every ENV_PARAMS template conformance test of the specification checkout,
    decoded as ``openjd check`` does with no Environment Templates."""

    @pytest.mark.parametrize("path", _suite_files("job_templates"), ids=lambda p: p.name)
    def test_job_template(self, path: Path) -> None:
        template = yaml.safe_load(path.read_text())
        if ".invalid." in path.name:
            with pytest.raises((DecodeValidationError, ModelValidationError)):
                decode_job_template(template=template, supported_extensions=_ALL_EXTS)
        else:
            decode_job_template(template=template, supported_extensions=_ALL_EXTS)

    @pytest.mark.parametrize("path", _suite_files("env_templates"), ids=lambda p: p.name)
    def test_environment_template(self, path: Path) -> None:
        template = yaml.safe_load(path.read_text())
        if ".invalid." in path.name:
            with pytest.raises((DecodeValidationError, ModelValidationError)):
                decode_environment_template(template=template, supported_extensions=_ALL_EXTS)
        else:
            decode_environment_template(template=template, supported_extensions=_ALL_EXTS)
