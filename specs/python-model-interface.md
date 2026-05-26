# Python Model Interface (`openjd.model`)

Rust-backed implementation of the Open Job Description model library.
Handles template parsing, validation, job creation, and task iteration.
No Pydantic dependency.

## Architecture

The `openjd.model._v1` namespace mirrors the underlying
[`openjd-model`][openjd-model] Rust crate's two-layer architecture:

1. **Revision-neutral types** — there is exactly one `JobTemplate`
   pyclass (under `openjd.model._v1.template.JobTemplate`), one
   `EnvironmentTemplate`, one `Action`, one `StepTemplate`, and so
   on. The set of pyclasses does **not** vary by specification
   revision.
2. **Revision-specific validation** — the
   `specificationVersion` field of the decoded template is read at
   parse time and used to dispatch the correct revision's
   validation pass on the parsed structure. The validation pass
   enforces revision-specific constraints (allowed extensions,
   field shapes, value bounds, etc.) but the resulting Python
   objects are the same revision-neutral types regardless of
   revision.

This is a deliberate divergence from the v0 (`openjd.model`)
architecture, which used Pydantic's discriminated-union machinery
to produce per-revision class hierarchies (e.g.
`v2023_09.JobTemplate`, with siblings under
`OpenJDModel_v2023_09`). v0 has ~85 per-revision classes under
`openjd.model.v2023_09`; the v1 surface has none. This is **not**
a regression — it is the v1 architecture by design:

* The Rust crate has no per-revision types either. The revision
  version is just a string field on the parsed template; the
  parsed type is identical regardless of revision.
* Future spec revisions that don't change the Python-level shape
  of decoded objects need *no* new pyclass at all — only a new
  validation arm in
  [`openjd_model::template::validation::validate_job_template`][validate].
* Future revisions that *do* change shape will be addressed when
  they ship; the most likely choice is to extend the existing
  pyclass surface with optional new fields rather than introduce
  parallel revision-typed classes.

If a v0 caller writes `isinstance(t, v2023_09.JobTemplate)`, the
v1 equivalent is `isinstance(t, template.JobTemplate)`. To
discriminate by revision, read
`t.specification_version` (returns a `TemplateSpecificationVersion`
enum value).

[openjd-model]: https://github.com/OpenJobDescription/openjd-rs/tree/main/crates/openjd-model
[validate]: https://github.com/OpenJobDescription/openjd-rs/blob/main/crates/openjd-model/src/template/validation/mod.rs

## Module Layout

The `openjd.model._v1` package is split into four submodules that
mirror the underlying Rust crate's organization. The top-level
`openjd.model._v1` re-exports the *entry points* (decode/create
functions, Python-only compatibility classes, str-Enum shims),
but **does not** re-export the structural pyclasses — those live
in their respective submodules. Examples in this spec import each
symbol from its canonical location.

| Submodule | Contents |
|---|---|
| `openjd.model._v1` (top level) | Entry-point functions (`decode_job_template`, `decode_job_template_str`, `decode_environment_template`, `decode_environment_template_str`, `create_job`, `preprocess_job_parameters`, `merge_job_parameter_definitions`, `evaluate_let_bindings`, `decode_template`), the `CallerLimits` and `ModelProfile` cross-cutting types, `DocumentType` (also in `.types`), Python-only compat (`SpecificationRevision`, `TemplateSpecificationVersion`, `ParameterValue`, `ValueReferenceConstants`, `RevisionExtensions`, `CancelationMethod*`, `CommandString`, `ArgString`, `EmbeddedFileText`, `EmbeddedFiles`, `StepDependencyGraphNode`, `StepDependencyGraphStepToStepEdge`), capability-validation helpers, and the legacy `openjd.expr` re-exports (`SymbolTable`, `FormatString`, `RangeExpr`, `ExpressionError`, `FormatStringError`). Also re-exports `DecodeValidationError`, `ModelValidationError`, and `UnsupportedSchema` from `.errors` for top-level convenience. |
| `openjd.model._v1.template` | Template-time pyclasses returned by `decode_*_template`: `JobTemplate`, `EnvironmentTemplate`, `StepTemplate`, `Action`, `EmbeddedFile`, the typed `JobParameterDefinition`/`TaskParameterDefinition`/`*UserInterface` variants, etc. |
| `openjd.model._v1.job` | Job-time pyclasses returned by `create_job`: `Job`, `Step`, `StepScript`, `StepActions`, `Action`, `Environment`, `StepParameterSpace`, `StepParameterSpaceIterator`, `StepDependencyGraph`, the typed task-parameter pyclasses, and the job-time `EmbeddedFile`. |
| `openjd.model._v1.types` | Cross-cutting types: `JobParameterType`, `TaskParameterType`, `DocumentType`, `ModelProfile`, `ModelExtension`, `SpecificationRevision` (Rust pyclass form), `CallerLimits`, `ValidationContext`. |
| `openjd.model._v1.errors` | Exception classes raised by decode/create paths: `DecodeValidationError`, `ModelValidationError`, `UnsupportedSchema`. |

