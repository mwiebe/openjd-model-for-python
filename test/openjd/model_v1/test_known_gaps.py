# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Failing tests demonstrating known parity gaps between the
``openjd.model._v1`` Rust-backed bindings and the pure-Python reference
implementation.

Every test here is expected to *fail* against the current bindings and is
marked ``xfail``. As gaps are resolved the corresponding tests are moved
to the appropriate home in this directory (e.g. pickle tests to
``test_pickle.py``, parser shape tests to ``test_parse.py``); this file
is being driven to zero.

Cross-reference:
    reports/model-bindings-quality-evaluation-report.md
"""

import pytest

from openjd.model._v1 import (
    UnsupportedSchema,
    create_job,
    decode_job_template,
)


_template_with_int_param = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "T",
    "parameterDefinitions": [{"name": "C", "type": "INT", "default": 5}],
    "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
}


@pytest.mark.xfail(
    reason="Rec #1: JobParameter is missing v0's `.type` getter (alias for param_type)",
    strict=True,
)
def test_job_parameter_has_type_alias() -> None:
    # v0 exposes JobParameter.type returning the JobParameterType enum;
    # v1 currently only exposes .param_type. Existing v0 callers
    # (deadline-cloud, openjd-cli) read .type, so the binding should
    # expose a `type` getter as an alias.
    t = decode_job_template(template=_template_with_int_param)
    j = create_job(job_template=t, job_parameter_values={})
    p = j.parameters["C"]
    assert hasattr(p, "type"), "JobParameter should expose .type as alias for param_type"


@pytest.mark.xfail(
    reason="Rec #2: job-time Step is missing host_requirements/hostRequirements getter",
    strict=True,
)
def test_step_exposes_host_requirements() -> None:
    # The Rust ``job::Step`` struct has ``host_requirements:
    # Option<HostRequirements>`` but the binding's PyStep doesn't
    # expose a getter for it. v0's job-time Step has
    # ``hostRequirements`` and downstream consumers read it.
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [
            {
                "name": "S",
                "hostRequirements": {
                    "amounts": [{"name": "amount.worker.vcpu", "min": 4}],
                },
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    t = decode_job_template(template=template)
    j = create_job(job_template=t, job_parameter_values={})
    step = j.steps[0]
    assert hasattr(step, "host_requirements") or hasattr(
        step, "hostRequirements"
    ), "job-time Step should expose host_requirements (Rust struct has the field)"


@pytest.mark.xfail(
    reason="Rec #3: job-time EmbeddedFile is missing runnable getter",
    strict=True,
)
def test_embedded_file_exposes_runnable() -> None:
    # Rust ``job::EmbeddedFile`` has ``runnable: Option<bool>`` and
    # template-time PyEmbeddedFile exposes it; job-time PyEmbeddedFile
    # doesn't.
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "steps": [
            {
                "name": "S",
                "script": {
                    "actions": {"onRun": {"command": "./run.sh"}},
                    "embeddedFiles": [
                        {
                            "name": "run.sh",
                            "type": "TEXT",
                            "data": "#!/bin/sh\necho hi",
                            "runnable": True,
                        }
                    ],
                },
            }
        ],
    }
    t = decode_job_template(template=template)
    j = create_job(job_template=t, job_parameter_values={})
    embedded = j.steps[0].script.embeddedFiles
    assert embedded is not None
    ef = embedded[0]
    assert hasattr(ef, "runnable"), "job-time EmbeddedFile should expose runnable"


@pytest.mark.xfail(
    reason="Rec #4: job-time EmbeddedFile is missing endOfLine/end_of_line getter",
    strict=True,
)
def test_embedded_file_exposes_end_of_line() -> None:
    # Rust ``job::EmbeddedFile`` has ``end_of_line: Option<EndOfLine>``
    # and template-time PyEmbeddedFile exposes it under both snake_case
    # and camelCase; job-time PyEmbeddedFile doesn't expose either.
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "extensions": ["FEATURE_BUNDLE_1"],
        "steps": [
            {
                "name": "S",
                "script": {
                    "actions": {"onRun": {"command": "echo"}},
                    "embeddedFiles": [
                        {
                            "name": "f1",
                            "type": "TEXT",
                            "data": "x",
                            "endOfLine": "LF",
                        }
                    ],
                },
            }
        ],
    }
    t = decode_job_template(template=template, supported_extensions=["FEATURE_BUNDLE_1"])
    j = create_job(job_template=t, job_parameter_values={})
    embedded = j.steps[0].script.embeddedFiles
    assert embedded is not None
    ef = embedded[0]
    assert hasattr(ef, "end_of_line") or hasattr(
        ef, "endOfLine"
    ), "job-time EmbeddedFile should expose end_of_line"


@pytest.mark.xfail(
    reason="Rec #6: StepParameterSpaceIterator is missing v0's validate_containment method",
    strict=True,
)
def test_step_parameter_space_iterator_validate_containment() -> None:
    # v0 exposes ``StepParameterSpaceIterator.validate_containment(params)``,
    # which raises with a specific message naming the offending param if
    # ``params`` is not in the iterator's space. v1 dropped the method.
    from openjd.model._v1.job import StepParameterSpaceIterator

    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": [1, 2, 3]},
                        ],
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        }
    )
    j = create_job(job_template=t, job_parameter_values={})
    it = StepParameterSpaceIterator(space=j.steps[0].parameterSpace)
    assert hasattr(
        it, "validate_containment"
    ), "StepParameterSpaceIterator should expose validate_containment"


@pytest.mark.xfail(
    reason="Rec #7: StepDependencyGraph is missing v0's max_indegree/max_outdegree properties",
    strict=True,
)
def test_step_dependency_graph_max_degree_properties() -> None:
    # v0's StepDependencyGraph exposes ``max_indegree`` and
    # ``max_outdegree`` properties used by downstream tooling. v1
    # doesn't expose them.
    from openjd.model._v1.job import StepDependencyGraph

    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {"name": "A", "script": {"actions": {"onRun": {"command": "echo"}}}},
                {
                    "name": "B",
                    "dependencies": [{"dependsOn": "A"}],
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                },
            ],
        }
    )
    j = create_job(job_template=t, job_parameter_values={})
    g = StepDependencyGraph(job=j)
    assert hasattr(g, "max_indegree"), "StepDependencyGraph should expose max_indegree"
    assert hasattr(g, "max_outdegree"), "StepDependencyGraph should expose max_outdegree"


@pytest.mark.xfail(
    reason="Rec #8: UnsupportedSchema constructor signature differs from v0",
    strict=True,
)
def test_unsupported_schema_constructor_parity() -> None:
    # v0: ``UnsupportedSchema(version_str)`` produces ``str(e) ==
    # 'Unsupported schema version: {version_str}'`` and exposes
    # ``e._version``. v1: ``UnsupportedSchema(msg)`` produces
    # ``str(e) == msg`` and has no ``_version`` attribute.
    e = UnsupportedSchema("foo")
    assert (
        str(e) == "Unsupported schema version: foo"
    ), "UnsupportedSchema('foo') should produce v0's wrapped message"
    assert (
        getattr(e, "_version", None) == "foo"
    ), "UnsupportedSchema should expose ._version like v0"


@pytest.mark.xfail(
    reason="Rec #9: TokenError doesn't inherit ExpressionError as v0 does",
    strict=True,
)
def test_token_error_inherits_expression_error() -> None:
    # v0's MRO: TokenError -> ExpressionError -> ValueError -> Exception.
    # v1's MRO:  TokenError -> Exception. v0 callers that catch
    # ExpressionError to handle TokenError will silently miss it.
    from openjd.model._v1 import ExpressionError, TokenError

    assert issubclass(
        TokenError, ExpressionError
    ), "TokenError should inherit ExpressionError per v0 reference"


@pytest.mark.xfail(
    reason="Rec #10: Action.timeout returns str in v1 but int (or FormatString) in v0",
    strict=True,
)
def test_action_timeout_int_round_trip() -> None:
    # v0's Action.timeout returns an int (60); v1 returns the
    # FormatString.raw() form ("60"). Downstream callers that do
    # arithmetic on the timeout (e.g. clamping, summation) get a
    # TypeError under v1.
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {
                    "name": "S",
                    "script": {"actions": {"onRun": {"command": "echo", "timeout": 60}}},
                }
            ],
        }
    )
    j = create_job(job_template=t, job_parameter_values={})
    timeout = j.steps[0].script.actions.onRun.timeout
    assert isinstance(
        timeout, int
    ), "v1 Action.timeout should match v0's int-returning shape for integer timeouts"
    assert timeout == 60
