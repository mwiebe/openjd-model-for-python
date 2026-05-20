# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Regression tests demonstrating known parity gaps between the openjd.model._v1
Rust-backed bindings and the pure-Python reference implementation.

Each test should *fail* against the current bindings — they document the
gaps. Mark them xfail so CI is honest about the gap until the underlying
bug is fixed.

Cross-reference:
- /home/markw/openjd-model-for-python/reports/model-bindings-quality-evaluation-report.md
"""

import pickle

import pytest

from openjd.model._v1 import (
    create_job,
    decode_job_template,
    model_to_object,
)


@pytest.mark.xfail(strict=True, reason="Issue: model_to_object NotImplementedError for JobTemplate")
def test_model_to_object_round_trip():
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "X",
        "steps": [
            {
                "name": "S",
                "script": {"actions": {"onRun": {"command": "echo"}}},
            }
        ],
    }
    t = decode_job_template(template=template)
    out = model_to_object(model=t)
    assert out == template


@pytest.mark.xfail(strict=True, reason="Issue: JobTemplate is not pickleable")
def test_job_template_pickleable():
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "X",
            "steps": [
                {"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}
            ],
        }
    )
    data = pickle.dumps(t)
    rt = pickle.loads(data)
    assert rt.name == t.name


def test_task_parameter_type_hashable():
    """Resolved by adding ``frozen, hash`` to the ``#[pyclass]`` attribute
    on ``PyTaskParameterType``. (Pickle support for the enum landed in
    the same change set; both follow from giving the enum a stable
    discriminant identity.)"""
    from openjd.model._v1 import TaskParameterType

    s = {TaskParameterType.INT, TaskParameterType.STRING}
    assert TaskParameterType.INT in s


@pytest.mark.xfail(
    strict=True, reason="Issue: taskParameterDefinitions returns serde JSON shape, not typed object"
)
def test_task_parameter_definitions_typed_objects():
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "X",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "F", "type": "INT", "range": "1-3"}
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        }
    )
    j = create_job(job_template=t, job_parameter_values={})
    ps = j.steps[0].parameterSpace
    F = ps.taskParameterDefinitions["F"]
    # Reference: F.type is TaskParameterType.INT, F.range is the IntRangeExpr.
    # Binding: F is a dict like {'int': {'range': {'rangeExpr': {...}}, 'chunks': None}}
    assert hasattr(F, "type")
    assert hasattr(F, "range")


@pytest.mark.xfail(strict=True, reason="Issue: decode_template not exported (reference exports it)")
def test_decode_template_re_export():
    from openjd.model._v1 import decode_template  # noqa: F401


@pytest.mark.xfail(
    strict=True,
    reason="Issue: JobTemplate.specificationVersion (camelCase) not exposed; only specification_version",
)
def test_job_template_specification_version_camelcase():
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "X",
            "steps": [
                {"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}
            ],
        }
    )
    assert t.specificationVersion is not None  # AttributeError today