## Functions

### Decode

> **Implementation note — Python-dict input.** The four
> `decode_*_template{,_str}` functions all share a Python→Rust
> conversion shim. The dict-shaped variants (`decode_job_template`
> / `decode_environment_template`) convert the Python dict to
> `serde_json::Value` via `json.dumps` + `serde_json::from_str`
> before handing off to the upstream Rust validator. This detour
> looks wasteful but the alternatives are not actually faster:
> a `pythonize::depythonize` prototype (against `pyo3 = 0.28`)
> regressed end-to-end decode time by 12% on small templates and
> 5% on medium templates (20 steps × 20 parameter definitions),
> because CPython's C-level `json.dumps` plus
> `serde_json::from_str` together are faster than `pythonize`'s
> PyO3-driven recursive walk. The conversion step is also only
> ~0.6% of end-to-end cost — template validation in
> [`openjd_model::decode_*_template`][openjd-model] dominates —
> so even a notionally faster shim wouldn't be visible to
> callers. As a side effect, both paths reject non-JSON-
> serialisable values (`Decimal`, `Path`, custom objects) with
> the same `unsupported type` error: `pythonize` would not
> have changed that.
>
> If decode performance ever matters for a workload, the
> productive optimisation lives in the upstream Rust validator,
> not in the conversion shim.

#### `decode_job_template`

Decode and validate a job template from a Python dict. Mirrors the
Rust `openjd_model::decode_job_template` signature: takes a list of
extension *strings* as the caller's allowlist, plus optional
`CallerLimits`.

```python
from openjd.model._v1 import decode_job_template

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

#### `decode_template` (deprecated)

Deprecated alias for ``decode_job_template``. Mirrors the v0
reference, which also exports a deprecated ``decode_template`` for
backward compatibility. New code should call ``decode_job_template``
directly.

```python
from openjd.model._v1 import decode_template

# Same signature and return type as decode_job_template.
template = decode_template(template={...})
```

Will be removed in a future release.

#### `decode_job_template_str`

Decode directly from a YAML or JSON string — no intermediate dict.
Convenience wrapper around the dict-shaped entry point above.

```python
from openjd.model._v1 import decode_job_template_str, DocumentType

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

The ``format`` argument defaults to ``DocumentType.YAML``, which is
also a superset of JSON, so most callers can omit it. Pass
``DocumentType.JSON`` to force strict JSON parsing — useful when
the source is known to be JSON and the caller wants JSON-only
diagnostics on parse failures.

``decode_job_template_str`` accepts the same ``supported_extensions``
and ``caller_limits`` kwargs as :func:`decode_job_template`.

#### `decode_environment_template`

Decode and validate an environment template from a Python dict.

```python
from openjd.model._v1 import decode_environment_template

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

``decode_environment_template`` accepts ``supported_extensions``
with the same semantics as :func:`decode_job_template`. Environment
templates do not accept ``caller_limits``.

#### `decode_environment_template_str`

Decode an environment template directly from a YAML or JSON string.

```python
from openjd.model._v1 import decode_environment_template_str, DocumentType

yaml_str = """
specificationVersion: environment-2023-09
environment:
  name: PythonVenv
  script:
    actions:
      onEnter: {command: python, args: ["-m", "venv", ".venv"]}
      onExit:  {command: rm, args: ["-rf", ".venv"]}
"""
env_template = decode_environment_template_str(yaml_str)
```

Same defaults as :func:`decode_job_template_str`: ``format``
defaults to ``DocumentType.YAML``. Accepts ``supported_extensions``;
environment templates do not accept ``caller_limits``.

### Job Creation

#### `create_job`

Create a fully resolved job from a template and parameter values.

```python
from openjd.model._v1 import decode_job_template, create_job

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
from openjd.model._v1 import decode_job_template, preprocess_job_parameters
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
from openjd.model._v1 import decode_job_template, merge_job_parameter_definitions

template = decode_job_template(template={...})
merged = merge_job_parameter_definitions(job_template=template)
```

#### `evaluate_let_bindings`

Evaluate a list of let-binding strings against a symbol table and
return a new symbol table containing both the original input symbols
and the new bound names.

The function lives under ``openjd.model._v1`` rather than
``openjd.expr`` because the binding implementation is in the
``openjd-model`` Rust crate (``openjd_model::evaluate_let_bindings``)
— it raises a model-layer ``ExpressionError`` and is consumed by
the model crate's job-creation runtime (and by the sessions runtime
when a step's ``script.let`` bindings need to be resolved against
the current task-scope symbols before ``Session.run_task``).

```python
from openjd.expr import SymbolTable
from openjd.model._v1 import evaluate_let_bindings

