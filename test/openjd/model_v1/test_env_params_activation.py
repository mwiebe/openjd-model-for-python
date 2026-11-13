# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""ENV_PARAMS ``activation``, ``exclusiveGroup`` and the one-pass job-creation
error shape, through the Rust-backed ``openjd.model._v1`` (openjd-rs-ep
c0333380, spec 87be017).

- ``EnvironmentActivation`` and ``TemplateEnvironment.activation``: an
  Environment without ``activation`` is ``BY_DEFAULT`` (Template Schemas §4
  item 4), which a Step can decline with a disabled ``environment:`` entry.
- ``TemplateEnvironment.exclusive_group`` (§4 item 7): of the Environments of a
  group a Step's Sessions would enter, only the first in the Job's Environment
  order is entered. The others are *superseded* for that Step. They are listed
  in ``CreatedJob.disabled_environments``, which does not say whether an
  Environment was disabled by its ``enableIf`` or superseded;
  ``CreatedJob.environment_statuses`` does (``test_env_params_statuses.py``).
- Job-creation errors are one ``ModelValidationError`` in §7.4.1 step order:
  ``for JobTemplate`` at Job-Template-relative paths with nothing attached, and
  ``for Submission`` with every path starting at its document otherwise, for
  every Job Template, ENV_PARAMS or not.
- ``TemplateAttributeRequirement.any_of`` / ``all_of`` hold one ``FormatString``
  for the ``<ListExpressionString>`` form (§3.3.2).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Optional

import pytest
import yaml  # type: ignore[import-untyped]

from openjd.expr import FormatString
from openjd.model._v1 import (
    create_job,
    create_job_with_environment_templates,
    decode_environment_template,
    decode_job_template,
)
from openjd.model._v1.errors import DecodeValidationError, ModelValidationError
from openjd.model._v1.job import CreatedJob, Document, EnvironmentRef
from openjd.model._v1.template import (
    EnvironmentActivation,
    TemplateAttributeRequirement,
    TemplateEnvironment,
)

_EXTS = ["ENV_PARAMS", "EXPR"]
_ALL_EXTS = ["TASK_CHUNKING", "REDACTED_ENV_VARS", "FEATURE_BUNDLE_1", "EXPR", "WRAP_ACTIONS"] + [
    "ENV_PARAMS"
]
_COPIES = Path(__file__).parent / "env_params_conformance"
_ECHO = {"actions": {"onRun": {"command": "echo"}}}
_JOB = Document.job_template()


def _env(name: str, **fields: Any) -> dict[str, Any]:
    return {"name": name, "variables": {"V": name}, **fields}


def _job_template(
    envs: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    params: Optional[list[dict[str, Any]]] = None,
) -> Any:
    template: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "extensions": _EXTS,
        "name": "J",
        "steps": steps,
    }
    if envs:
        template["jobEnvironments"] = envs
    if params:
        template["parameterDefinitions"] = params
    return decode_job_template(template=template, supported_extensions=_EXTS)


def _env_template(name: str, **fields: Any) -> Any:
    return decode_environment_template(
        template={
            "specificationVersion": "environment-2023-09",
            "extensions": _EXTS,
            "environment": _env(name, **fields),
        },
        supported_extensions=_EXTS,
    )


def _refs(*names: str, document: Document = _JOB) -> list[EnvironmentRef]:
    return [EnvironmentRef(document=document, environment=n) for n in names]


def _missing(param: str, env: str) -> str:
    """The constraint 7 message for a Job Environment."""
    return (
        "\tmust supply, in an 'environment:' dependency, every parameter without a default of "
        "each Environment that applies to it (every jobEnvironments entry with activation "
        "ALWAYS, each one with activation BY_DEFAULT that the Step does not decline, and each "
        "one with activation ON_REQUEST that the Step requests; Template Schemas §3.2 "
        "constraint 7), whatever that Environment's own enableIf is; "
        f"missing: '{param}' of Environment '{env}'."
    )


# Supplies B's INT Seats with a value that does not convert.
_SEATS_MANY = {"environment": "B", "parameters": {"Seats": "many"}}


