# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Open Job Description Model — backed by Rust bindings."""

import json
from enum import Enum
from typing import Any, Optional


# ── Re-exports from Rust native module ──

from openjd._openjd_rs import (
    # Decode functions
    decode_job_template_str,
    decode_job_template_dict,
    decode_environment_template_str,
    decode_environment_template_dict,
    # Job creation
    create_job,
    preprocess_job_parameters,
    merge_job_parameter_definitions,
    # Output types
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
    StepParameterSpace,
    StepDependency,
    CancelationMode,
    # Iteration
    StepParameterSpaceIterator,
    StepDependencyGraph,
    StepDependencyNode as _RustStepDependencyNode,
    StepDependencyEdge as _RustStepDependencyEdge,
    # Template types
    JobTemplate,
    EnvironmentTemplate,
    # Enums
    DocumentType,
    JobParameterType,
    TaskParameterType,
    TaskParameterValue,
    JobParameterValue,
    # Errors
    DecodeValidationError,
    ModelValidationError,
    UnsupportedSchema,
    # Expr types used by model consumers
    SymbolTable,
    FormatString,
    ExpressionError,
    FormatStringValidationError as FormatStringError,
    RangeExpr,
)
from openjd._openjd_rs import TemplateSpecificationVersion as _RustTSV


# Note: the `__module__` / `__name__` / `__qualname__` of the Rust-backed
# exceptions (DecodeValidationError, ModelValidationError, UnsupportedSchema,
# and the openjd.expr exceptions re-imported above) are set by the
# `_openjd_rs` module init in Rust to their canonical user-facing values
# (e.g. `openjd.model.v1.DecodeValidationError`). No Python-side fix-up
# needed.


# ── Python-only types ──

# Backward compatibility alias
ParameterValueType = JobParameterType


class ParameterValue:
    """A parameter value with its type. Accepts either JobParameterType or TaskParameterType."""
    def __init__(self, *, type, value: str):
        self.type = type
        self.value = value

    def __eq__(self, other):
        if not hasattr(other, 'type') or not hasattr(other, 'value'):
            return NotImplemented
        return self.type.as_str() == other.type.as_str() and self.value == other.value

    def __hash__(self):
        return hash((self.type.as_str(), self.value))

    def __repr__(self):
        return f"ParameterValue(type={self.type.as_str()}, value={self.value!r})"



class TemplateSpecificationVersion(str, Enum):
    JOBTEMPLATE_v2023_09 = "jobtemplate-2023-09"
    ENVIRONMENT_v2023_09 = "environment-2023-09"

    @staticmethod
    def is_job_template(v: "TemplateSpecificationVersion") -> bool:
        return v == TemplateSpecificationVersion.JOBTEMPLATE_v2023_09

    @staticmethod
    def is_environment_template(v: "TemplateSpecificationVersion") -> bool:
        return v == TemplateSpecificationVersion.ENVIRONMENT_v2023_09

    @staticmethod
    def job_template_versions() -> list["TemplateSpecificationVersion"]:
        return [TemplateSpecificationVersion.JOBTEMPLATE_v2023_09]

    @staticmethod
    def environment_template_versions() -> list["TemplateSpecificationVersion"]:
        return [TemplateSpecificationVersion.ENVIRONMENT_v2023_09]


class SpecificationRevision(str, Enum):
    v2023_09 = "2023-09"


class RevisionExtensions:
    """Tracks which extensions are active for a specification revision."""
    def __init__(self, spec_rev: SpecificationRevision = None, revision: SpecificationRevision = None, 
                 supported_extensions: Optional[list] = None, extensions: Optional[set] = None):
        self.revision = spec_rev or revision or SpecificationRevision.v2023_09
        self.extensions = set(supported_extensions or []) if supported_extensions is not None else (extensions or set())




# Type aliases
JobParameterValues = dict  # dict[str, ParameterValue] or dict[str, dict]
JobParameterInputValues = dict  # dict[str, str]
TaskParameterSet = dict  # dict[str, Any]
JobParameterDefinition = Any  # opaque from Rust
OpenJDModel = Any  # base class no longer needed


# ── Compatibility aliases ──

IntRangeExpr = RangeExpr


# ── Types needed by sessions ──

# CommandString and ArgString are FormatString constructors
CommandString = FormatString
ArgString = FormatString