symtab = SymbolTable({"Param.Start": 1, "Param.Count": 10})
resolved = evaluate_let_bindings(
    ["end = Param.Start + Param.Count - 1"],
    symtab,
)
resolved["end"].item()         # 10
resolved["Param.Start"].item() # 1 — input symbols are preserved
```

Each binding is parsed and evaluated in left-to-right order against
the running symbol table, so a later binding may reference names
introduced by earlier ones:

```python
result = evaluate_let_bindings(
    [
        "a = Param.X + 1",
        "b = a * 2",
        "c = a + b",
    ],
    SymbolTable({"Param.X": 10}),
)
result["a"].item(), result["b"].item(), result["c"].item()  # (11, 22, 33)
```

The full signature is
``evaluate_let_bindings(bindings, symtab, *, profile=None) -> SymbolTable``.
``profile`` accepts an [``ExprProfile``][profile] when the caller
needs a non-default revision / extension set or a configured
``HostContext``; omitting it uses the current profile.

[profile]: ./python-expr-interface.md#exprrevision--exprextension--hostcontext--exprprofile

A binding without ``=`` raises ``ExpressionError`` with the
offending text in the message
(``"Missing '=' in let binding: <text>"``); a binding whose
right-hand side fails to parse or evaluate raises
``ExpressionError`` with a diagnostic that names the offending
binding (``"Error evaluating let binding '<name>': ..."``).

### Utility

#### `model_to_object` — v0-only, not implemented in v1

`model_to_object(*, model)` is a pure-Python helper from
`openjd.model` (the v0 / pydantic-based reference) that walks a
`BaseModel.model_dump()` result and converts nested `Decimal`
instances back to strings so the resulting dict is JSON/YAML-
serializable. It is **not** part of the v1 (Rust-backed)
interface — the v1 model pyclasses (`JobTemplate`,
`EnvironmentTemplate`, the various `*ParameterDefinition`s, etc.)
do not have a general "serialize this whole model back to a
JSON-shaped dict" method, and there are no plans to add one.

If specific use cases surface that need similar functionality
(e.g. round-tripping a job template back to YAML for diffing,
or extracting a particular sub-model as a dict), they will be
addressed as targeted helpers on the relevant pyclass(es) — not
as a single `model_to_object` umbrella API. Reach out with the
concrete use case and we'll decide what shape that helper takes.

The v0 module retains `from openjd.model import model_to_object`
unchanged; it works on v0 / pydantic models only, and importing
it through `openjd.model._v1` is intentionally not supported.

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

`Step` defines `__eq__` and `__hash__` by **name only** — two
``Step`` instances with the same ``name`` compare equal and hash
identically, regardless of script/parameter-space/etc. content.
This matches how `StepDependencyGraph` and the worker agent
identify steps for graph operations and runtime correlation.

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
ef.type                     # "TEXT"
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
space.taskParameterDefinitions  # dict[str, IntTaskParameter | FloatTaskParameter |
                                #            StringTaskParameter | PathTaskParameter |
                                #            ChunkIntTaskParameter]
space.combination               # Optional[str]
```

Each value in `taskParameterDefinitions` is one of five typed
pyclasses, mirroring the underlying Rust `TaskParameter` runtime enum
1:1. Discriminate by `isinstance` or by the `type` getter.

### `IntTaskParameter` / `FloatTaskParameter` / `StringTaskParameter` / `PathTaskParameter`

```python
F = step.parameterSpace.taskParameterDefinitions["F"]
isinstance(F, IntTaskParameter)         # True for INT
F.type                                  # TaskParameterType.INT
F.range                                 # list[int] | RangeExpr  (INT only)
                                        # list[float]            (FLOAT)
                                        # list[str]              (STRING / PATH)
```

| Class | `type` | `range` element type |
|---|---|---|
| `IntTaskParameter` | `TaskParameterType.INT` | `list[int]` or `RangeExpr` |
| `FloatTaskParameter` | `TaskParameterType.FLOAT` | `list[float]` |
| `StringTaskParameter` | `TaskParameterType.STRING` | `list[str]` |
| `PathTaskParameter` | `TaskParameterType.PATH` | `list[str]` |

None of these four carry a `chunks` field — only `ChunkIntTaskParameter`
does. (The underlying Rust struct has `chunks: Option<ResolvedChunks>`
on the `Int` variant for shape reasons, but no resolver path ever
populates it; the binding mirrors the runtime *behaviour*.)

### `ChunkIntTaskParameter`

Available only when the `TASK_CHUNKING` extension is enabled.

```python
F = step.parameterSpace.taskParameterDefinitions["F"]
F.type                                  # TaskParameterType.CHUNK_INT
F.range                                 # list[int] | RangeExpr
F.chunks                                # TaskChunksDefinition (always set)
```

