# Python Model Interface (`openjd.model`)

Rust-backed implementation of the Open Job Description model library.
Handles template parsing, validation, job creation, and task iteration.
No Pydantic dependency.

## Functions

### Decode

#### `decode_job_template`

Decode and validate a job template from a Python dict. Mirrors the
Rust `openjd_model::decode_job_template` signature: takes a list of
extension *strings* as the caller's allowlist, plus optional
`CallerLimits`.

```python
from openjd.model import decode_job_template

template = decode_job_template(
    template={
        "specificationVersion": "jobtemplate-2023-09",
        "name": "MyRenderJob",
        "extensions": ["EXPR"],
        "parameterDefinitions": [
            {"name": "Frames", "type": "STRING", "default": "1-10"},
        ],
        "steps": [{
            "name": "Render",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Frame", "type": "INT", "range": "{{Param.Frames}}"}
                ]
            },
            "script": {
                "actions": {
                    "onRun": {
                        "command": "render",
                        "args": ["--frame", "{{Task.Param.Frame}}"]
                    }
                }
            }
        }],
    },
    supported_extensions=["EXPR"],
)
template.name        # "MyRenderJob"
template.profile     # ModelProfile from the *template's* declared extensions:
                     # ModelProfile(revision=V2023_09, extensions=[EXPR])
```

Argument semantics (matching the Rust API):

* `supported_extensions` — the caller's *allowlist*. The template's
  `extensions:` field is validated against this list; any name in the
  template that is not both a recognized `ModelExtension` AND in this
  list is rejected with `Unsupported extension names: ...`. Pass
  `None` (the default) for an empty allowlist.
* `caller_limits` — optional `CallerLimits` to tighten spec-defined
  limits (max steps, max envs, max task count, max template size, …).

The `ModelProfile` type is used as an *output* of decoding (via
`JobTemplate.profile`) and as an *input* to other functions
(`create_job(validation_context=...)`, `ModelProfile.to_expr_profile(host)`).
It is not an input to `decode_*_template` itself — that function takes
a flat list of strings, mirroring the Rust crate.

#### `decode_job_template_str`

Decode directly from a YAML or JSON string — no intermediate dict.

```python
from openjd.model import decode_job_template_str, DocumentType

yaml_str = """
specificationVersion: jobtemplate-2023-09
name: SimpleJob
steps:
  - name: Step1
    script:
      actions:
        onRun:
          command: echo
          args: ["hello"]
"""
template = decode_job_template_str(yaml_str, DocumentType.YAML)
```

#### `decode_environment_template` / `decode_environment_template_str`

Same pattern for environment templates.

```python
from openjd.model import decode_environment_template

env_template = decode_environment_template(template={
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "PythonVenv",
        "script": {
            "actions": {
                "onEnter": {"command": "python", "args": ["-m", "venv", ".venv"]},
                "onExit": {"command": "rm", "args": ["-rf", ".venv"]},
            }
        }
    }
})
```

### Job Creation

#### `create_job`

Create a fully resolved job from a template and parameter values.

```python
from openjd.model import decode_job_template, create_job

template = decode_job_template(template={
    "specificationVersion": "jobtemplate-2023-09",
    "name": "{{Param.JobName}}",
    "parameterDefinitions": [
        {"name": "JobName", "type": "STRING"},
    ],
    "steps": [{
        "name": "Render",
        "script": {"actions": {"onRun": {"command": "render"}}}
    }]
})

job = create_job(
    job_template=template,
    job_parameter_values={"JobName": {"type": "STRING", "value": "MyJob"}},
)
job.name                          # "MyJob"
job.steps[0].name                 # "Render"
str(job.steps[0].script.actions.onRun.command)  # "render"
```

#### `preprocess_job_parameters`

Validate and coerce job parameter values. Accepts `str` or `pathlib.Path`
for directory arguments.

