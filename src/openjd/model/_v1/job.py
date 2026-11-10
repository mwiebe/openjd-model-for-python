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
    DiscardedHostRequirement,
    Document,
    EnvironmentParameterValues,
    EnvironmentRef,
    EnvironmentScope,
    EnvironmentStatus,
    HostRequirementKind,
    OptionalEntryNotFound,
    StepDisabledEnvironments,
    StepEnvironmentStatus,
    StepEnvironmentStatuses,
    SupersedingEnvironment,
)

__all__ = (
    "Action",
    "AmountRequirement",
    "AttributeRequirement",
    "CancelationMode",
    "ChunkIntTaskParameter",
    "CreatedJob",
    "DiscardedHostRequirement",
    "Document",
    "EmbeddedFile",
    "Environment",
    "EnvironmentActions",
    "EnvironmentParameterValues",
    "EnvironmentRef",
    "EnvironmentScope",
    "EnvironmentScript",
    "EnvironmentStatus",
    "FloatTaskParameter",
    "HostRequirementKind",
    "HostRequirements",
    "IntTaskParameter",
    "Job",
    "JobParameter",
    "OptionalEntryNotFound",
    "PathTaskParameter",
    "Step",
    "StepActions",
    "StepDependency",
    "StepDependencyEdge",
    "StepDependencyGraph",
    "StepDependencyNode",
    "StepDisabledEnvironments",
    "StepEnvironmentStatus",
    "StepEnvironmentStatuses",
    "StepParameterSpace",
    "StepParameterSpaceIterator",
    "StepScript",
    "StringTaskParameter",
    "SupersedingEnvironment",
    "TaskChunksDefinition",
)