### `TaskChunksDefinition`

```python
chunks = chunk_int_param.chunks
chunks.default_task_count               # int
chunks.target_runtime_seconds           # Optional[int]
chunks.range_constraint                 # "CONTIGUOUS" or "NONCONTIGUOUS"
```

`range_constraint` is exposed as a string rather than a separate enum
class because it has only two values; future revisions may promote it
to a typed enum if a third variant is added.

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
template.specificationVersion    # camelCase alias for specification_version
template.description             # Optional[str]
template.steps                   # list[StepTemplate]
template.job_environments        # Optional[list[Environment]]
template.jobEnvironments         # camelCase alias

env_template = decode_environment_template(template={...})
env_template.environment         # Environment
env_template.specification_version
env_template.specificationVersion
```

The structural pyclasses for template-time types live under
``openjd.model._v1.template`` and mirror ``openjd_model::template``
in the Rust crate 1:1.

```python
from openjd.model._v1.template import (
    StepTemplate, Environment, Action,
    EnvironmentScript, EnvironmentActions,
    StepScript, StepActions, EmbeddedFile,
    HostRequirements, AmountRequirement, AttributeRequirement,
    StepDependency, CancelationMode, SimpleAction,
)
```

The classes whose names collide with their job-time counterparts at
``openjd.model._v1.job`` (``Action``, ``Environment``,
``CancelationMode``, ``EmbeddedFile``, ``EnvironmentScript``,
``EnvironmentActions``, ``StepScript``, ``StepActions``,
``StepDependency``) are exposed under both their short name and a
``Template``-prefixed alias (e.g. ``Action`` and ``TemplateAction``
are the same class).

### `StepTemplate`

```python
step = job_template.steps[0]
step.name                       # str
step.description                # Optional[str]
step.let_bindings               # Optional[list[str]] (alias: step.let)
step.dependencies               # Optional[list[StepDependency]]
step.step_environments          # Optional[list[Environment]] (alias: stepEnvironments)
step.host_requirements          # Optional[HostRequirements] (alias: hostRequirements)
step.parameter_space            # Optional[StepParameterSpaceDefinition]
                                #   (alias: parameterSpace)
step.script                     # Optional[StepScript]
# SimpleAction sugar (FEATURE_BUNDLE_1):
step.bash                       # Optional[SimpleAction]
step.python                     # Optional[SimpleAction]
step.cmd                        # Optional[SimpleAction]
step.powershell                 # Optional[SimpleAction]
step.node                       # Optional[SimpleAction]
```

### `Environment`

```python
env = job_template.job_environments[0]  # or env_template.environment
env.name                        # str
env.description                 # Optional[str]
env.script                      # Optional[EnvironmentScript]
env.variables                   # Optional[dict[str, FormatString]]
```

### `EnvironmentScript` / `StepScript`

```python
script = step.script  # or env.script
script.actions                  # StepActions or EnvironmentActions
script.let_bindings             # Optional[list[str]] (alias: script.let)
script.embedded_files           # Optional[list[EmbeddedFile]] (alias: embeddedFiles)
```

### `StepActions` / `EnvironmentActions`

```python
script.actions.on_run           # Action  (StepActions; alias: onRun)
script.actions.on_enter         # Optional[Action]  (EnvironmentActions; alias: onEnter)
script.actions.on_exit          # Optional[Action]  (EnvironmentActions; alias: onExit)
```

### `Action`

```python
action = step.script.actions.on_run
action.command                  # FormatString
action.args                     # Optional[list[FormatString]]
action.timeout                  # Optional[FormatString]
action.cancelation              # Optional[CancelationMode]
```

### `CancelationMode`

```python
cm = action.cancelation
cm.mode                         # "TERMINATE" or "NOTIFY_THEN_TERMINATE"
cm.notify_period_in_seconds     # Optional[FormatString] (alias: notifyPeriodInSeconds)
```

### `EmbeddedFile`

```python
ef = step.script.embedded_files[0]
ef.name                         # str
ef.type                         # "TEXT"
ef.filename                     # Optional[FormatString]
ef.data                         # Optional[FormatString]
ef.runnable                     # Optional[bool]
ef.end_of_line                  # Optional["LF" | "CRLF" | "AUTO"] (alias: endOfLine)
```

### `HostRequirements` / `AmountRequirement` / `AttributeRequirement`

```python
hr = step.host_requirements
hr.amounts                      # Optional[list[AmountRequirement]]
hr.attributes                   # Optional[list[AttributeRequirement]]

amt = hr.amounts[0]
amt.name                        # str
amt.min                         # Optional[FormatString]
amt.max                         # Optional[FormatString]