```python
from openjd.model import decode_job_template, preprocess_job_parameters
from pathlib import Path

template = decode_job_template(template={
    "specificationVersion": "jobtemplate-2023-09",
    "name": "Test",
    "parameterDefinitions": [
        {"name": "Count", "type": "INT", "default": "10"},
    ],
    "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
})

params = preprocess_job_parameters(
    job_template=template,
    job_parameter_values={"Count": "5"},
    job_template_dir=Path("."),
    current_working_dir=Path("."),
)
# Returns validated parameter dict
```

#### `merge_job_parameter_definitions`

Merge parameter definitions from a job template and environment templates.

```python
from openjd.model import decode_job_template, merge_job_parameter_definitions

template = decode_job_template(template={...})
merged = merge_job_parameter_definitions(job_template=template)
```

### Utility

#### `model_to_object`

Serialize a model object to a dict. Calls `to_dict()` if available.

```python
from openjd.model import model_to_object
# model_to_object(model=some_object)  # returns dict
```

## Output Types (from Rust)

Both snake_case and camelCase property accessors are provided.

### `Job`

The fully resolved job, produced by `create_job`.

```python
job.name                    # "MyRenderJob"
job.description             # Optional[str]
job.revision                # "2023-09"
job.extensions              # Optional[list[str]], e.g. ["EXPR"]
job.steps                   # list[Step]
job.parameters              # dict[str, JobParameter]
job.job_environments        # Optional[list[Environment]]
job.jobEnvironments         # same (camelCase alias)
```

### `Step`

A step within a job.

```python
step = job.steps[0]
step.name                   # "Render"
step.description            # Optional[str]
step.script                 # StepScript
step.parameterSpace         # Optional[StepParameterSpace]
step.stepEnvironments       # Optional[list[Environment]]
step.dependencies           # Optional[list[StepDependency]]
step.resolvedBindings       # Optional[list[str]] — let binding strings
step.resolved_symtab        # Optional[SymbolTable] — resolved at step scope
```

### `StepScript`

```python
script = step.script
script.revision             # "2023-09"
script.actions              # StepActions
script.let                  # Optional[list[str]], e.g. ["end = Param.Start + Param.Count - 1"]
script.embeddedFiles        # Optional[list[EmbeddedFile]]
```

### `StepActions` / `Action`

```python
action = step.script.actions.onRun
action.command              # FormatString — resolve at runtime with .resolve(symtab, library)
action.args                 # Optional[list[FormatString]]
action.timeout              # Optional[str]
action.cancelation          # Optional[CancelationMode]

# At runtime (in sessions):
from openjd.expr import SymbolTable, FunctionLibrary
symtab = SymbolTable({"Param.Frame": 42})
library = FunctionLibrary()
command_str = str(action.command.resolve(symtab, library))
```

### `Environment`

```python
env = job.job_environments[0]
env.name                    # "PythonVenv"
env.description             # Optional[str]
env.script                  # Optional[EnvironmentScript]
env.variables               # Optional[dict[str, str]]
```

### `EnvironmentScript` / `EnvironmentActions`

```python
env.script.actions.onEnter  # Optional[Action]
env.script.actions.onExit   # Optional[Action]
env.script.embeddedFiles    # Optional[list[EmbeddedFile]]
```

### `EmbeddedFile`

```python
ef = step.script.embeddedFiles[0]
ef.name                     # "run.sh"
ef.type_                    # "TEXT"
ef.filename                 # "run.sh"
ef.data                     # file content string
```

### `JobParameter`

```python
param = job.parameters["Count"]
param.name                  # "Count"
param.param_type            # "INT"
param.value                 # ExprValue — use .item() to get native value
param.value.item()          # 5
```

### `StepParameterSpace`

```python
space = step.parameterSpace
space.taskParameterDefinitions  # dict
space.combination               # Optional[str]
```

### `StepDependency`

```python
dep = step.dependencies[0]
dep.dependsOn               # "PreviousStep"
```

### `CancelationMode`

```python
cancel = action.cancelation
cancel.mode                 # "TERMINATE" or "NOTIFY_THEN_TERMINATE"
cancel.notify_period_in_seconds  # Optional[int]
```

