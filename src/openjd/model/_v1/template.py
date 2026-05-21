# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Template-time model types.

Mirrors ``openjd_model::template`` in the underlying Rust crate.
These are the types you get back from ``decode_job_template`` and
``decode_environment_template`` — the raw, parsed template before
job creation has resolved parameters and let-bindings.

For job-time (resolved, post-``create_job``) types, see
``openjd.model._v1.job``.
"""

from openjd._openjd_rs import (
    JobTemplate,
    EnvironmentTemplate,
)

__all__ = (
    "JobTemplate",
    "EnvironmentTemplate",
)
