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
    Document,
    EnvironmentParameterValues,
    EnvironmentRef,
)
from openjd.model._v1.types import ModelExtension, ModelProfile, ValidationContext

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
        with pytest.raises(ModelValidationError) as exc:
            create_job(job_template=_job_template(template), job_parameter_values={})
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0]:\n"
            "\tmust supply, in an 'environment:' dependency, every parameter without a default "
            "of each Environment its Sessions enter (every jobEnvironments entry with activation "
            "ALWAYS, and each one with activation ON_REQUEST that the Step requests; Template "
            "Schemas §3.2 constraint 7); missing: 'Flavor' of Environment 'Tool'."
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
        message = str(exc.value)
        assert message.startswith(
            "1 validation error for Submission\n"
            "JobTemplate -> steps[0] -> dependencies[0] -> environment:\n"
            "\tnames Environment 'Conda', which is not a jobEnvironments entry of the Job "
            "Template, and no Environment Template"
        ), message

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
        assert "names Environment 'Conda'" in str(exc.value)


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

    def test_environment_ref(self) -> None:
        ref = EnvironmentRef(document=Document.job_template(), environment="Tool")
        assert ref.environment == "Tool" and ref.document == Document.job_template()
        assert ref == EnvironmentRef(document=Document.job_template(), environment="Tool")
        assert hash(ref) == hash(
            EnvironmentRef(document=Document.job_template(), environment="Tool")
        )
        assert repr(ref) == 'EnvironmentRef(document=Document.job_template(), environment="Tool")'

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
        assert str(exc.value).startswith("Failed to parse EnvironmentParameterValues JSON: ")


class TestValidationContext:
    def test_submission_path_policy(self) -> None:
        ctx = ValidationContext(ModelProfile(extensions=[ModelExtension.ENV_PARAMS]))
        assert ctx.allow_uri_path_values is False
        assert ctx.submission_path_format in (PathFormat.POSIX, PathFormat.WINDOWS)
        windows = ctx.with_submission_path_format(PathFormat.WINDOWS).with_allow_uri_path_values(
            True
        )
        assert windows.submission_path_format == PathFormat.WINDOWS
        assert windows.allow_uri_path_values is True
        assert windows != ctx
        assert pickle.loads(pickle.dumps(windows)) == windows
        assert (
            ValidationContext(
                ctx.profile, submission_path_format=PathFormat.WINDOWS, allow_uri_path_values=True
            )
            == windows
        )

    def _uri_template(self) -> Any:
        return _job_template(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": _EXTS,
                "name": "Uri",
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
                        "name": "A",
                        "dependencies": [
                            {"environment": "Mnt", "parameters": {"Dir": "s3://bucket/key"}}
                        ],
                        "script": _echo("A"),
                    }
                ],
            }
        )

    def test_uri_path_values_follow_the_context(self) -> None:
        jt = self._uri_template()
        with pytest.raises(ModelValidationError) as exc:
            create_job(job_template=jt, job_parameter_values={})
        assert str(exc.value) == (
            "1 validation error for JobTemplate\n"
            "steps[0] -> dependencies[0] -> parameters -> Dir:\n"
            "\tis a URI ('s3://bucket/key'), and URI path values are not permitted for this "
            "submission."
        )
        ctx = ValidationContext(jt.profile, allow_uri_path_values=True)
        step = create_job(job_template=jt, job_parameter_values={}, validation_context=ctx).steps[0]
        mnt = step.environment_parameters_for("Mnt")
        assert mnt is not None
        assert _values(mnt) == [{"name": "Dir", "type": "path", "value": "s3://bucket/key"}]


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
        assert "names Environment 'Conda'" in str(exc.value)


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