class ValueReferenceConstants(str, Enum):
    """String constants for symbol table key prefixes."""
    JOB_PARAMETER_PREFIX = "Param"
    JOB_PARAMETER_RAWPREFIX = "RawParam"
    TASK_PARAMETER_PREFIX = "Task.Param"
    TASK_PARAMETER_RAWPREFIX = "Task.RawParam"
    ENV_FILE_PREFIX = "Env.File"
    TASK_FILE_PREFIX = "Task.File"
    WORKING_DIRECTORY = "Session.WorkingDirectory"
    HAS_PATH_MAPPING_RULES = "Session.HasPathMappingRules"
    PATH_MAPPING_RULES_FILE = "Session.PathMappingRulesFile"


class CancelationMethodTerminate:
    """A cancelation method that terminates the process."""
    def __init__(self, mode=None):
        self.mode = mode or "TERMINATE"


class CancelationMethodNotifyThenTerminate:
    """A cancelation method that notifies then terminates."""
    def __init__(self, mode=None, notify_period_in_seconds: int = 120):
        self.mode = mode or "NOTIFY_THEN_TERMINATE"
        self.notify_period_in_seconds = notify_period_in_seconds


# EmbeddedFileText is the same as EmbeddedFile in the Rust model
EmbeddedFileText = EmbeddedFile

# EmbeddedFiles is a list type alias — sessions defines its own wrapper
EmbeddedFiles = list


class CompatibilityError(Exception):
    """Raised when template versions are incompatible."""
    pass


class TokenError(Exception):
    """Raised for tokenization errors (legacy)."""
    def __init__(self, source: str, token: str, position: int):
        self.source = source
        self.token = token
        self.position = position
        super().__init__(f"Unexpected '{token}' in '{source}' after '{source[:position]}'")


# ── Python functions ──

# Environment variable can optionally disable CSafeLoader
try:
    from yaml import CSafeLoader as _YamlLoader
except ImportError:
    from yaml import SafeLoader as _YamlLoader  # type: ignore[assignment]




def document_string_to_object(*, document: str, document_type: "DocumentType" = None) -> dict[str, Any]:
    """Parse a YAML or JSON document string into a Python dict."""
    import json as _json
    import yaml as _yaml
    try:
        if document_type == DocumentType.JSON:
            result = _json.loads(document)
        else:
            result = _yaml.load(document, Loader=_YamlLoader)
    except Exception as e:
        raise DecodeValidationError(str(e)) from e
    if not isinstance(result, dict):
        raise DecodeValidationError(
            f"Template must be a mapping/object, got {type(result).__name__}"
        )
    return result


def decode_job_template(
    *, template: dict[str, Any], supported_extensions: Optional[list[str]] = None
) -> JobTemplate:
    """Decode a job template from a dict."""
    return decode_job_template_dict(template, supported_extensions)


def decode_environment_template(
    *, template: dict[str, Any], supported_extensions: Optional[list[str]] = None
) -> EnvironmentTemplate:
    """Decode an environment template from a dict."""
    return decode_environment_template_dict(template, supported_extensions)


def parse_model(*, model: Any = None, obj: dict[str, Any]) -> Any:
    """Decode a template from a dict, auto-detecting the type.

    The `model` parameter is accepted for backward compatibility but ignored —
    the template type is determined from specificationVersion in the dict.
    """
    spec = obj.get("specificationVersion", "")
    if "environment" in spec:
        return decode_environment_template_dict(obj)
    return decode_job_template_dict(obj)




def model_to_object(*, model: Any) -> dict[str, Any]:
    """Serialize a model object to a dict. Limited support with Rust types."""
    if hasattr(model, "to_dict"):
        return model.to_dict()
    raise NotImplementedError("model_to_object is not supported for this type")




def validate_amount_capability_name(name: str) -> None:
    """Validate an amount capability name."""
    pass  # Validation happens in Rust during decode


def validate_attribute_capability_name(name: str) -> None:
    """Validate an attribute capability name."""
    pass  # Validation happens in Rust during decode


StepDependencyGraphNode = _RustStepDependencyNode
StepDependencyGraphStepToStepEdge = _RustStepDependencyEdge


from .._version import version  # noqa: E402