def _create_copy(name: str) -> CreatedJob:
    test = yaml.safe_load((_COPIES / name).read_text())
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


class TestEnvironmentActivation:
    def test_members(self) -> None:
        members = [
            EnvironmentActivation.ALWAYS,
            EnvironmentActivation.BY_DEFAULT,
            EnvironmentActivation.ON_REQUEST,
        ]
        assert [m.name for m in members] == ["ALWAYS", "BY_DEFAULT", "ON_REQUEST"]
        assert [m.value for m in members] == ["ALWAYS", "BY_DEFAULT", "ON_REQUEST"]
        assert [repr(m) for m in members] == [
            "EnvironmentActivation.ALWAYS",
            "EnvironmentActivation.BY_DEFAULT",
            "EnvironmentActivation.ON_REQUEST",
        ]
        assert len(set(members)) == 3
        assert EnvironmentActivation.ALWAYS != EnvironmentActivation.BY_DEFAULT

    @pytest.mark.parametrize("member", ["ALWAYS", "BY_DEFAULT", "ON_REQUEST"])
    def test_pickle(self, member: str) -> None:
        value = getattr(EnvironmentActivation, member)
        assert pickle.loads(pickle.dumps(value)) == value

    def test_module(self) -> None:
        assert EnvironmentActivation.__module__ == "openjd.model._v1.template"


class TestTemplateEnvironmentFields:
    def test_decoded_activation_and_group(self) -> None:
        jt = _job_template(
            [
                _env("A", exclusiveGroup="G"),
                _env("B", activation="ON_REQUEST", exclusiveGroup="G"),
                _env("C", activation="ALWAYS"),
                _env("D", activation="BY_DEFAULT"),
            ],
            [{"name": "S", "script": _ECHO}],
        )
        envs = jt.job_environments
        assert [e.activation for e in envs] == [
            EnvironmentActivation.BY_DEFAULT,  # absent: the default
            EnvironmentActivation.ON_REQUEST,
            EnvironmentActivation.ALWAYS,
            EnvironmentActivation.BY_DEFAULT,
        ]
        assert [e.exclusive_group for e in envs] == ["G", "G", None, None]
        assert [e.exclusiveGroup for e in envs] == ["G", "G", None, None]

    def test_environment_template(self) -> None:
        env = _env_template("Conda", activation="ON_REQUEST", exclusiveGroup="Soft").environment
        assert env.activation == EnvironmentActivation.ON_REQUEST
        assert env.exclusive_group == "Soft"

    def test_without_env_params(self) -> None:
        jt = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "J",
                "jobEnvironments": [_env("A")],
                "steps": [{"name": "S", "script": _ECHO}],
            }
        )
        assert jt.job_environments is not None
        env = jt.job_environments[0]
        assert env.activation == EnvironmentActivation.BY_DEFAULT
        assert env.exclusive_group is None

    @pytest.mark.parametrize("member", ["ALWAYS", "BY_DEFAULT", "ON_REQUEST"])
    def test_constructor_and_pickle(self, member: str) -> None:
        activation = getattr(EnvironmentActivation, member)
        env = TemplateEnvironment(name="X", activation=activation, exclusive_group="G")
        assert env.activation == activation
        assert env.exclusive_group == "G"
        assert env.__reduce__()[1][1] == {
            "name": "X",
            "activation": activation,
            "exclusive_group": "G",
        }
        copy = pickle.loads(pickle.dumps(env))
        assert copy.name == "X"
        assert copy.activation == activation
        assert copy.exclusive_group == "G"

    def test_absent_activation_stays_absent_through_pickle(self) -> None:
        # The getter applies the default; the pickled form keeps the field
        # absent, since template validation rejects `activation` without
        # ENV_PARAMS.
        env = TemplateEnvironment(name="Y")
        assert env.activation == EnvironmentActivation.BY_DEFAULT
        assert env.exclusive_group is None
        assert env.__reduce__()[1][1] == {"name": "Y"}
        assert pickle.loads(pickle.dumps(env)).activation == EnvironmentActivation.BY_DEFAULT


