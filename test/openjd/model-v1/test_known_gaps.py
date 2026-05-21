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

import pickle

import pytest

from openjd.model._v1 import (
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


@pytest.mark.xfail(strict=True, reason="Issue: decode_template not exported (reference exports it)")
def test_decode_template_re_export():
    from openjd.model._v1 import decode_template  # noqa: F401