## Template Types (from Rust, opaque)

Templates are produced by `decode_*` functions and passed to `create_job`.

```python
template = decode_job_template(template={...})
template.name                    # raw format string, e.g. "{{Param.JobName}}"
template.specification_version   # TemplateSpecificationVersion enum
template.description             # Optional[str]
```

## Iteration Types (from Rust)

### `StepParameterSpaceIterator`

Iterate over task parameter combinations for a step.

```python
from openjd.model import StepParameterSpaceIterator

it = StepParameterSpaceIterator(step=job.steps[0])
# or: it = StepParameterSpaceIterator(space=step.parameterSpace)

len(it)                     # total task count, e.g. 10
it[0]                       # {"Frame": 1}
it[-1]                      # {"Frame": 10}
for params in it:
    print(params["Frame"])  # 1, 2, 3, ...

it.names()                  # {"Frame"}
it.chunks_adaptive          # bool
it.chunks_parameter_name    # Optional[str]
it.chunks_default_task_count  # Optional[int]
```

### `StepDependencyGraph`

Step dependency graph for topological ordering.

```python
from openjd.model import StepDependencyGraph

graph = StepDependencyGraph(job=job)
graph.topo_sorted()         # ["Render", "Composite"] — dependency order
graph.step_names()          # ["Render", "Composite"]
```

## Enums

### `DocumentType` (Rust)

```python
from openjd.model import DocumentType
DocumentType.JSON
DocumentType.YAML
```

### `TemplateSpecificationVersion` (Python str Enum)

```python
from openjd.model import TemplateSpecificationVersion as TSV

TSV.JOBTEMPLATE_v2023_09    # "jobtemplate-2023-09"
TSV.ENVIRONMENT_v2023_09    # "environment-2023-09"
TSV.is_job_template(TSV.JOBTEMPLATE_v2023_09)  # True
```

### `JobParameterType` (Rust)

```python
from openjd.model import JobParameterType
JobParameterType.STRING     # STRING, INT, FLOAT, PATH, BOOL, RANGE_EXPR
JobParameterType.LIST_INT   # LIST_STRING, LIST_INT, LIST_FLOAT, LIST_PATH, LIST_BOOL, LIST_LIST_INT
```

### `TaskParameterType` (Rust)

```python
from openjd.model import TaskParameterType
TaskParameterType.INT       # INT, FLOAT, STRING, PATH, CHUNK_INT
```

### `SpecificationRevision` (Python str Enum)

```python
from openjd.model import SpecificationRevision
SpecificationRevision.v2023_09  # "2023-09"
```

### `ValueReferenceConstants` (Python str Enum)

Symbol table key prefixes used by sessions at runtime.

```python
from openjd.model import ValueReferenceConstants as VRC

VRC.JOB_PARAMETER_PREFIX        # "Param"
VRC.TASK_PARAMETER_PREFIX       # "Task.Param"
VRC.WORKING_DIRECTORY           # "Session.WorkingDirectory"
VRC.HAS_PATH_MAPPING_RULES     # "Session.HasPathMappingRules"
```

## Simple Types (Python)

```python
from openjd.model import ParameterValue, JobParameterType

# A parameter value with its type
pv = ParameterValue(type=JobParameterType.STRING, value="hello")

## Profile

### `ModelProfile` / `ModelExtension` / `SpecificationRevision` / `CallerLimits` / `ValidationContext`

Profile types that describe what features a template or job uses.
Mirror the equivalent types in the underlying `openjd-model` Rust crate.

`decode_*_template` does **not** take a `ModelProfile` — it takes a
`supported_extensions: list[str]` allowlist (see [Decode](#decode)
above), matching the Rust API. `ModelProfile` is an *output* of
decoding (read it off `JobTemplate.profile`) and an *input* to
`create_job(validation_context=...)` and to the bridge to the
expression engine.

```python
from openjd.model import (
    ModelProfile, ModelExtension, SpecificationRevision,
    CallerLimits, ValidationContext,
    decode_job_template, create_job,
)