class TestByDefault:
    def test_entered_by_every_step(self) -> None:
        jt = _job_template(
            [_env("Lic")],
            [{"name": "A", "script": _ECHO}, {"name": "B", "script": _ECHO}],
        )
        job = create_job(job_template=jt, job_parameter_values={})
        assert [s.environments for s in job.steps] == [None, None]
        assert all(s.enters_environment("Lic") for s in job.steps)

    def test_disabled_entry_declines(self) -> None:
        jt = _job_template(
            [_env("Lic")],
            [
                {
                    "name": "A",
                    "dependencies": [{"environment": "Lic", "enableIf": False}],
                    "script": _ECHO,
                },
                {"name": "B", "script": _ECHO},
            ],
        )
        created = create_job_with_environment_templates(job_template=jt, job_parameter_values={})
        a, b = created.job.steps
        assert a.environments == []
        assert not a.enters_environment("Lic")
        # B enters every Job Environment, which openjd-rs writes as None.
        assert b.environments is None and b.enters_environment("Lic")
        # A declined Environment is not "disabled" (§3.2.2): it is not listed.
        assert [d.environments for d in created.disabled_environments] == [[], []]

    def test_disabled_entry_by_expression_declines(self) -> None:
        jt = _job_template(
            [_env("Lic")],
            [
                {
                    "name": "A",
                    "dependencies": [{"environment": "Lic", "enableIf": "Param.UseLic"}],
                    "script": _ECHO,
                }
            ],
            params=[{"name": "UseLic", "type": "BOOL", "default": True}],
        )
        on = create_job(job_template=jt, job_parameter_values={})
        off = create_job(job_template=jt, job_parameter_values={"UseLic": "false"})
        assert on.steps[0].enters_environment("Lic")
        assert not off.steps[0].enters_environment("Lic")

    def test_always_cannot_be_declined(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            _job_template(
                [_env("Lic", activation="ALWAYS")],
                [
                    {
                        "name": "S",
                        "dependencies": [{"environment": "Lic", "enableIf": False}],
                        "script": _ECHO,
                    }
                ],
            )
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> dependencies[0] -> enableIf:\n"
            "\tis false, so Step 'S' would decline Environment 'Lic', whose activation is "
            "ALWAYS: no Step can leave out an ALWAYS Environment (Template Schemas §3.2 item 3.2)."
        )

    def test_conformance_copy_disabled_literal(self) -> None:
        created = _create_copy("3.2--by-default-entry-disabled-literal-not-entered.test.yaml")
        assert created.job.steps[0].environments == []