__all__ = (
    "create_job",
    "decode_environment_template",
    "decode_job_template",
    "document_string_to_object",
    "merge_job_parameter_definitions",
    "model_to_object",
    "parse_model",
    "preprocess_job_parameters",
    "validate_amount_capability_name",
    "validate_attribute_capability_name",
    "CompatibilityError",
    "DecodeValidationError",
    "DocumentType",
    "EnvironmentTemplate",
    "ExpressionError",
    "FormatStringError",
    "IntRangeExpr",
    "Job",
    "JobParameterDefinition",
    "JobParameterInputValues",
    "JobParameterValues",
    "JobTemplate",
    "ModelValidationError",
    "OpenJDModel",
    "ParameterValue",
    "JobParameterType",
    "ParameterValueType",
    "TaskParameterType",
    "RevisionExtensions",
    "SpecificationRevision",
    "Step",
    "StepDependencyGraph",
    "StepDependencyGraphNode",
    "StepDependencyGraphStepToStepEdge",
    "StepParameterSpace",
    "StepParameterSpaceIterator",
    "SymbolTable",
    "TaskParameterSet",
    "TemplateSpecificationVersion",
    "TokenError",
    "UnsupportedSchema",
    "ArgString",
    "CommandString",
    "ValueReferenceConstants",
    "CancelationMethodTerminate",
    "CancelationMethodNotifyThenTerminate",
    "EmbeddedFileText",
    "EmbeddedFiles",
    "version",
    "STANDARD_AMOUNT_CAPABILITIES",
    "STANDARD_ATTRIBUTE_CAPABILITIES",
    "validate_amount_capability_name",
    "validate_attribute_capability_name",
)


# ── Standard capabilities (source of truth: openjd-model Rust crate) ──

STANDARD_AMOUNT_CAPABILITIES: dict[str, dict] = {
    "amount.worker.vcpu": {},
    "amount.worker.memory": {},
    "amount.worker.gpu": {},
    "amount.worker.gpu.memory": {},
    "amount.worker.disk.scratch": {},
}

STANDARD_ATTRIBUTE_CAPABILITIES: dict[str, dict] = {
    "attr.worker.os.family": {"values": {"linux", "windows", "macos"}, "multivalued": False},
    "attr.worker.cpu.arch": {"values": {"x86_64", "arm64"}, "multivalued": False},
}


def validate_amount_capability_name(name: str = "", *, capability_name: str = "", standard_capabilities=None) -> str:
    """Validate that a string is a valid amount capability name. Returns the name or raises ValueError."""
    import re
    n = capability_name or name
    if not re.match(r"(?i)\A([A-Za-z_][A-Za-z0-9_]*:)?amount\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*\Z", n):
        raise ValueError(f"'{n}' is not a valid amount capability name")
    _validate_capability_scoping(n, "amount", standard_capabilities)
    return n


def validate_attribute_capability_name(name: str = "", *, capability_name: str = "", standard_capabilities=None) -> str:
    """Validate that a string is a valid attribute capability name. Returns the name or raises ValueError."""
    import re
    n = capability_name or name
    if not re.match(r"(?i)\A([A-Za-z_][A-Za-z0-9_]*:)?attr\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*\Z", n):
        raise ValueError(f"'{n}' is not a valid attribute capability name")
    _validate_capability_scoping(n, "attr", standard_capabilities)
    return n


_RESERVED_SCOPES = {"worker", "job", "step", "task"}


def _validate_capability_scoping(name: str, prefix: str, standard_capabilities=None) -> None:
    """Check that capability names respect reserved scope rules.

    Rules:
    - If the name uses a reserved scope (e.g. amount.worker.*), it must appear in the
      standard_capabilities list and must NOT have a vendor prefix.
    - Vendor-prefixed names must NOT use reserved scopes.
    """
    import re
    # Separate optional vendor prefix from the rest
    vendor_match = re.match(r"(?i)\A([A-Za-z_][A-Za-z0-9_]*):(.+)\Z", name)
    if vendor_match:
        bare_name = vendor_match.group(2)
    else:
        bare_name = name

    # Check if the name uses a reserved scope (prefix.scope.*)
    parts = bare_name.split(".")
    # parts[0] is the prefix (amount/attr), parts[1] would be the scope if present
    if len(parts) >= 3:
        scope = parts[1].lower()
        if scope in _RESERVED_SCOPES:
            # Vendor-prefixed names cannot use reserved scopes
            if vendor_match:
                raise ValueError(
                    f"'{name}' is not valid: vendor-prefixed names cannot use reserved scope '{scope}'"
                )
            # Names in reserved scopes must be in the standard capabilities list
            if standard_capabilities is not None:
                if name.lower() not in [c.lower() for c in standard_capabilities]:
                    raise ValueError(
                        f"'{name}' is not a recognized standard capability in scope '{scope}'"
                    )

