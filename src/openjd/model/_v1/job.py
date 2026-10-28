# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Job-time model types.

Mirrors ``openjd_model::job`` in the underlying Rust crate. These
are the resolved-and-instantiated types produced by ``create_job``:
parameters bound to concrete values, format strings still raw, the
parameter space resolved into a typed ``StepParameterSpace`` mapping.

For template-time (raw, pre-``create_job``) types, see
``openjd.model._v1.template``.
"""

from openjd._openjd_rs import (
    # Top-level job + structural
    Job,
    Step,
    StepScript,
    StepActions,
    Action,
    Environment,
    EnvironmentScript,
    EnvironmentActions,
    EmbeddedFile,
    JobParameter,
    HostRequirements,
    AmountRequirement,
    AttributeRequirement,
    StepParameterSpace,
    StepDependency,
    CancelationMode,
    # Iteration / graph helpers
    StepParameterSpaceIterator,
    StepDependencyGraph,
    StepDependencyNode,
    StepDependencyEdge,
    # Task-parameter pyclasses (one per ``TaskParameter`` runtime
    # variant in the underlying Rust crate). Returned by
    # ``StepParameterSpace.taskParameterDefinitions[name]``.
    TaskChunksDefinition,
    IntTaskParameter,
    FloatTaskParameter,
    StringTaskParameter,
    PathTaskParameter,
    ChunkIntTaskParameter,
    # ENV_PARAMS (RFC 0010, draft; Rust path only)
    CreatedJob,
    Document,
    EnvironmentParameterValues,
    EnvironmentRef,
    StepDisabledEnvironments,
)

__all__ = (
    "Action",
    "AmountRequirement",
    "AttributeRequirement",
    "CancelationMode",
    "ChunkIntTaskParameter",
    "CreatedJob",
    "Document",
    "EmbeddedFile",
    "Environment",
    "EnvironmentActions",
    "EnvironmentParameterValues",
    "EnvironmentRef",
    "EnvironmentScript",
    "FloatTaskParameter",
    "HostRequirements",
    "IntTaskParameter",
    "Job",
    "JobParameter",
    "PathTaskParameter",
    "Step",
    "StepActions",
    "StepDependency",
    "StepDependencyEdge",
    "StepDependencyGraph",
    "StepDependencyNode",
    "StepDisabledEnvironments",
    "StepParameterSpace",
    "StepParameterSpaceIterator",
    "StepScript",
    "StringTaskParameter",
    "TaskChunksDefinition",
)