class TestExclusiveGroup:
    def test_first_job_environment_of_a_group_is_entered(self) -> None:
        jt = _job_template(
            [_env("A", exclusiveGroup="G"), _env("B", exclusiveGroup="G"), _env("C")],
            [{"name": "S", "script": _ECHO}],
        )
        created = create_job_with_environment_templates(job_template=jt, job_parameter_values={})
        step = created.job.steps[0]
        assert step.environments == _refs("A", "C")
        assert step.enters_environment("A") and not step.enters_environment("B")
        # The superseded one is listed with those enableIf disabled.
        assert created.disabled_environments[0].environments == _refs("B")

    def test_a_disabled_member_falls_through(self) -> None:
        jt = _job_template(
            [_env("A", exclusiveGroup="G", enableIf=False), _env("B", exclusiveGroup="G")],
            [{"name": "S", "script": _ECHO}],
        )
        created = create_job_with_environment_templates(job_template=jt, job_parameter_values={})
        assert created.job.steps[0].environments == _refs("B")
        assert created.disabled_environments[0].environments == _refs("A")

    def test_superseded_is_held_to_constraint_7_but_its_values_are_not_checked(self) -> None:
        # B is superseded by A for S, but it still applies to S (it is
        # BY_DEFAULT and S does not decline it), so constraint 7 holds for it
        # whatever its exclusiveGroup: S must supply its Seats, which has no
        # default. Being disabled for S, B's values are not checked
        # (constraint 6).
        envs = [
            _env("A", exclusiveGroup="G"),
            _env(
                "B", exclusiveGroup="G", envParameterDefinitions=[{"name": "Seats", "type": "INT"}]
            ),
        ]
        with pytest.raises(ModelValidationError) as exc:
            _job_template(envs, [{"name": "S", "script": _ECHO}])
        assert str(exc.value) == "1 validation error for JobTemplate\nsteps[0]:\n" + _missing(
            "Seats", "B"
        )

        supplies = [{"name": "S", "dependencies": [_SEATS_MANY], "script": _ECHO}]
        created = create_job_with_environment_templates(
            job_template=_job_template(envs, supplies), job_parameter_values={}
        )
        step = created.job.steps[0]
        assert step.environments == _refs("A")
        assert step.environment_parameters_for("B") is None
        assert created.disabled_environments[0].environments == _refs("B")
        # Without A, B is entered and the same value is checked.
        with pytest.raises(ModelValidationError) as exc:
            create_job_with_environment_templates(
                job_template=_job_template(envs[1:], supplies), job_parameter_values={}
            )
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> dependencies[0] -> parameters -> Seats:\n"
            "\tis not a valid INT value: Cannot parse 'many' as integer"
        )

    def test_attached_environment_supersedes_a_job_environment(self) -> None:
        # Attached Environments come first in the Job's Environment order, so
        # the attached Conda supersedes the Job Template's Docker.
        docker = _env(
            "Docker",
            exclusiveGroup="Soft",
            envParameterDefinitions=[{"name": "Image", "type": "STRING"}],
        )
        # Docker applies to S whatever its group, so S must supply its Image
        # (constraint 7), and template validation says so.
        with pytest.raises(ModelValidationError) as exc:
            _job_template([docker], [{"name": "S", "script": _ECHO}])
        assert str(exc.value) == "1 validation error for JobTemplate\nsteps[0]:\n" + _missing(
            "Image", "Docker"
        )

        entry = {"environment": "Docker", "parameters": {"Image": "ubuntu"}}
        jt = _job_template([docker], [{"name": "S", "dependencies": [entry], "script": _ECHO}])
        conda = _env_template("Conda", exclusiveGroup="Soft")
        created = create_job_with_environment_templates(
            job_template=jt, job_parameter_values={}, environment_templates=[(conda, "queue")]
        )
        queue = Document.environment_template(0, "queue")
        step = created.job.steps[0]
        assert step.environments == _refs("Conda", document=queue)
        assert step.enters_environment("Conda", queue)
        assert not step.enters_environment("Docker")
        assert step.environment_parameters_for("Docker") is None
        assert created.disabled_environments[0].environments == _refs("Docker")
        # Without the attachment, Docker is entered with the Step's Image.
        created = create_job_with_environment_templates(job_template=jt, job_parameter_values={})
        step = created.job.steps[0]
        # None: the Step enters every Job Environment.
        assert step.environments is None
        assert step.enters_environment("Docker")
        assert created.disabled_environments[0].environments == []
        docker_values = step.environment_parameters_for("Docker")
        assert docker_values is not None
        assert docker_values.values.to_json_str() == (
            '[{"name":"Image","type":"string","value":"ubuntu"}]'
        )

    def test_conformance_copy_superseded_held_to_constraint_7(self) -> None:
        # Docker, attached second, would be superseded by Conda, but it applies
        # to the Step, so its Image, which has no default, must be supplied.
        with pytest.raises(ModelValidationError) as exc:
            _create_copy("4--exclusive-group-superseded-held-to-constraint-7.invalid.test.yaml")
        assert str(exc.value) == (
            "1 validation error for Submission\n"
            "JobTemplate -> steps[0]:\n"
            "\tmust supply, in an 'environment:' dependency, every parameter without a default "
            "of each Environment that applies to it (every attached Environment with activation "
            "ALWAYS, each one with activation BY_DEFAULT that the Step does not decline, and each "
            "one with activation ON_REQUEST that the Step requests; Template Schemas §3.2.1), "
            "whatever that Environment's own enableIf is; missing: 'Image' of Environment "
            "'Docker' (EnvironmentTemplate[1])."
        )

    def test_conformance_copy_superseded_enable_if_not_evaluated(self) -> None:
        # The Step requests the superseded ON_REQUEST Docker with a Seats that
        # does not convert to INT; its enableIf is not evaluated and its values
        # are not checked.
        created = _create_copy("4--exclusive-group-superseded-enable-if-not-evaluated.test.yaml")
        conda = Document.environment_template(0)
        docker = Document.environment_template(1)
        step = created.job.steps[0]
        assert step.environments == _refs("Conda", document=conda)
        assert created.disabled_environments[0].environments == _refs("Docker", document=docker)
        assert step.environment_parameters_for("Docker", docker) is None

    def test_conformance_copy_job_environments(self) -> None:
        created = _create_copy("4--exclusive-group-job-environments.test.yaml")
        assert created.job.steps[0].environments == _refs("A")
        assert created.disabled_environments[0].environments == _refs("B")