# 1. Decode a template using the string-list allowlist (Rust-aligned).
template = decode_job_template(template={...}, supported_extensions=["EXPR"])

# 2. Read the template's declared profile back out.
profile = template.profile        # ModelProfile(revision=V2023_09, extensions=[EXPR])
profile.revision                  # SpecificationRevision.V2023_09
profile.extensions                # [ModelExtension.EXPR]
profile.has_extension(ModelExtension.EXPR)  # True

# 3. Build it manually if needed (e.g. when validating against a different
#    policy than the template declared).
manual = ModelProfile(extensions=[ModelExtension.EXPR, ModelExtension.TASK_CHUNKING])
ModelProfile.from_strings(SpecificationRevision.V2023_09, ["EXPR"])

# 4. Pass to create_job through a ValidationContext if you want to
#    override the template's default validation context.
limits = CallerLimits(max_step_count=100, max_task_count=10_000)
ctx = ValidationContext(profile, caller_limits=limits)
job = create_job(
    job_template=template,
    job_parameter_values={...},
    validation_context=ctx,   # optional; defaults to template.default_validation_context()
)

# 5. Bridge to the expression engine.
from openjd.expr import HostContext
expr_profile = profile.to_expr_profile(HostContext.unresolved())
```

`ModelExtension` members:

| Member | String form | Notes |
|---|---|---|
| `TASK_CHUNKING` | `"TASK_CHUNKING"` | RFC 0001 |
| `REDACTED_ENV_VARS` | `"REDACTED_ENV_VARS"` | RFC 0003 |
| `FEATURE_BUNDLE_1` | `"FEATURE_BUNDLE_1"` | RFC 0004 |
| `EXPR` | `"EXPR"` | RFC 0005 |

### `RevisionExtensions` (legacy)

`RevisionExtensions(spec_rev=..., supported_extensions=[...])` is a
thin Python wrapper kept for backward compatibility with code in
`openjd-sessions`, `openjd-cli`, and `deadline-cloud-worker-agent`.
It exposes `.to_profile()` to convert to a `ModelProfile`. New code
should construct a `ModelProfile` directly.

from openjd.model import CancelationMethodTerminate, CancelationMethodNotifyThenTerminate

CancelationMethodTerminate(mode="TERMINATE")
CancelationMethodNotifyThenTerminate(mode="NOTIFY_THEN_TERMINATE", notify_period_in_seconds=120)
```

## Compatibility Aliases

| Alias | Target | Usage |
|---|---|---|
| `IntRangeExpr` | `RangeExpr` | `IntRangeExpr("1-10")` |
| `CommandString` | `FormatString` | `CommandString("echo")` |
| `ArgString` | `FormatString` | `ArgString("{{Param.Frame}}")` |
| `EmbeddedFileText` | `EmbeddedFile` | isinstance checks |
| `EmbeddedFiles` | `list` | type alias |
| `JobParameterValues` | `dict` | `dict[str, ParameterValue]` |
| `TaskParameterSet` | `dict` | `dict[str, Any]` |

## Exceptions

```python
from openjd.model import DecodeValidationError, decode_job_template

# Invalid template
try:
    decode_job_template(template={"bad": "template"})
except DecodeValidationError as e:
    str(e)  # "Template is missing Open Job Description schema version key: specificationVersion"

# Empty steps
try:
    decode_job_template(template={
        "specificationVersion": "jobtemplate-2023-09",
        "name": "Test",
        "steps": [],
    })
except DecodeValidationError as e:
    str(e)  # validation error about empty steps
```

| Exception | Base |
|---|---|
| `DecodeValidationError` | `ValueError` |
| `ModelValidationError` | `ValueError` |
| `UnsupportedSchema` | `ValueError` |
| `ExpressionError` | `ValueError` |
| `FormatStringError` | `ValueError` |
| `CompatibilityError` | `Exception` |
| `TokenError` | `Exception` |
