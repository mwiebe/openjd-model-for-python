# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Open Job Description Model — backed by Rust bindings."""

from enum import Enum
from typing import Any, Optional


# ── Re-exports from Rust native module ──

from openjd._openjd_rs import (
    # Decode functions (raw)
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
    # Profile types — the canonical inputs to decode_*_template and create_job.
    # Mirror openjd_model::types::{ModelProfile, ModelExtension,
    # SpecificationRevision, CallerLimits, ValidationContext}.
    ModelProfile,
    ModelExtension,
    SpecificationRevision as _RsSpecificationRevision,
    CallerLimits,
    ValidationContext,
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
# exceptions are set by the `_openjd_rs` module init in Rust to their
# canonical user-facing values (e.g. `openjd.model._v1.ModelValidationError`).
# No Python-side fix-up needed.


# ── SpecificationRevision (Python str-Enum for backward-compatibility) ──
#
# The Rust binding exposes its `SpecificationRevision` pyclass under the
# private name `_RsSpecificationRevision` above. Existing consumers
# (openjd-sessions, openjd-cli, deadline-cloud-worker-agent) reference
# `SpecificationRevision.v2023_09` (lowercase `v`) — a Python `str`-Enum
# member name. We keep that surface here as the primary import; new code
# can reach for the Rust pyclass via `_RsSpecificationRevision` if it
# wants the Rust naming.
#
# Conversion happens in `_to_rust_revision`/`_from_rust_revision` below.


class SpecificationRevision(str, Enum):
    """Specification revision identifier.

    Currently the only revision is `v2023_09` (= `"2023-09"`).
    """

    v2023_09 = "2023-09"

    def to_rust(self) -> "_RsSpecificationRevision":
        """Convert to the Rust pyclass enum used by the bindings."""
        return _to_rust_revision(self)


def _to_rust_revision(rev: "SpecificationRevision | str") -> _RsSpecificationRevision:
    if isinstance(rev, _RsSpecificationRevision):
        return rev
    s = rev.value if isinstance(rev, SpecificationRevision) else rev
    if s == "2023-09":
        return _RsSpecificationRevision.V2023_09
    raise ValueError(f"Unknown specification revision: {s}")


def _from_rust_revision(rev: _RsSpecificationRevision) -> SpecificationRevision:
    if rev == _RsSpecificationRevision.V2023_09:
        return SpecificationRevision.v2023_09
    raise ValueError(f"Unknown specification revision: {rev!r}")


# ── Python-only types ──

# Backward compatibility alias
ParameterValueType = JobParameterType


class ParameterValue:
    """A parameter value with its type. Accepts either JobParameterType or TaskParameterType."""

    def __init__(self, *, type, value: str):
        self.type = type
        self.value = value

    def __eq__(self, other):
        if not hasattr(other, "type") or not hasattr(other, "value"):
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


class RevisionExtensions:
    """Tracks which extensions are active for a specification revision.

    Thin compat wrapper around `ModelProfile` for callers that still pass
    `RevisionExtensions(spec_rev=..., supported_extensions=[...])`. New
    code should construct a `ModelProfile` directly.
    """

    def __init__(
        self,
        spec_rev: SpecificationRevision = None,
        revision: SpecificationRevision = None,
        supported_extensions: Optional[list] = None,
        extensions: Optional[set] = None,
    ):
        self.revision = spec_rev or revision or SpecificationRevision.v2023_09
        if supported_extensions is not None:
            self.extensions = set(supported_extensions)
        else:
            self.extensions = extensions or set()

    def to_profile(self) -> "ModelProfile":
        """Build the matching `ModelProfile`."""
        return ModelProfile.from_strings(
            _to_rust_revision(self.revision),
            sorted(str(e) for e in self.extensions),
        )


# Type aliases
JobParameterValues = dict  # dict[str, ParameterValue] or dict[str, dict]
JobParameterInputValues = dict  # dict[str, str]
TaskParameterSet = dict  # dict[str, Any]
JobParameterDefinition = Any  # opaque from Rust
OpenJDModel = Any  # base class no longer needed


# ── Compatibility aliases ──

IntRangeExpr = RangeExpr


# ── Types needed by sessions ──

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
    def __init__(self, mode=None):
        self.mode = mode or "TERMINATE"


class CancelationMethodNotifyThenTerminate:
    def __init__(self, mode=None, notify_period_in_seconds: int = 120):
        self.mode = mode or "NOTIFY_THEN_TERMINATE"
        self.notify_period_in_seconds = notify_period_in_seconds


EmbeddedFileText = EmbeddedFile
EmbeddedFiles = list


class CompatibilityError(Exception):
    pass


class TokenError(Exception):
    def __init__(self, source: str, token: str, position: int):
        self.source = source
        self.token = token
        self.position = position
        super().__init__(f"Unexpected '{token}' in '{source}' after '{source[:position]}'")


# ── Python functions ──

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
    *,
    template: dict[str, Any],
    supported_extensions: Optional[list[str]] = None,
    caller_limits: Optional[CallerLimits] = None,
) -> JobTemplate:
    """Decode and validate a job template from a Python dict.

    Args:
        template: The decoded template mapping.
        supported_extensions: The caller's allowlist of OpenJD extension
            names. The template's `extensions:` field is validated
            against this list — any name in the template that is not
            both a recognized `ModelExtension` AND in this list is
            rejected with `Unsupported extension names: ...`. Pass
            `None` (the default) for an empty allowlist (i.e., reject
            every extension the template requests).
        caller_limits: Optional `CallerLimits` to tighten spec-defined
            limits.

    Returns:
        The parsed `JobTemplate`. Use `template.profile` to access the
        `ModelProfile` describing the template's declared revision and
        extensions (a subset of `supported_extensions`).
    """
    return decode_job_template_dict(
        template,
        supported_extensions=list(supported_extensions) if supported_extensions is not None else None,
        caller_limits=caller_limits,
    )


