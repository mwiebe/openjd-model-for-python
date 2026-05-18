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
from pathlib import Path

import pytest

from openjd.model._v1 import (
    EmbeddedFile,
    IntRangeExpr,
    JobParameterType,
    ParameterValue,
    StepParameterSpaceIterator,
    TemplateSpecificationVersion,
    decode_job_template,
    create_job,
    model_to_object,
)


@pytest.mark.xfail(strict=True, reason="Issue: descending IntRangeExpr.from_str loses input order")
def test_int_range_expr_descending_iteration_order():
    # Reference: IntRangeExpr.from_str('-1 - -2 : -1') iterates as [-1, -2]
    # because IntRange normalises to positive step but stores _start = end of
    # the input range.
    r = IntRangeExpr.from_str("-1 - -2 : -1")
    assert list(r) == [-1, -2]


@pytest.mark.xfail(strict=True, reason="Issue: __contains__ rejects items it just yielded")
def test_step_param_space_iter_contains_self_yielded():
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "X",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": "1-3"}
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        }
    )
    j = create_job(job_template=t, job_parameter_values={})
    it = StepParameterSpaceIterator(step=j.steps[0])

    yielded = list(iter(it))
    it.reset_iter()
    for v in yielded:
        assert v in it


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


@pytest.mark.xfail(strict=True, reason="Issue: chunks_default_task_count setter is a no-op")
def test_step_param_space_iter_chunks_default_task_count_setter():
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "X",
            "extensions": ["TASK_CHUNKING"],
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {
                                "name": "F",
                                "type": "CHUNK[INT]",
                                "range": "1-100",
                                "chunks": {
                                    "defaultTaskCount": 10,
                                    "targetRuntimeSeconds": 120,
                                    "rangeConstraint": "CONTIGUOUS",
                                },
                            }
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        },
        supported_extensions=["TASK_CHUNKING"],
    )
    j = create_job(job_template=t, job_parameter_values={})
    it = StepParameterSpaceIterator(step=j.steps[0])
    assert it.chunks_default_task_count == 10
    it.chunks_default_task_count = 5
    assert it.chunks_default_task_count == 5  # silently stays at 10


@pytest.mark.xfail(
    strict=True, reason="Issue: __len__ returns 0 on adaptive chunked space (reference raises)"
)
def test_step_param_space_iter_adaptive_len_raises():
    t = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "name": "X",
            "extensions": ["TASK_CHUNKING"],
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {
                                "name": "F",
                                "type": "CHUNK[INT]",
                                "range": "1-100",
                                "chunks": {
                                    "defaultTaskCount": 10,
                                    "targetRuntimeSeconds": 120,
                                    "rangeConstraint": "CONTIGUOUS",
                                },
                            }
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        },
        supported_extensions=["TASK_CHUNKING"],
    )
    j = create_job(job_template=t, job_parameter_values={})
    it = StepParameterSpaceIterator(step=j.steps[0])
    with pytest.raises(ValueError):
        len(it)


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


@pytest.mark.xfail(strict=True, reason="Issue: TaskParameterType is not hashable but spec implies it should be (parallel to JobParameterType)")
def test_task_parameter_type_hashable():
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