# A Job whose Step S names a missing Environment (§7.4.1 step 3) and whose
# Step T requests Lic with a Seats that does not convert to INT (step 7), an
# error template validation cannot see.
def _two_error_template() -> Any:
    return _job_template(
        [
            _env(
                "Lic",
                activation="ON_REQUEST",
                envParameterDefinitions=[{"name": "Seats", "type": "INT"}],
            )
        ],
        [
            {"name": "S", "dependencies": [{"environment": "Missing"}], "script": _ECHO},
            {
                "name": "T",
                "dependencies": [{"environment": "Lic", "parameters": {"Seats": "{{Param.N}}"}}],
                "script": _ECHO,
            },
        ],
        params=[{"name": "N", "type": "STRING", "default": "many"}],
    )


_LIC_SEATS_INVALID = (
    "\tcould not be resolved as a value of type INT: Cannot convert 'many' to int: invalid "
    "digit found in string\n"
    "  Param.N\n"
    "  ~~~~~~^"
)


class TestErrorShape:
    def test_nothing_attached_is_for_job_template(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            create_job(job_template=_two_error_template(), job_parameter_values={})
        assert str(exc.value) == (
            "2 validation errors for JobTemplate\n"
            "steps[0] -> dependencies[0] -> environment:\n"
            "\tnames Environment 'Missing', which is not a jobEnvironments entry of the Job "
            "Template, and no Environment Template is attached. The entry is required; set "
            "'required: false' if the Step can run without the Environment (Template Schemas "
            "§3.2.1 item 2).\n"
            "steps[1] -> dependencies[0] -> parameters -> Seats:\n" + _LIC_SEATS_INVALID
        )

    def test_an_enable_if_does_not_defer_constraint_7(self) -> None:
        # Lic applies to T, which requests it without its Seats. Constraint 7
        # does not depend on Lic's own enableIf, so template validation reports
        # it even though the enableIf is not known there.
        with pytest.raises(ModelValidationError) as exc:
            _job_template(
                [
                    _env(
                        "Lic",
                        activation="ON_REQUEST",
                        enableIf="Param.UseLic",
                        envParameterDefinitions=[{"name": "Seats", "type": "INT"}],
                    )
                ],
                [{"name": "T", "dependencies": [{"environment": "Lic"}], "script": _ECHO}],
                params=[{"name": "UseLic", "type": "BOOL", "default": True}],
            )
        assert str(exc.value) == "1 validation error for JobTemplate\nsteps[0]:\n" + _missing(
            "Seats", "Lic"
        )

    @pytest.mark.parametrize("label", [None, "queue"])
    def test_attached_is_for_submission(self, label: Optional[str]) -> None:
        other = _env_template("Other")
        item: Any = other if label is None else (other, label)
        name = label or "EnvironmentTemplate[0]"
        with pytest.raises(ModelValidationError) as exc:
            create_job_with_environment_templates(
                job_template=_two_error_template(),
                job_parameter_values={},
                environment_templates=[item],
            )
        assert str(exc.value) == (
            "2 validation errors for Submission\n"
            "JobTemplate -> steps[0] -> dependencies[0] -> environment:\n"
            "\tnames Environment 'Missing', which is not a jobEnvironments entry of the Job "
            f"Template, and none of the attached Environment Templates ({name}) defines it. The "
            "entry is required; set 'required: false' if the Step can run without the "
            "Environment (Template Schemas §3.2.1 item 2).\n"
            "JobTemplate -> steps[1] -> dependencies[0] -> parameters -> Seats:\n"
            + _LIC_SEATS_INVALID
        )

    def test_without_env_params(self) -> None:
        # The shape rule applies to every Job Template: with an Environment
        # Template attached, a Job Template error is reported for Submission.
        jt = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1"],
                "name": "J",
                "parameterDefinitions": [{"name": "T", "type": "INT", "default": 0}],
                "steps": [
                    {
                        "name": "S",
                        "script": {
                            "actions": {"onRun": {"command": "echo", "timeout": "{{Param.T}}"}}
                        },
                    }
                ],
            },
            supported_extensions=["FEATURE_BUNDLE_1"],
        )
        env = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "environment": {"name": "Q", "variables": {"V": "x"}},
            }
        )
        with pytest.raises(ModelValidationError) as alone:
            create_job(job_template=jt, job_parameter_values={})
        assert str(alone.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> script -> actions -> onRun -> timeout:\n"
            "\ttimeout must be > 0."
        )
        with pytest.raises(ModelValidationError) as attached:
            create_job_with_environment_templates(
                job_template=jt, job_parameter_values={}, environment_templates=[env]
            )
        assert str(attached.value) == (
            "1 validation error for Submission\n"
            "JobTemplate -> steps[0] -> script -> actions -> onRun -> timeout:\n"
            "\ttimeout must be > 0."
        )