attr = hr.attributes[0]
attr.name                       # str
attr.any_of                     # Optional[list[FormatString]] (alias: anyOf)
attr.all_of                     # Optional[list[FormatString]] (alias: allOf)
```

### `StepDependency`

```python
dep = step.dependencies[0]
dep.depends_on                  # str (alias: dependsOn)
```

### `SimpleAction` (FEATURE_BUNDLE_1)

```python
sa = step.bash  # or .python, .cmd, .powershell, .node
sa.script                       # str
sa.let_bindings                 # Optional[list[str]] (alias: let)
sa.args                         # Optional[list[FormatString]]
sa.timeout                      # Optional[FormatString]
sa.cancelation                  # Optional[CancelationMode]
```

### `StepParameterSpaceDefinition` (5 typed task-parameter variants)

`StepTemplate.parameter_space` returns
`Optional[StepParameterSpaceDefinition]`. The `task_parameter_definitions`
list contains one of five typed pyclasses per element, mirroring the
underlying `template::TaskParameterDefinition` enum 1:1:

| Variant | Pyclass | `range` element type |
|---|---|---|
| `INT` | `IntTaskParameterDefinition` | `list[int]` or `FormatString` |
| `FLOAT` | `FloatTaskParameterDefinition` | `list[float \| FormatString]` or `FormatString` |
| `STRING` | `StringTaskParameterDefinition` | `list[FormatString]` or `FormatString` |
| `PATH` | `PathTaskParameterDefinition` | `list[FormatString]` or `FormatString` |
| `CHUNK[INT]` | `ChunkIntTaskParameterDefinition` | `list[int]` or `FormatString` |

Common attributes on every variant:

```python
defs = step.parameter_space.task_parameter_definitions  # list[...]
d = defs[0]
d.type                          # "INT" | "FLOAT" | "STRING" | "PATH" | "CHUNK[INT]"
d.name                          # str — the parameter name
d.range                         # see table above
```

For lists where the element type is `int`/`float`/`FormatString`, the
list-form vs format-string-form is dispatched by the binding: the
`.range` getter returns either a Python list (literal range) or a
`FormatString` (e.g. `"1-10:2"`, possibly carrying a
`{{Param.X}}` interpolation under the EXPR extension). Only `INT` and
`CHUNK[INT]` accept the list-form `[1, 2, 3]`; the others always carry
`FormatString` elements (which may themselves be literal or
interpolating).

The `CHUNK[INT]` variant additionally exposes:

```python
chunks = chunk_int_def.chunks   # ChunksDefinition
chunks.default_task_count       # int | FormatString  (alias: defaultTaskCount)
chunks.target_runtime_seconds   # Optional[int | FormatString] (alias: targetRuntimeSeconds)
chunks.range_constraint         # "CONTIGUOUS" or "NONCONTIGUOUS" (alias: rangeConstraint)
```

The combination expression on the parameter space is exposed as a raw
string (no AST):

```python
ps = step.parameter_space
ps.combination                  # Optional[str], e.g. "Param1 * (Param2, Param3)"
```

When the field is absent, `combination` is `None` and the resolver
defaults to a left-to-right product over the
`task_parameter_definitions` list.

### `JobParameterDefinition` (12 typed variants)

`JobTemplate.parameter_definitions` and
`EnvironmentTemplate.parameter_definitions` return
`Optional[list[JobParameterDefinition]]`, where each element is one
of twelve typed pyclasses, mirroring the runtime
`JobParameterDefinition` Rust enum 1:1:

| Variant | Pyclass | `default` type |
|---|---|---|
| `STRING` | `JobStringParameterDefinition` | `Optional[str]` |
| `INT` | `JobIntParameterDefinition` | `Optional[int]` |
| `FLOAT` | `JobFloatParameterDefinition` | `Optional[float]` |
| `PATH` | `JobPathParameterDefinition` | `Optional[str]` |
| `BOOL` (EXPR) | `JobBoolParameterDefinition` | `Optional[bool]` |
| `RANGE_EXPR` (EXPR) | `JobRangeExprParameterDefinition` | `Optional[str]` |
| `LIST[STRING]` (EXPR) | `JobListStringParameterDefinition` | `Optional[list[str]]` |
| `LIST[PATH]` (EXPR) | `JobListPathParameterDefinition` | `Optional[list[str]]` |
| `LIST[INT]` (EXPR) | `JobListIntParameterDefinition` | `Optional[list[int]]` |
| `LIST[FLOAT]` (EXPR) | `JobListFloatParameterDefinition` | `Optional[list[float]]` |
| `LIST[BOOL]` (EXPR) | `JobListBoolParameterDefinition` | `Optional[list[bool]]` |
| `LIST[LIST[INT]]` (EXPR) | `JobListListIntParameterDefinition` | `Optional[list[list[int]]]` |

Common attributes:

```python
d = template.parameter_definitions[0]
d.type                          # JobParameterType enum
d.name                          # str
d.description                   # Optional[str]
d.default                       # see table above
```

Type-specific attributes:

```python
# STRING / PATH variants:
d.allowed_values                # Optional[list[str]] (alias: allowedValues)
d.min_length                    # Optional[int]      (alias: minLength)
d.max_length                    # Optional[int]      (alias: maxLength)
# PATH only:
d.object_type                   # Optional["FILE" | "DIRECTORY"]  (alias: objectType)
d.data_flow                     # Optional["NONE" | "IN" | "OUT" | "INOUT"]  (alias: dataFlow)