def decode_environment_template(
    *,
    template: dict[str, Any],
    supported_extensions: Optional[list[str]] = None,
) -> EnvironmentTemplate:
    """Decode and validate an environment template from a Python dict.

    See `decode_job_template` for `supported_extensions` semantics.
    Environment templates do not accept caller limits.
    """
    return decode_environment_template_dict(
        template,
        supported_extensions=list(supported_extensions) if supported_extensions is not None else None,
    )


def parse_model(*, model: Any = None, obj: dict[str, Any]) -> Any:
    """Decode a template from a dict, auto-detecting the type.

    The `model` parameter is accepted for backward compatibility but
    ignored — the template type is determined from `specificationVersion`
    in the dict.
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


# ── Capability validation (Python side) ──


def validate_amount_capability_name(
    name: str = "", *, capability_name: str = "", standard_capabilities=None
) -> str:
    import re

    n = capability_name or name
    if not re.match(
        r"(?i)\A([A-Za-z_][A-Za-z0-9_]*:)?amount\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*\Z",
        n,
    ):
        raise ValueError(f"'{n}' is not a valid amount capability name")
    _validate_capability_scoping(n, "amount", standard_capabilities)
    return n


def validate_attribute_capability_name(
    name: str = "", *, capability_name: str = "", standard_capabilities=None
) -> str:
    import re

    n = capability_name or name
    if not re.match(
        r"(?i)\A([A-Za-z_][A-Za-z0-9_]*:)?attr\.[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*\Z",
        n,
    ):
        raise ValueError(f"'{n}' is not a valid attribute capability name")
    _validate_capability_scoping(n, "attr", standard_capabilities)
    return n


_RESERVED_SCOPES = {"worker", "job", "step", "task"}


def _validate_capability_scoping(name: str, prefix: str, standard_capabilities=None) -> None:
    import re

    vendor_match = re.match(r"(?i)\A([A-Za-z_][A-Za-z0-9_]*):(.+)\Z", name)
    bare_name = vendor_match.group(2) if vendor_match else name

    parts = bare_name.split(".")
    if len(parts) >= 3:
        scope = parts[1].lower()
        if scope in _RESERVED_SCOPES:
            if vendor_match:
                raise ValueError(
                    f"'{name}' is not valid: vendor-prefixed names cannot use reserved scope '{scope}'"
                )
            if standard_capabilities is not None:
                if name.lower() not in [c.lower() for c in standard_capabilities]:
                    raise ValueError(
                        f"'{name}' is not a recognized standard capability in scope '{scope}'"
                    )


# ── Standard capabilities ──

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


StepDependencyGraphNode = _RustStepDependencyNode
StepDependencyGraphStepToStepEdge = _RustStepDependencyEdge


from .._version import version  # noqa: E402


__all__ = (
    # Decode + create
    "create_job",
    "decode_environment_template",
    "decode_job_template",
    "document_string_to_object",
    "merge_job_parameter_definitions",
    "model_to_object",
    "parse_model",
    "preprocess_job_parameters",
    # Capability validation
    "validate_amount_capability_name",
    "validate_attribute_capability_name",
    "STANDARD_AMOUNT_CAPABILITIES",
    "STANDARD_ATTRIBUTE_CAPABILITIES",
    # Profile types
    "ModelProfile",
    "ModelExtension",
    "SpecificationRevision",
    "CallerLimits",
    "ValidationContext",
    "RevisionExtensions",
    # Errors
    "CompatibilityError",
    "DecodeValidationError",
    "ExpressionError",
    "FormatStringError",
    "ModelValidationError",
    "TokenError",
    "UnsupportedSchema",
    # Templates and jobs
    "DocumentType",
    "EnvironmentTemplate",
    "Job",
    "JobParameter",
    "JobParameterDefinition",
    "JobParameterInputValues",
    "JobParameterType",
    "JobParameterValues",
    "JobTemplate",
    "ParameterValue",
    "ParameterValueType",
    "Step",
    "StepDependency",
    "StepDependencyGraph",
    "StepDependencyGraphNode",
    "StepDependencyGraphStepToStepEdge",
    "StepParameterSpace",
    "StepParameterSpaceIterator",
    "TaskParameterSet",
    "TaskParameterType",
    "TemplateSpecificationVersion",
    "OpenJDModel",
    # Expr re-exports
    "ArgString",
    "CommandString",
    "FormatString",
    "IntRangeExpr",
    "RangeExpr",
    "SymbolTable",
    # Misc
    "CancelationMethodNotifyThenTerminate",
    "CancelationMethodTerminate",
    "EmbeddedFile",
    "EmbeddedFileText",
    "EmbeddedFiles",
    "ValueReferenceConstants",
    "version",
)