class TestAttributeValues:
    def test_decoded_expression_form(self) -> None:
        jt = _job_template(
            [],
            [
                {
                    "name": "S",
                    "hostRequirements": {
                        "attributes": [
                            {"name": "attr.custom.arch", "anyOf": "{{Param.Archs}}"},
                            {"name": "attr.custom.os", "allOf": ["linux"]},
                        ]
                    },
                    "script": _ECHO,
                }
            ],
            params=[{"name": "Archs", "type": "LIST[STRING]", "default": ["x86_64", "arm64"]}],
        )
        hr = jt.steps[0].host_requirements
        assert hr is not None and hr.attributes is not None
        arch, os_ = hr.attributes
        assert isinstance(arch.any_of, FormatString)
        assert arch.any_of.raw() == "{{Param.Archs}}"
        assert arch.all_of is None
        assert isinstance(os_.all_of, list)
        assert [v.raw() for v in os_.all_of] == ["linux"]
        assert os_.any_of is None
        # The job-side requirement holds the resolved list.
        job = create_job(job_template=jt, job_parameter_values={})
        job_hr = job.steps[0].host_requirements
        assert job_hr is not None and job_hr.attributes is not None
        attrs = job_hr.attributes
        assert [(a.name, a.any_of, a.all_of) for a in attrs] == [
            ("attr.custom.arch", ["x86_64", "arm64"], None),
            ("attr.custom.os", None, ["linux"]),
        ]

    def test_constructor_forms(self) -> None:
        listed = TemplateAttributeRequirement(
            name=FormatString("attr.custom.x"), any_of=[FormatString("a"), FormatString("b")]
        )
        assert isinstance(listed.any_of, list)
        assert [v.raw() for v in listed.any_of] == ["a", "b"]
        assert listed.all_of is None
        expr = TemplateAttributeRequirement(
            name=FormatString("attr.custom.x"), all_of=FormatString("{{Env.Param.X}}")
        )
        assert isinstance(expr.all_of, FormatString)
        assert expr.all_of.raw() == "{{Env.Param.X}}"
        assert isinstance(expr.allOf, FormatString)
        assert expr.allOf.raw() == "{{Env.Param.X}}"
        assert expr.any_of is None and expr.anyOf is None
        copy = pickle.loads(pickle.dumps(expr))
        assert isinstance(copy.all_of, FormatString)
        assert copy.all_of.raw() == "{{Env.Param.X}}"
        copy = pickle.loads(pickle.dumps(listed))
        assert isinstance(copy.anyOf, list)
        assert [v.raw() for v in copy.anyOf] == ["a", "b"]
        any_expr = TemplateAttributeRequirement(
            name=FormatString("attr.custom.x"), any_of=FormatString("{{Param.Archs}}")
        )
        copy = pickle.loads(pickle.dumps(any_expr))
        assert isinstance(copy.any_of, FormatString)
        assert copy.any_of.raw() == "{{Param.Archs}}"
        assert copy.all_of is None

    @pytest.mark.parametrize(
        "value, got",
        [
            ("a", "str"),
            (3, "int"),
            ([FormatString("a"), "b"], "list containing str"),
            ([1, "b"], "list containing int"),
        ],
    )
    @pytest.mark.parametrize("field", ["any_of", "all_of"])
    def test_constructor_rejects_other_types(self, field: str, value: Any, got: str) -> None:
        with pytest.raises(TypeError) as exc:
            TemplateAttributeRequirement(name=FormatString("attr.custom.x"), **{field: value})
        assert str(exc.value) == (
            "any_of and all_of must each be a list of FormatString, or one FormatString for the "
            f"<ListExpressionString> form, got {got}"
        )

    def test_empty_list(self) -> None:
        req = TemplateAttributeRequirement(name=FormatString("attr.custom.x"), any_of=[])
        assert req.any_of == []
        assert pickle.loads(pickle.dumps(req)).any_of == []

    def test_constructor_accepts_any_sequence(self) -> None:
        req = TemplateAttributeRequirement(
            name=FormatString("attr.custom.x"), any_of=(FormatString("a"), FormatString("b"))
        )
        assert isinstance(req.any_of, list)
        assert [v.raw() for v in req.any_of] == ["a", "b"]

    @pytest.mark.parametrize(
        "form, count",
        [
            # The list form stops resolving at the 51st value (openjd-rs #486),
            # so it does not give the count; the expression form does.
            (["{{Param.Many}}"], "more than 50"),
            ("{{Param.Many}}", "60"),
        ],
    )
    def test_more_than_50_values_after_resolution(self, form: Any, count: str) -> None:
        jt = _job_template(
            [],
            [
                {
                    "name": "S",
                    "hostRequirements": {"attributes": [{"name": "attr.custom.a", "anyOf": form}]},
                    "script": _ECHO,
                }
            ],
            params=[
                {
                    "name": "Many",
                    "type": "LIST[STRING]",
                    "default": [f"v{i}" for i in range(60)],
                }
            ],
        )
        with pytest.raises(DecodeValidationError) as exc:
            create_job(job_template=jt, job_parameter_values={})
        assert str(exc.value) == (
            "steps[0] -> hostRequirements -> attributes[0] -> anyOf: attribute 'attr.custom.a' "
            f"of Step 'S' has {count} anyOf values after resolution, exceeding the maximum of 50 "
            "(Template Schemas §3.3.2)"
        )


class TestRangeExprLengthCheck:
    """openjd-rs c0333380 (spec §2.10): a RANGE_EXPR Job Parameter's
    ``minLength`` / ``maxLength`` apply to its canonical form only in a document
    that lists ENV_PARAMS; the value as written is checked in every document."""

    @staticmethod
    def _template(extensions: list[str]) -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": extensions,
            "name": "J",
            "parameterDefinitions": [
                # "1,2,3,5" is 7 characters; its canonical form "1-3,5" is 5.
                {"name": "R", "type": "RANGE_EXPR", "minLength": 7, "default": "1,2,3,5"}
            ],
            "steps": [{"name": "S", "script": _ECHO}],
        }

    def test_without_env_params_only_as_written(self) -> None:
        jt = decode_job_template(template=self._template(["EXPR"]), supported_extensions=_EXTS)
        assert jt.name == "J"

    def test_with_env_params_also_canonical(self) -> None:
        with pytest.raises(ModelValidationError) as exc:
            decode_job_template(template=self._template(_EXTS), supported_extensions=_EXTS)
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "parameterDefinitions[0]:\n"
            "\tParameter 'R': canonical form '1-3,5' length 5 is less than minimum 7 (default)"
        )