# INT / FLOAT variants:
d.allowed_values                # Optional[list[int|float]]
d.min_value                     # Optional[int|float]  (alias: minValue)
d.max_value                     # Optional[int|float]  (alias: maxValue)

# LIST[*] variants (all): min_length / max_length
# LIST[PATH] variant: also object_type / data_flow
# RANGE_EXPR variant: min_length / max_length
# BOOL variant: only the common attributes
```

### `userInterface` types

Each `Job*ParameterDefinition` exposes a `user_interface` getter
(camelCase alias `userInterface`) that returns
`Optional[<TypedUserInterface>]`. The pyclass type returned is
specific to the parameter variant — see the table below. All UI
pyclasses share three common fields: `control: Optional[str]`,
`label: Optional[str]`, `group_label: Optional[str]` (camelCase
alias `groupLabel`).

| Job parameter variant | UI pyclass | Type-specific fields |
|---|---|---|
| `STRING` | `StringUserInterface` | (none) |
| `INT` | `IntUserInterface` | `single_step_delta: Optional[int]` |
| `FLOAT` | `FloatUserInterface` | `decimals: Optional[int]`, `single_step_delta: Optional[float]` |
| `PATH` | `PathUserInterface` | `file_filters: Optional[list[FileFilter]]`, `file_filter_default: Optional[FileFilter]` |
| `BOOL` (EXPR) | `BoolUserInterface` | (none) |
| `RANGE_EXPR` (EXPR) | `RangeExprUserInterface` | (none) |
| `LIST[STRING]`, `LIST[BOOL]` (EXPR) | `ListSimpleUserInterface` | (none) |
| `LIST[PATH]` (EXPR) | `ListPathUserInterface` | `file_filters`, `file_filter_default` (same as `PathUserInterface`) |
| `LIST[INT]` (EXPR) | `ListIntUserInterface` | `single_step_delta: Optional[int]` |
| `LIST[FLOAT]` (EXPR) | `ListFloatUserInterface` | `decimals`, `single_step_delta` (same as `FloatUserInterface`) |
| `LIST[LIST[INT]]` (EXPR) | `HiddenOnlyUserInterface` | (none) |

Multi-word getters have camelCase aliases:
`groupLabel`/`singleStepDelta`/`fileFilters`/`fileFilterDefault`.

Example:

```python
from openjd.model._v1.template import (
    JobIntParameterDefinition, IntUserInterface,
)
d = template.parameter_definitions[0]
if isinstance(d, JobIntParameterDefinition) and d.user_interface is not None:
    ui: IntUserInterface = d.user_interface
    ui.control                  # e.g. "SPIN_BOX" or "DROPDOWN_LIST"
    ui.label                    # Optional[str]
    ui.group_label              # Optional[str] (alias: groupLabel)
    ui.single_step_delta        # Optional[int] (alias: singleStepDelta)
```

The `control` field is preserved as a free-form `Optional[str]`;
the spec defines per-variant validation (e.g. `INT` accepts
`SPIN_BOX`/`DROPDOWN_LIST`/`HIDDEN`, `LIST[INT]` accepts
`SPIN_BOX_LIST`/`HIDDEN`, etc.) that the decoder enforces at
template-decode time.

### `FileFilter`

```python
ff = path_ui.file_filters[0]
ff.label                        # str
ff.patterns                     # list[str], e.g. ["*.png", "*.jpg"]
```

## Iteration Types (from Rust)

### `StepParameterSpaceIterator`

Iterate over task parameter combinations for a step.

```python
from openjd.model._v1.job import StepParameterSpaceIterator

it = StepParameterSpaceIterator(step=job.steps[0])
# or: it = StepParameterSpaceIterator(space=step.parameterSpace)

len(it)                     # total task count, e.g. 10
it[0]                       # {"Frame": 1}
it[-1]                      # {"Frame": 10}
for params in it:
    print(params["Frame"])  # 1, 2, 3, ...

it.names                    # {"Frame"} — property, not callable
it.chunks_adaptive          # bool
it.chunks_parameter_name    # Optional[str]
it.chunks_default_task_count  # Optional[int]

it.reset_iter()             # rewind to position 0; subsequent
                            # for/next iteration yields the first
                            # combination again
```

`reset_iter()` is useful for callers that want to re-walk the same
parameter space without rebuilding the iterator (the iterator caches
non-trivial state for chunked spaces). Indexing (``it[i]``) is
unaffected by iteration position; ``__contains__`` is also
non-mutating.

### `StepDependencyGraph`

Step dependency graph for topological ordering.

```python
from openjd.model._v1.job import StepDependencyGraph

graph = StepDependencyGraph(job=job)
graph.topo_sorted()         # ["Render", "Composite"] — dependency order
graph.step_names()          # ["Render", "Composite"]
```

## Enums

### `DocumentType` (Rust)

```python
from openjd.model._v1.types import DocumentType
DocumentType.JSON
DocumentType.YAML
```

### `TemplateSpecificationVersion` (Python str Enum)

```python
from openjd.model._v1 import TemplateSpecificationVersion as TSV

TSV.JOBTEMPLATE_v2023_09    # "jobtemplate-2023-09"
TSV.ENVIRONMENT_v2023_09    # "environment-2023-09"
TSV.is_job_template(TSV.JOBTEMPLATE_v2023_09)  # True
```

### `JobParameterType` (Rust)

```python
from openjd.model._v1.types import JobParameterType
JobParameterType.STRING     # STRING, INT, FLOAT, PATH, BOOL, RANGE_EXPR
JobParameterType.LIST_INT   # LIST_STRING, LIST_INT, LIST_FLOAT, LIST_PATH, LIST_BOOL, LIST_LIST_INT
```

### `TaskParameterType` (Rust)

```python
from openjd.model._v1.types import TaskParameterType
TaskParameterType.INT       # INT, FLOAT, STRING, PATH, CHUNK_INT
```

### `SpecificationRevision` (Python str Enum)

```python
from openjd.model._v1 import SpecificationRevision
SpecificationRevision.v2023_09  # "2023-09"
```

### `ValueReferenceConstants` (Python str Enum)

Symbol table key prefixes used by sessions at runtime.

```python
from openjd.model._v1 import ValueReferenceConstants as VRC

VRC.JOB_PARAMETER_PREFIX        # "Param"
VRC.TASK_PARAMETER_PREFIX       # "Task.Param"
VRC.WORKING_DIRECTORY           # "Session.WorkingDirectory"
VRC.HAS_PATH_MAPPING_RULES     # "Session.HasPathMappingRules"
```

## Simple Types (Python)

```python
from openjd.model._v1 import ParameterValue
from openjd.model._v1.types import JobParameterType

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
from openjd.model._v1 import (
    ModelProfile, SpecificationRevision,
    CallerLimits,
    decode_job_template, create_job,
)
from openjd.model._v1.types import ModelExtension, ValidationContext

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

from openjd.model._v1 import CancelationMethodTerminate, CancelationMethodNotifyThenTerminate

CancelationMethodTerminate(mode="TERMINATE")
CancelationMethodNotifyThenTerminate(mode="NOTIFY_THEN_TERMINATE", notify_period_in_seconds=120)
```

## Compatibility Aliases

| Alias | Target | Usage |
|---|---|---|
| `CommandString` | `FormatString` | `CommandString("echo")` |
| `ArgString` | `FormatString` | `ArgString("{{Param.Frame}}")` |
| `EmbeddedFileText` | `EmbeddedFile` | isinstance checks |
| `EmbeddedFiles` | `list` | type alias |
| `JobParameterValues` | `dict` | `dict[str, ParameterValue]` |
| `TaskParameterSet` | `dict` | `dict[str, Any]` |
| `ParameterValueType` | `JobParameterType` | legacy v0 name |

> **Note.** Earlier versions exposed an ``IntRangeExpr`` alias under
> ``openjd.model._v1`` for legacy parity with v0. Use
> ``openjd.expr.RangeExpr`` directly instead. The model layer no
> longer re-exports a range-expression type.

### Behavior change: `RangeExpr` iteration is always ascending

`openjd.expr.RangeExpr` always presents its values as an **increasing
list of integers**, regardless of how the source expression was
written. Iteration, indexing, and `__str__` all operate on the
canonical ascending form; the input's direction is not retained.

```python
from openjd.expr import RangeExpr

r = RangeExpr("-1 - -2 : -1")
list(r)   # [-2, -1]   (ascending)
r[0]      # -2
r[-1]     # -1

r = RangeExpr("10-1:-1")
list(r)   # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  (ascending)
```

This differs from the v0 pure-Python reference implementation
(`openjd.model._range_expr.IntRangeExpr`), which preserves the
user-supplied direction so that `IntRangeExpr.from_str("-1 - -2 : -1")`
iterates as `[-1, -2]`. The Rust-backed binding intentionally drops
that direction-preserving behavior because every consumer of
`RangeExpr` in the model layer treats a range as an unordered set of
integers, and the canonical form eliminates a class of edge cases
from indexing and length arithmetic. See
`openjd-rs/specs/expr/range-expr.md` ("Internal Representation") for
the underlying design rationale.

Practical consequences:

- Code that constructs a descending range expression and depends on
  iteration yielding values in descending order must sort the result
  itself, or build the expected ordering from the parsed `(start, end,
  step)` tuples.
- INT and CHUNK[INT] task parameters defined with a descending range
  (e.g. `"10-1:-1"`) iterate frames in ascending order under the Rust
  bindings.
- `__contains__`, `__len__`, and equality (`==`) are unaffected:
  `RangeExpr` equality is set-based.

## Exceptions

```python
from openjd.model._v1 import DecodeValidationError, decode_job_template

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
| `CompatibilityError` | `ValueError` |
| `TokenError` | `Exception` |

## Pickle Support

The following value types are pickleable. Pickled state round-trips
through ``pickle.dumps`` / ``pickle.loads`` and compares equal to the
original.

| Type | Reduces through |
|---|---|
| ``DocumentType`` | variant name (``YAML`` / ``JSON``) |
| ``JobParameterType`` | variant name (``INT``, ``LIST_PATH``, …) |
| ``TaskParameterType`` | variant name (``INT``, ``CHUNK_INT``, …) |
| ``ModelExtension`` | variant name (``EXPR``, ``TASK_CHUNKING``, …) |
| ``ModelProfile`` | constructor arguments (``revision``, ``extensions``) |
| ``CallerLimits`` | constructor arguments (six optional fields) |
| ``ValidationContext`` | constructor arguments (``profile``, ``caller_limits``) |
| ``JobParameterValue`` | constructor arguments (``type``, ``value``) |
| ``TaskParameterValue`` | constructor arguments (``type``, ``value``) |
| ``IntTaskParameter`` | constructor argument (``range``) |
| ``FloatTaskParameter`` | constructor argument (``range``) |
| ``StringTaskParameter`` | constructor argument (``range``) |
| ``PathTaskParameter`` | constructor argument (``range``) |
| ``ChunkIntTaskParameter`` | constructor arguments (``range``, ``chunks``) |
| ``TaskChunksDefinition`` | constructor arguments (three fields) |
| ``DecodeValidationError``, ``ModelValidationError``, ``UnsupportedSchema`` | standard exception pickle, under their canonical ``openjd.model._v1`` module path |

``SpecificationRevision`` and ``TemplateSpecificationVersion`` pickle
through the Python ``str``-Enum shims provided by ``openjd.model._v1``
(the underlying Rust pyclasses live at ``openjd._openjd_rs`` and pickle
correctly there too).

The decoded model containers (``JobTemplate``, ``EnvironmentTemplate``,
``Job``, ``Step``, etc.) and the live ``StepParameterSpaceIterator`` /
``StepDependencyGraph`` types are **not pickleable**, and there are no
plans to add pickle support to them. The intended round-trip path for a
decoded template is to keep the source document around (or its parsed
``dict``) and re-decode it on the other side; the decoded model object
is not designed to act as a wire format.

If a specific sub-model needs to cross a process boundary or be cached
to disk, the recommendation is to pickle (or otherwise serialise) the
inputs that produced it — the template ``dict`` and the
``job_parameter_values`` for ``Job``, etc. — rather than the model
itself. Targeted helpers will be considered case-by-case if a concrete
serialisation need arises that cannot be met by re-decoding.


## Bindings-internal helpers

The following functions are exposed by the underlying Rust extension
module ``openjd._openjd_rs`` but are **not** re-exported through the
``openjd.model._v1`` wrapper. They exist to support the openjd-sessions
runtime and the Deadline Cloud worker agent's wire-protocol decode
path; ordinary template/job consumers should not need them. They are
"subject to change" — signatures and semantics may evolve as the
runtime layer matures.

### `_openjd_rs.create_environment`

Convert a template-time ``EnvironmentTemplate`` into a job-time
``Environment``. Used by the sessions runtime when a session attaches
an externally-defined environment (queue environment, host
environment) to the job it's about to run.

```python
from openjd._openjd_rs import create_environment

env = create_environment(env_template)  # template-time → job-time
```

### `_openjd_rs.deserialize_step`

Reconstruct a job-side ``Step`` from the wire-protocol dict shape
that the Deadline Cloud service's ``GetStepDetails`` /
``BatchGetJobEntity`` API returns in the ``template`` field. The
payload is a serialised ``openjd_model::job::Step`` (i.e. a
*resolved* step, not a template-time ``StepTemplate``).

```python
from openjd._openjd_rs import deserialize_step

step = deserialize_step(step_dict_from_service)
session.run_task(step.script, ...)
```
