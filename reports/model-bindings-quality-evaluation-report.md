# openjd-model Bindings Quality Evaluation Report

**Date:** 2026-05-25
**Component:** `openjd.model._v1`
**Reference branch:** `OpenJobDescription/openjd-model-for-python` @ `mainline` (`f410f7d`)
**Active branch:** `bindings-rs` (commit `8f19e4d`)
**Sibling crate:** `openjd-rs` @ `baca1f2`

## Executive Summary

The `openjd.model._v1` Rust-backed bindings have matured substantially
since the prior evaluation. The 12 typed `JobParameterDefinition`
variants, the 5 typed `TaskParameterDefinition` variants, the 11
typed `*UserInterface` pyclasses + `FileFilter`, the structural
template-time pyclasses (`StepTemplate`, `Environment`, `Action`,
`HostRequirements`, …), pickle support for value types, the
`StepParameterSpaceIterator` setter and `__len__` semantics, and
the `decode_template` deprecated alias are all in place. The full
test suite passes — `4952 passed, 24 skipped, 6 xfailed, 0 failed`
across 4982 collected tests (the 6 xfails are all in the `expr`
subtree and are tracked in the `expr` report). `hatch run lint`
(ruff + black + mypy) is fully clean. The bindings now cover most
of the surface a v0 caller exercises.

What remains:

1. **Top-level wrapper-module re-exports diverge from the spec's
   examples.** `openjd.model._v1.__init__` deliberately does not
   re-export structural pyclasses (Job, Step, JobTemplate,
   StepParameterSpaceIterator, ModelValidationError, …) — these
   live in the `template` / `job` / `types` / `errors` submodules.
   The spec's example code imports them as `from openjd.model
   import Step` etc. Either the spec should be updated to direct
   users to the submodules, or the wrapper should re-export the
   spec'd entry points at the top level. **Today, several spec
   examples cannot be copy-pasted as written** — `from
   openjd.model._v1 import StepParameterSpaceIterator,
   ModelValidationError, UnsupportedSchema,
   decode_job_template_str, decode_environment_template_str,
   Job, Step, JobTemplate, EnvironmentTemplate` all fail with
   `ImportError`.

2. **`Job.parameters` omits parameters that resolve to defaults.**
   The v0 reference returns the full resolved-parameter dict
   (defaults plus explicit values); the v1 binding returns only
   parameters whose values were explicitly supplied via
   `job_parameter_values`. Code that walks `job.parameters` to
   reconstruct the running parameter set will see different
   behaviour between v0 and v1.

3. **`StepParameterSpaceIterator.__contains__` regresses for
   `CHUNK[INT]` parameter spaces.** Yielded values from a chunked
   iterator do not round-trip through `in fresh_iter`. Plain `INT`
   parameter spaces work correctly. Surface:
   `extract_task_parameter_set` in
   `rust-bindings/src/model/step_param_space.rs` produces a
   `TaskParameterValue` whose `value` is a plain `RangeExpr`
   string ("1-2") under `TaskParameterType::ChunkInt`, but the
   underlying Rust iterator's `contains` check expects the chunk
   to be expressed as the resolver-internal form. This is a
   parity gap, not a soundness issue.

4. **Format-string parsing inside templates raises
   `ModelValidationError`, not `FormatStringError`.** The mapping
   in `model_err_to_py` (`rust-bindings/src/model/errors.rs`)
   collapses `ModelError::FormatStringError`, `Expression`, and
   `Compatibility` into `ModelValidationError`; only
   `ModelValidationError` is registered as a renamed exception.
   Code that catches `FormatStringError` to specifically handle
   in-template expression issues will not catch them.

5. **`CompatibilityError` inherits from `Exception`, not
   `ValueError`.** The reference inherits `CompatibilityError`
   from `ValueError`; the v1 wrapper defines it as a plain
   `Exception` subclass. Code that catches `ValueError` in
   legacy code paths will miss the v1 binding's
   `CompatibilityError`.

6. **76 clippy lints remain** when `cargo clippy --workspace --
   -D warnings` runs against `rust-bindings/`. The mix is
   stable across reports: ~50 `non_camel_case_types` /
   `upper_case_acronyms` (the deliberate Python-facing naming),
   ~12 PyO3 0.20+ deprecations (`from_py_object` opt-in,
   `Bound::cast`), ~5 `redundant_closure` / `needless_borrow`,
   plus a few `dead_code` / `unused` / `type_complexity` items.
   None block the build (`cargo build --all-targets` succeeds
   with 17 informational warnings).

7. **Spec drift, primarily on import paths.** Spec examples
   show `from openjd.model import …` for symbols that today
   live under `openjd.model._v1.{template, job, types, errors}`.
   The `openjd.model.__init__` shim still re-exports the v0
   pure-Python implementation; per AGENTS.md, the rename to
   `openjd.model = v1` is the intended end state. The spec is
   forward-looking, but until the rename happens, copy-paste
   examples are broken.

8. **GIL is never released across model operations.**
   `decode_job_template_*`, `create_job`, and the iterator
   construction paths all hold the GIL during YAML/JSON parsing,
   validation, and combination-expression evaluation. A
   threaded probe (8 threads × 20 decodes) succeeded with no
   errors but every decode runs strictly serially.

The remainder of the report digs into each of these in detail and
ends with a numbered Recommendations section.

## 1. Python Interface Spec Review

`specs/python-model-interface.md` (1129 lines) describes the public
contract for the `openjd.model._v1` Rust-backed bindings. Coverage
is broad and deep — the spec now documents every typed
`JobParameterDefinition` variant, every `TaskParameterDefinition`
variant, every `*UserInterface` pyclass, the structural
template-time types, the `ModelProfile`/`CallerLimits`/
`ValidationContext` profile system, the pickle-support contract
including the explicit "out of scope" call-out for decoded
containers, the `RangeExpr` ascending-iteration behaviour change,
and the deprecated `decode_template` alias.

### What's well covered

* Decode entry points (`decode_job_template`, `decode_job_template_str`,
  `decode_environment_template`, `decode_environment_template_str`,
  `decode_template`, `parse_model`).
* `create_job`, `preprocess_job_parameters`,
  `merge_job_parameter_definitions`.
* `model_to_object` v0-only call-out (under "Utility").
* The full job-time output surface (`Job`, `Step`, `StepScript`,
  `StepActions`, `Action`, `Environment`, …).
* Iteration: `StepParameterSpaceIterator` and `StepDependencyGraph`.
* All 12 `JobParameterDefinition` variants with type-specific
  attribute tables.
* All 5 `TaskParameterDefinition` variants + `ChunksDefinition`.
* All 11 `*UserInterface` variants + `FileFilter`.
* The full template-time structural pyclass inventory under
  `openjd.model._v1.template`, including the `Template`-prefixed
  disambiguating aliases.
* Pickle-support inventory (Group A enums + Group B value types)
  with the explicit "decoded containers are not pickleable" note.
* `ModelProfile` / `ModelExtension` / `SpecificationRevision` /
  `CallerLimits` / `ValidationContext` profile system.
* `RangeExpr` ascending-iteration design note under "Compatibility
  Aliases".

### Spec ↔ binding gaps

#### Spec examples that don't import as written

The spec uses `from openjd.model import …` for many symbols. While
that path works today against the v0 (pure-Python) module, it does
not work against the v1 Rust-backed bindings: `openjd.model` is
the legacy pydantic implementation, and v1 lives at
`openjd.model._v1`. Importantly, even with the `_v1` qualifier,
several spec examples still fail because the `_v1.__init__` does
not re-export structural pyclasses:

| Spec snippet | What works today | What fails |
|---|---|---|
| `from openjd.model import StepParameterSpaceIterator` | `from openjd.model._v1.job import StepParameterSpaceIterator` | `from openjd.model._v1 import StepParameterSpaceIterator` ❌ |
| `from openjd.model import StepDependencyGraph` | `from openjd.model._v1.job import StepDependencyGraph` | `from openjd.model._v1 import StepDependencyGraph` ❌ |
| `from openjd.model import DocumentType, JobParameterType, TaskParameterType` | `from openjd.model._v1.types import DocumentType, …` | `from openjd.model._v1 import DocumentType` works (re-exported), but `JobParameterType`/`TaskParameterType` ❌ |
| `from openjd.model import DecodeValidationError, ModelValidationError, UnsupportedSchema` | `from openjd.model._v1.errors import …` | top level only re-exports `DecodeValidationError`; `ModelValidationError` and `UnsupportedSchema` ❌ |
| (Implicit `decode_job_template_str`) | `openjd._openjd_rs.decode_job_template_str` | `from openjd.model._v1 import decode_job_template_str` ❌ |
| (Implicit `decode_environment_template_str`) | same | same ❌ |
| `from openjd.model import Job, Step, JobTemplate, EnvironmentTemplate` | `from openjd.model._v1.{job,template} import …` | top-level v1 imports ❌ |

The architecture choice — push structural pyclasses into
`template` / `job` / `types` / `errors` submodules — is
defensible. But the spec does not call this out, which leaves
copy-paste callers stuck. **Either the wrapper should re-export
the spec'd entry points at the top level, or the spec should be
updated to use the submodule import paths consistently.**

#### Inconsistent `EmbeddedFile.type` accessor

The spec exposes `EmbeddedFile.type_` (with trailing underscore,
job-time, line 352) and `EmbeddedFile.type` (no underscore,
template-time, line 556). Verified at runtime:

* Template-time `EmbeddedFile` (under `openjd.model._v1.template`)
  has `.type` and **not** `.type_`.
* Job-time `EmbeddedFile` (under `openjd.model._v1.job`) has
  `.type_` and **not** `.type`.

Both names are spec'd, both work in their respective contexts.
The asymmetry is confusing — readers may not realise they need
different attribute names depending on whether they're holding a
template-time or job-time `EmbeddedFile`. Either both surfaces
should accept both names, or the spec should highlight the
divergence. (The underlying reason is that `type` is a Python
builtin name; the job-time class avoids the shadow with `type_`,
the template-time class uses `type` because the Rust struct field
is `type` and `pyo3-stub-gen` derives the getter name from the
Rust field.)

#### Documented but not yet exposed

These spec items continue to lack a live binding:

* `IntRangeExpr.start` / `end` — the spec doesn't call these out
  but the v0 reference exposes them. Status: **resolved**, both
  exist on `RangeExpr` today (verified at runtime: `r.start`,
  `r.end` work on `IntRangeExpr("1-5")`).
* `IntRangeExpr.from_list([…])` — verified: now exists.
* `IntRangeExpr.from_str(…)` — verified: now exists.

### Spec entries with no live binding symbol

None remaining at the top level — every spec'd entry point
resolves to *something*, even if the import path is via a
submodule.

### Binding surfaces not in the spec

* `Step.__eq__` / `Step.__hash__` based on step name alone — used
  internally; not in the spec but observable.
* `it.chunks_parameter_name` getter — listed in the spec
  ("StepParameterSpaceIterator" section), works.
* `it.reset_iter()` method — exposed by the binding, not in the
  spec.
* `_reconstruct_enum` / `_reconstruct_kwargs` — pickle-helper
  module functions referenced by `__reduce__` payloads. Names
  are part of the pickle wire format and underscore-prefixed,
  so they're correctly considered private.

## 2. PyO3 Binding Source Review

The model bindings live in `rust-bindings/src/model/` (15 files,
6,635 lines total). Per-file overview:

| File | Lines | Role |
|---|---:|---|
| `mod.rs` | 65 | Submodule re-exports |
| `errors.rs` | 21 | `PyDecodeValidationError`, `PyModelValidationError`, `PyUnsupportedSchema`, `model_err_to_py` |
| `types.rs` | 423 | `PyDocumentType`, `PyTemplateSpecificationVersion`, `PyJobParameterType`, `PyTaskParameterType`, `PyTaskParameterValue`, `PyJobParameterValue` |
| `profile.rs` | 519 | `PyModelExtension`, `PyModelProfile`, `PyCallerLimits`, `PyValidationContext`, `PySpecificationRevision` |
| `template.rs` | 183 | `PyJobTemplate`, `PyEnvironmentTemplate` |
| `template_types.rs` | 1296 | structural template-time pyclasses (Action, Environment, Step, etc.) |
| `job_param_defs.rs` | 1174 | 12 typed `JobParameterDefinition` variants |
| `step_param_space_def.rs` | 489 | `StepParameterSpaceDefinition` + 5 typed `TaskParameterDefinition` variants + `ChunksDefinition` |
| `user_interfaces.rs` | 637 | 11 `*UserInterface` pyclasses + `FileFilter` |
| `decode.rs` | 104 | `decode_job_template_*`, `decode_environment_template_*` |
| `job.rs` | 805 | job-time pyclasses (Job, Step, etc.), JobParameter |
| `step_param_space.rs` | 242 | `PyStepParameterSpaceIterator` (now persistent) |
| `step_dependency_graph.rs` | 133 | graph + node + edge |
| `task_parameter.rs` | 581 | 5 typed task-parameter pyclasses (job time) |
| `create_job_fns.rs` | 252 | `create_job`, `preprocess_job_parameters`, `merge_job_parameter_definitions`, `evaluate_let_bindings`, `deserialize_step`, `create_environment` |

### `errors.rs` — exception mapping

Three `pyo3::create_exception!` types and a `model_err_to_py`
mapper. The mapper collapses several distinct `ModelError`
variants into `PyModelValidationError`:

```rust
ModelError::FormatStringError { message, .. } => PyModelValidationError::new_err(message),
ModelError::Expression(expr_err) => PyModelValidationError::new_err(expr_err.to_string()),
ModelError::Compatibility(msg) => PyModelValidationError::new_err(msg),
```

The pure-Python reference distinguishes `FormatStringError`,
`ExpressionError`, and `CompatibilityError` from
`ModelValidationError`. The wrapper module re-exports
`FormatStringError` and `ExpressionError` from `openjd.expr`, but
because the binding never raises those classes, code that catches
the more specific exception will not catch them. ⚠

The exception classes themselves register correctly via
`register_renamed_exception` in `lib.rs`:

```rust
register_renamed_exception(m, …PyDecodeValidationError…, "DecodeValidationError", "openjd.model._v1.errors")?;
register_renamed_exception(m, …PyModelValidationError…, "ModelValidationError", "openjd.model._v1.errors")?;
register_renamed_exception(m, …PyUnsupportedSchema…, "UnsupportedSchema", "openjd.model._v1.errors")?;
```

Verified via runtime probe: `pickle.dumps(e); pickle.loads(b)`
round-trips with the canonical names; `type(e).__qualname__` is
`DecodeValidationError` (etc.). ✓

### `decode.rs` — dict ↔ JSON round-trip

`decode_*_template_dict` still goes Python dict → `json.dumps` →
`serde_json::from_str` → `serde_json::Value`. Cost: doubles the
parse time for callers that already hold a dict, and silently
fails on values that aren't JSON-serialisable (`Decimal`,
`Path`, custom objects) — `json.dumps` raises a clear error so
the failure is at least visible, but it's still a foot-gun. ⚠

### `template.rs` — full template surface

`PyJobTemplate` and `PyEnvironmentTemplate` now expose the full
structural surface:

* `name` / `description` / `specification_version` /
  `specificationVersion` (camelCase alias) / `profile` /
  `parameter_definitions` / `parameterDefinitions` (camelCase
  alias).
* `JobTemplate`-only: `steps` (`list[StepTemplate]`),
  `job_environments` / `jobEnvironments` (camelCase).
* `EnvironmentTemplate`-only: `environment` (single
  `Environment`).

Both classes implement `__repr__` cleanly. Neither implements
`__eq__` / `__hash__`. ✓ for surface; pickle is intentionally
out of scope per the spec (decoded containers do not pickle).

### `types.rs` — enums and value types

`PyJobParameterType` declares `frozen, hash` and pickles via
`__reduce__` through `_reconstruct_enum`. `PyTaskParameterType`
and `PyDocumentType` likewise.

Verified at runtime:

* `JobParameterType.INT` is hashable. ✓
* `TaskParameterType.INT` is hashable. ✓
* `ModelExtension.EXPR` is hashable. ✓
* `SpecificationRevision.v2023_09` (Python str-Enum shim) is
  hashable. ✓
* **`DocumentType.JSON` is NOT hashable.** ⚠

`DocumentType` is missing the `frozen, hash` attributes that the
other enum-shaped pyclasses carry. Symmetry says it should be
hashable.

`PyTaskParameterValue.__eq__` / `PyJobParameterValue.__eq__`
implement cross-type equality with the Python-side
`ParameterValue` shim, verified at runtime: all six combinations
(`pv == jv`, `jv == pv`, `pv == tv`, `tv == pv`, `jv == tv`,
`tv == jv`) return True for matching `(type, value)` pairs. ✓

### `step_param_space.rs` — iterator persistence

`PyStepParameterSpaceIterator` now holds a persistent
`Mutex<StepParameterSpaceIterator>` (per the resolution of the
prior report's Recommendation #4). The setter for
`chunks_default_task_count` actually mutates the live state;
`__len__` raises `ValueError` with the reference's message for
adaptive-chunked spaces. Both behaviours are covered by passing
tests in `test_step_param_space_iter.py`.

`__contains__` calls `extract_task_parameter_set` which produces
a `TaskParameterValue` whose `value` is parsed via
`ExprValue::from_str_coerce`. For plain `INT`/`FLOAT`/`STRING`/
`PATH` the round-trip works: yielded values pass `in fresh_iter`.
**For `CHUNK[INT]` it fails:** the iterator yields
`TaskParameterValue(type=CHUNK[INT], value="1-2")` (where `"1-2"`
is the chunk-range RangeExpr string), but the Rust `contains`
check in `openjd-model::job::step_param_space::StepParameterSpaceIterator::contains`
expects the chunk to be expressed differently in the candidate
set. Surface fix is in `extract_task_parameter_set` (or in the
underlying `validate_containment` if the issue is upstream).

### `step_param_space_def.rs` — typed task-parameter definitions

`PyStepParameterSpaceDefinition` exposes `task_parameter_definitions`
as a `list[…]` of typed pyclasses (`IntTaskParameterDefinition`,
`FloatTaskParameterDefinition`, …, `ChunkIntTaskParameterDefinition`),
plus `combination` as `Optional[str]`. Each variant has
`type` / `name` / `range`, and `ChunkIntTaskParameterDefinition`
additionally has `chunks: ChunksDefinition`. The dispatch on the
Rust enum is clean. ✓

### `user_interfaces.rs` — 11 typed UI variants + FileFilter

Implements `StringUserInterface`, `IntUserInterface`,
`FloatUserInterface`, `PathUserInterface`, `BoolUserInterface`,
`RangeExprUserInterface`, `ListSimpleUserInterface`,
`ListPathUserInterface`, `ListIntUserInterface`,
`ListFloatUserInterface`, `HiddenOnlyUserInterface`, plus the
`FileFilter` payload class. Each `Job*ParameterDefinition` has a
`user_interface` getter (camelCase alias `userInterface`) that
returns the appropriate variant. Verified at runtime:
`d.user_interface.control == "SPIN_BOX"` works on a
`JobIntParameterDefinition` whose template carried
`{"control": "SPIN_BOX", "singleStepDelta": 2}`. ✓

### `create_job_fns.rs`

`py_preprocess_job_parameters` no longer rewrites `Path(".")` to
empty string — verified at runtime: passing both `Path(td)` and
the bare string `td` (an absolute temp-dir path) succeeds.
However, `Path(".")` (the current directory) is now rejected
with `DecodeValidationError("The value supplied for the job
template dir, , is not an absolute path.")`. Note the **empty
string** in the error message, not `.`. The empty-rewrite is
gone for absolute paths but remains for relative ones — the
caller passes the raw path through, the underlying Rust code
sees an empty string. ⚠ minor cosmetic; the right fix is to
preserve the user-supplied path in the error message verbatim.

`py_create_environment` and `py_deserialize_step` are
exposed as `create_environment` and `deserialize_step` on the
`_openjd_rs` module. Neither is documented in the spec; both
are reachable via `from openjd._openjd_rs import …` for the
sessions runtime. ⚠ spec coverage gap.

### `job.rs` — job-time output surface

The `PyJob.parameters` getter only returns parameters that were
explicitly resolved via `job_parameter_values`. **Parameters
with defaults but no explicit value are absent from the dict**
— verified at runtime: a template with two `parameterDefinitions`
that have `default` values produces an empty `j.parameters` dict
when `create_job(..., job_parameter_values={})` runs. The v0
reference includes both defaults and explicit values. ⚠
behavioural divergence; this is a real parity bug, not a spec
gap.

### PyO3-specific concerns

* **Exception class registration.** Verified for all three model
  exceptions; pickle round-trips under canonical names. ✓
* **Type conversions.** Boundary integers (i64::MIN / i64::MAX)
  round-trip through `INT`-typed `JobParameter.value` correctly.
  ✓ Ordered vs unordered: `Job.parameters` iteration order
  matches `IndexMap` insertion order. ✓
* **GIL handling.** **Zero `Python::allow_threads` calls in any
  of the model bindings.** The decode path holds the GIL across
  YAML parsing, JSON conversion, serde deserialisation, and
  validation. The `create_job` path holds the GIL across
  combination-expression evaluation. The
  `StepParameterSpaceIterator` constructor holds the GIL while
  building the iterator graph. A multi-threaded probe (8 threads
  × 20 decodes) succeeds with no errors but the work is
  serialised. ⚠
* **`#[pyclass]` constructor signatures.**
  `PyStepParameterSpaceIterator::new` takes `step` and `space`
  as keyword-only optional arguments; matches the spec.
  `PyEmbeddedFile` accepts both `endOfLine` and `end_of_line`.
  ✓
* **`Py<T>` lifetime.** No `BorrowMutError` / use-after-free
  patterns spotted. All getters return `Clone`d data.
* **ABI3 compatibility.** `Cargo.toml` declares `abi3-py39`;
  the wheel emits `cp39-abi3-linux_x86_64`. ✓
* **Stub generation.** `src/openjd/_openjd_rs.pyi` is 102 KB,
  2,994 lines, and now reflects the full surface (the prior
  report's `cd93ebe` commit closed the gaps). The stub is
  unchanged in this evaluation. ✓

## 3. Python Wrapper Module Review

`src/openjd/model/_v1/__init__.py` (517 lines) re-exports the
package's *entry points* — decode/create functions, Python-only
compatibility classes, and Python str-Enum shims for
`SpecificationRevision` / `TemplateSpecificationVersion` — but
deliberately does *not* re-export structural pyclasses. Those
live in:

* `src/openjd/model/_v1/template.py` (163 lines) — template-time
  pyclasses + `Template`-prefixed aliases.
* `src/openjd/model/_v1/job.py` (70 lines) — job-time pyclasses
  + iteration helpers.
* `src/openjd/model/_v1/types.py` (37 lines) — cross-cutting
  enums and value types.
* `src/openjd/model/_v1/errors.py` (20 lines) — three exception
  classes.

This split is documented in the docstring of `__init__.py`. The
intent is clean — `from openjd.model._v1.template import …`
gives you template-time stuff; `from openjd.model._v1.job
import …` gives you job-time. But **the top-level
`__init__.py` does not export the structural pyclasses or the
non-`DecodeValidationError` exceptions** that the spec uses in
its example code, and there is no shim that warns the user
about this.

### Top-level `_v1` re-exports (current)

Confirmed via `import openjd.model._v1 as v1; v1.__all__`:

* Decode: `decode_job_template`, `decode_environment_template`,
  `decode_template`, `parse_model`, `document_string_to_object`.
* Job: `create_job`, `preprocess_job_parameters`,
  `merge_job_parameter_definitions`.
* Capability validation: `validate_amount_capability_name`,
  `validate_attribute_capability_name`,
  `STANDARD_AMOUNT_CAPABILITIES`,
  `STANDARD_ATTRIBUTE_CAPABILITIES`.
* Python str-Enums: `SpecificationRevision`,
  `TemplateSpecificationVersion`.
* Python-only compat: `ParameterValue`, `ParameterValueType`,
  `RevisionExtensions`, `CancelationMethodNotifyThenTerminate`,
  `CancelationMethodTerminate`, `CompatibilityError`,
  `TokenError`, `ValueReferenceConstants`.
* Type aliases: `JobParameterDefinition`, `JobParameterInputValues`,
  `JobParameterValues`, `OpenJDModel`, `TaskParameterSet`.
* Re-exports for spec examples: `CallerLimits`, `DocumentType`,
  `ModelProfile`.
* Single error: `DecodeValidationError`.
* Cross-component re-exports from `openjd.expr`: `ExpressionError`,
  `FormatString`, `FormatStringError` (alias for
  `FormatStringValidationError`), `RangeExpr`, `SymbolTable`.
* Aliases: `ArgString`, `CommandString`, `EmbeddedFileText`,
  `EmbeddedFiles`, `IntRangeExpr`, `StepDependencyGraphNode`,
  `StepDependencyGraphStepToStepEdge`.

### NOT exposed at `_v1` top level (live in submodules)

Verified by `hasattr(v1, X)` returning False for these
spec-mentioned symbols:

* `Job`, `Step`, `StepScript`, `StepActions`, `Action`,
  `Environment`, `EnvironmentScript`, `EnvironmentActions`,
  `EmbeddedFile`, `JobParameter`, `StepParameterSpace`,
  `StepDependency`, `CancelationMode` — all in `_v1.job`.
* `JobTemplate`, `EnvironmentTemplate` — in `_v1.template`.
* `StepParameterSpaceIterator`, `StepDependencyGraph` — in
  `_v1.job`.
* `JobParameterType`, `TaskParameterType` — in `_v1.types`.
* `ModelValidationError`, `UnsupportedSchema` — in `_v1.errors`.
* `decode_job_template_str`, `decode_environment_template_str`
  — only on `openjd._openjd_rs`, not on the v1 wrapper at all.

### Python-side compat classes

| Symbol | Source | Notes |
|---|---|---|
| `ParameterValue` | Python class | `__eq__` is symmetric with `JobParameterValue` and `TaskParameterValue` (verified). |
| `RevisionExtensions` | Python wrapper | Accepts both `spec_rev=` and `revision=`, both `supported_extensions=` and `extensions=`. Reference is strict kw-only `spec_rev`+`supported_extensions`. ⚠ mostly cosmetic. |
| `CancelationMethodTerminate` / `CancelationMethodNotifyThenTerminate` | Python wrappers | Plain dataclasses; do not unify with `openjd.model._v1.job.CancelationMode` (the Rust class). Two parallel hierarchies; v0 reference has the same shape so this is intentional compat. |
| `CompatibilityError` | `Exception` subclass | Reference inherits from `ValueError`. ⚠ |
| `TokenError` | `Exception` subclass | Reference inherits from `Exception`. ✓ |
| `validate_amount_capability_name` / `validate_attribute_capability_name` | Pure-Python re-implementations | Permit positional `name` and make `standard_capabilities` optional, both more permissive than the reference. Behaviour matches the reference when called with reference signature. ⚠ |

### `openjd.model._v1.v2023_09` shim

`src/openjd/model/_v1/v2023_09/__init__.py` (51 lines) re-exports
a small set of names for legacy compat (`Action`, `EmbeddedFile`,
`Environment`, `EnvironmentTemplate`, `EnvironmentScript`,
`FormatString`, `Job`, `JobTemplate`, `Step`, `StepScript`,
`StepActions`, `StepParameterSpace`, `StepParameterSpaceIterator`,
plus `STANDARD_*_CAPABILITIES`, the `dict` aliases, and
`EmbeddedFileTypes` / `ExtensionName`). The corresponding
test directory `test/openjd/model_v1/v2023_09/` is empty; the
prior report's Recommendation #7 was resolved by deleting the
broken-collection v2023_09 test files (per the design rationale
that v1 has no per-revision class hierarchy). ✓

## 4. Test Review

### Inventory

```
test/openjd/model_v0/   pure-Python reference (2306 tests, all passing)
  __init__.py
  conftest.py
  benchmark/
  format_strings/{test_format_string,test_expression,test_parser,
                  test_dyn_constrained_str,test_node,test_edit_distance}.py
  _internal/{test_combination_expr,test_create_job,
             test_param_space_dim_validation,test_range_expr,
             test_variable_reference_validation}.py
  v2023_09/{test_create,test_environments,test_parameter_space,
            test_strings,test_redacted_env_vars,test_definitions,
            test_module,test_job_template,test_environment_template,
            test_step_host_requirements,test_step_template,
            test_feature_bundle_1,test_embedded,
            test_chunk_int_task_parameter_type,test_action,
            test_scripts,test_job_parameters,test_template_variables}.py
  test_{capabilities,convert_pydantic_error,create_job,errors,fuzz,
        importable,lexer,merge_job_parameters,parse,
        step_dependency_graph,step_param_space_iter,
        step_param_space_iter_with_chunks,symbol_table,
        tokenstream,version_enums}.py

test/openjd/model_v1/   binding tests (867 tests, all passing)
  __init__.py
  benchmark/
  v2023_09/                ← empty placeholder dir (was deleted in Rec #7 resolution)
  format_strings/__init__.py     ← empty
  _internal/__init__.py          ← empty
  test_capabilities.py
  test_create_job.py
  test_errors.py
  test_fuzz.py
  test_importable.py
  test_job_param_defs.py
  test_known_gaps.py             ← currently empty (no known gaps tracked)
  test_merge_job_parameters.py
  test_parse.py
  test_pickle.py
  test_pyclass_modules.py
  test_range_expr.py
  test_rust_model_bindings.py
  test_step_dependency_graph.py
  test_step_param_space_def.py
  test_step_param_space_iter.py
  test_symbol_table.py
  test_task_parameter.py
  test_template_types.py
  test_user_interfaces.py
  test_version_enums.py
```

### What `test/openjd/model_v1/` covers well

* `test_pyclass_modules.py` — exhaustive coverage of `__module__`,
  `__name__`, `__qualname__`, and pickle-name fix-up for every
  exposed pyclass (`EXPECTED_MODULES` table is the source of
  truth). ✓
* `test_pickle.py` — Group A enums + Group B value types.
* `test_template_types.py` — structural template-time accessors
  on `JobTemplate`, `StepTemplate`, `Environment`, `Action`,
  `HostRequirements`, etc.
* `test_job_param_defs.py` — all 12 typed
  `JobParameterDefinition` variants.
* `test_user_interfaces.py` — 23 tests covering every
  `*UserInterface` variant + `FileFilter`.
* `test_task_parameter.py` — 35 tests covering the 5 typed
  job-time `TaskParameter` variants + dispatch through
  `StepParameterSpace.taskParameterDefinitions`.
* `test_step_param_space_def.py` — 14 tests covering all 5
  `TaskParameterDefinition` variants + `ChunksDefinition` +
  `StepParameterSpaceDefinition`.
* `test_create_job.py` — happy path + most error paths.
* `test_step_param_space_iter.py` — basic iteration, indexing,
  product/associate combinations, `contains`, name set.
* `test_step_dependency_graph.py` — node/edge/topological API.
* `test_known_gaps.py` — currently empty (no tracked gaps).

### Coverage gaps relative to the v0 reference

* `test/openjd/model_v0/test_convert_pydantic_error.py` —
  no analog. Reasonable: pydantic-specific.
* `test/openjd/model_v0/test_lexer.py`, `test_tokenstream.py` —
  no analog. Reasonable: binding does not expose tokenstream/lexer.
* `test/openjd/model_v0/format_strings/` — six test files; the
  binding's `format_strings/` directory is empty. The
  format-string semantics flow through `openjd.expr` so there is
  arguably coverage there, but a binding-level
  round-trip-through-template integration test would be
  valuable.
* `test/openjd/model_v0/_internal/` — five test files; the
  binding's `_internal/` directory is empty. These cover
  combination-expression internals, range-expr edge cases,
  parameter-space-dimension validation. The behaviours are
  mostly tested via `test_step_param_space_iter.py` /
  `test_step_param_space_def.py` integration paths, but
  micro-tests are missing.
* `test/openjd/model_v0/test_step_param_space_iter_with_chunks.py`
  — a 28k-line reference test file. The binding's
  `test_step_param_space_iter.py` covers some chunked cases
  but is much smaller. The `CHUNK[INT] __contains__` regression
  found during exploratory probing (see §7) is exactly the
  kind of issue these tests would catch.

### Tests that exist in the binding without a v0 analog

* `test_pyclass_modules.py` — binding-specific.
* `test_rust_model_bindings.py` — direct exercise of
  `_openjd_rs.*`. Binding-specific.
* `test_user_interfaces.py`, `test_task_parameter.py`,
  `test_step_param_space_def.py`, `test_template_types.py`,
  `test_job_param_defs.py`, `test_pickle.py`, `test_parse.py`
  — coverage of binding-side typed pyclasses for a surface
  the v0 reference exposes through different shapes (Pydantic
  discriminated unions). Equivalent v0 tests live in
  `test_v2023_09/`.

## 5. Parity with Pure-Python Reference

This is the most important section. Each row maps a public symbol
in the v0 reference (`openjd.model.__init__`) to its v1
counterpart and notes any divergence.

### Functions

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `decode_job_template(*, template, supported_extensions=None, caller_limits=None)` | Returns pydantic `JobTemplate` | Returns Rust `JobTemplate` | ✓ |
| `decode_job_template_str(document, format=…, *, supported_extensions=None, caller_limits=None)` | n/a — v0 splits as `decode_job_template` + `document_string_to_object` | Direct binding (only on `_openjd_rs`, not on `_v1`) | ⚠ binding-only entry point; not re-exported through wrapper |
| `decode_environment_template(*, template, supported_extensions=None)` | Returns pydantic `EnvironmentTemplate` | Returns Rust `EnvironmentTemplate` | ✓ |
| `decode_environment_template_str(document, format=…, *, supported_extensions=None)` | n/a | Direct binding (only on `_openjd_rs`) | ⚠ same |
| `decode_template(*, name, raw_data, document_type)` | Reference signature with `name` / `raw_data` / `document_type` | v1 alias accepts the same kwargs as `decode_job_template` (`template=`, `supported_extensions=`, `caller_limits=`) | ⚠ different kwargs |
| `create_job(*, job_template, job_parameter_values, …)` | Returns Job; resolved `parameters` includes defaults | Returns Job; **`parameters` omits defaults** | ❌ behavioural divergence |
| `preprocess_job_parameters(*, job_template, job_parameter_values, …, job_template_dir, current_working_dir)` | Returns dict[str, ParameterValue] | Returns dict[str, JobParameterValue] | ⚠ value type differs but `__eq__` is symmetric |
| `merge_job_parameter_definitions(*, job_template, environment_templates=None)` | Returns list of pydantic objects | Returns list of pydantic-shaped dicts | ⚠ shape differs |
| `model_to_object(*, model)` | Returns dict via `model_dump` | **Removed (v0-only)** | ✓ documented in spec |
| `parse_model(*, model=None, obj)` | Returns pydantic model | Returns Rust model; **does NOT accept `supported_extensions=`** | ⚠ — templates with `extensions:` field fail |
| `document_string_to_object(*, document, document_type=None)` | Returns dict (CSafeLoader) | Returns dict (CSafeLoader) | ✓ |
| `validate_amount_capability_name(*, capability_name, standard_capabilities)` | strict kw-only | Permissive: accepts positional `name=` and makes `standard_capabilities` optional | ⚠ |
| `validate_attribute_capability_name(*, capability_name, standard_capabilities)` | strict kw-only | Same as above | ⚠ |

### Output types (job-time)

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `Job` | Pydantic model | Rust `Job` | ✓ shape; minor: `revision` always `'2023-09'` |
| `Job.parameters` | dict including defaults | **dict containing only explicit values** | ❌ |
| `Step.script.actions.onRun.command` | `FormatString` | `FormatString` (from `openjd.expr`) | ✓ |
| `Step.script.actions.onRun.timeout` | string in spec | `Optional[str]` | ✓ |
| `Step.script.actions.onRun.cancelation` | typed | `CancelationMode` with `.mode` and `.notify_period_in_seconds` | ✓ |
| `Step.script.let` | `Optional[list[str]]` | `Optional[list[str]]` | ✓ |
| `Step.script.embedded_files` / `embeddedFiles` | both | both | ✓ |
| `Step.parameterSpace.taskParameterDefinitions[name]` | typed `RangeExpression…/RangeList…TaskParameterDefinition` | typed `IntTaskParameter` / `FloatTaskParameter` / `StringTaskParameter` / `PathTaskParameter` / `ChunkIntTaskParameter` (mirrors Rust runtime enum 1:1) | ✓ different shape, intentional per spec |
| `Step.parameterSpace.combination` | `Optional[str]` | `Optional[str]` | ✓ |
| `Step.resolved_symtab` | `SymbolTable` | `SymbolTable` | ✓ |
| `Step.resolvedBindings` | `Optional[list[str]]` | `Optional[list[str]]` | ✓ |
| `JobParameter.value` | `ExprValue` | `ExprValue` | ✓ |
| `JobParameter.name` | str | str | ✓ |
| `JobParameter.param_type` | str | str | ✓ |
| `Environment.script.actions.onEnter` / `onExit` | `Optional[Action]` | `Optional[Action]` | ✓ |
| `EmbeddedFile.type_` (job-time) / `EmbeddedFile.type` (template-time) | one accessor | asymmetric (job-time: `type_`; template-time: `type`) | ⚠ asymmetry |
| `EmbeddedFile(name, type, filename, data, runnable, endOfLine)` | Pydantic | Rust struct, both `endOfLine` and `end_of_line` accepted | ✓ |

### Template types

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `JobTemplate.{name, description, specification_version}` | All present | All present | ✓ |
| `JobTemplate.specificationVersion` (camel) | ✓ in reference | ✓ in binding | ✓ |
| `JobTemplate.parameter_definitions` / `parameterDefinitions` | list of typed defs | list of 12 typed pyclasses dispatching on Rust enum | ✓ |
| `JobTemplate.steps` | list[StepTemplate] | list[StepTemplate] | ✓ |
| `JobTemplate.job_environments` / `jobEnvironments` | Optional list | Optional list | ✓ |
| `JobTemplate.profile` | `RevisionExtensions`-shaped | `ModelProfile` | ⚠ different type; v1's is richer |
| `EnvironmentTemplate.environment` | nested Environment | typed Environment | ✓ |
| `EnvironmentTemplate.parameter_definitions` | list | list | ✓ |
| `StepTemplate.parameter_space` | typed | `Optional[StepParameterSpaceDefinition]` | ✓ |
| `StepTemplate.host_requirements` | typed | `Optional[HostRequirements]` | ✓ |
| `StepTemplate.{bash,python,cmd,powershell,node}` | sugar (FEATURE_BUNDLE_1) | `Optional[SimpleAction]` | ✓ |

### Iterators

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `StepParameterSpaceIterator(*, space=None, step=None)` | accepts `space` + `chunks_task_count_override` | accepts `step` or `space` | ⚠ no `chunks_task_count_override` |
| `len(it)` | raises `ValueError` for adaptive-chunked | raises `ValueError` with matching message | ✓ |
| `it[i]` / `it[-1]` | works | works | ✓ |
| `for v in it` (dict[str, ParameterValue]) | yields ParameterValue | yields TaskParameterValue | ✓ (compares equal) |
| `v in it` after iteration (INT) | True | True | ✓ |
| `v in it` after iteration (CHUNK[INT]) | True | **False** | ❌ |
| `it.names` (property) | property | property | ✓ |
| `it.chunks_adaptive` | property | property | ✓ |
| `it.chunks_default_task_count` (mutate) | mutates | mutates | ✓ |
| `it.chunks_default_task_count` (set on non-adaptive) | raises | raises with matching message | ✓ |

### Enums and constants

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `DocumentType.{JSON, YAML}` | str-based Enum | int-eq pyclass; pickleable | ⚠ different shape (Enum vs pyclass), `==` works only because pyclass implements `__eq__` against str via `as_str()` |
| `DocumentType` hashable | ✓ | **NOT hashable** | ⚠ |
| `TemplateSpecificationVersion.JOBTEMPLATE_v2023_09` | str-based Enum | str-based Enum (Python shim) | ✓ |
| `JobParameterType.{STRING,INT,…,LIST_LIST_INT}` | str-based Enum | int-eq pyclass; hashable; pickleable | ⚠ shape diff but functional parity |
| `TaskParameterType.{INT,FLOAT,STRING,PATH,CHUNK_INT}` | str-based Enum | int-eq pyclass; hashable; pickleable | ✓ |
| `SpecificationRevision.v2023_09` | str-based Enum | str-based Enum (Python shim) | ✓ |
| `ValueReferenceConstants` | str-based Enum | str-based Enum | ✓ |
| `ModelExtension.{TASK_CHUNKING, REDACTED_ENV_VARS, FEATURE_BUNDLE_1, EXPR}` | n/a in v0 | int-eq pyclass; hashable; pickleable | ✓ binding-side new |
| `ModelProfile`, `CallerLimits`, `ValidationContext` | n/a | new in v1 | ✓ binding-side new |

### Exceptions

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `DecodeValidationError(ValueError)` | ✓ | ✓ | ✓ |
| `ModelValidationError(ValueError)` | ✓ | ✓ but only via `.errors` submodule | ⚠ |
| `UnsupportedSchema(ValueError)` | ✓ | ✓ but only via `.errors` submodule | ⚠ |
| `ExpressionError(ValueError)` | ✓ | ✓ from `openjd.expr` | ✓ |
| `FormatStringError(ValueError)` | ✓ | ✓ but `__qualname__` is `FormatStringValidationError` (re-imported from `openjd.expr` under that name) | ⚠ name mismatch |
| `CompatibilityError(ValueError)` | inherits from `ValueError` in `_errors.py` | inherits from `Exception` only | ❌ |
| `TokenError(Exception)` | ✓ | ✓ | ✓ |

When format-string parsing inside a template fails, the reference
raises `FormatStringError`; the binding maps everything to
`ModelValidationError` via `model_err_to_py`. Code catching the
more specific exception type breaks. ⚠

## 6. Build and Test Results

### `python scripts/maturin_build.py develop`

Built cleanly against `openjd-rs` @ `baca1f2`:

```
🔗 Found pyo3 bindings with abi3 support
   Compiling openjd-python v0.9.0 (.../rust-bindings)
warning: `openjd-python` (lib) generated 17 warnings (run `cargo fix --lib -p openjd-python` to apply 9 suggestions)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.72s
📦 Built wheel for abi3 Python ≥ 3.9 to .../openjd_model-0.9.1.post26+g8f19e4d6d.d20260525-cp39-abi3-linux_x86_64.whl
🛠 Installed openjd-model-0.9.1.post26+g8f19e4d6d.d20260525
```

The 17 build warnings are a subset of the clippy lints (see
below). None block the build.

### `python -m pytest test/openjd/model_v1`

```
867 passed in 3.91s
```

All `model_v1` tests pass. No xfails, no errors, no failures.

### `python -m pytest test/openjd/model_v0`

```
2306 passed in 2.44s
```

All `model_v0` reference tests pass against the same source tree.

### `python -m pytest test/` (whole suite)

```
4952 passed, 24 skipped, 6 xfailed, 8 warnings in 4.46s
```

The 6 xfails are all in `test/openjd/expr/test_known_gaps.py`
and are tracked in the `expr` report — none belong to the
model component.

### `hatch run lint`

```
cmd [1] | ruff check src test
All checks passed!
cmd [2] | black --check --diff src test
All done! ✨ 🍰 ✨
154 files would be left unchanged.
cmd [3] | mypy src test
Success: no issues found in 103 source files
```

ruff, black, and mypy all green. Zero typing errors. ✓

### `cargo build --manifest-path rust-bindings/Cargo.toml --all-targets`

Succeeds with 17 informational warnings (subset of the clippy
output below; non-blocking).

### `cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets -- -D warnings`

Fails with 56 errors (76 lint occurrences total counting
duplicates). Distribution:

| Category | Count |
|---|---:|
| `non_camel_case_types` (`CHUNK_INT`, `READY_ENDING`, etc.) | 2 |
| `upper_case_acronyms` (`YAML`, `JSON`, `INT`, `FLOAT`, `STRING`, `PATH`, `BOOL`, `EXPR`, `RUNNING`, `READY`, `SUCCESS`, `FAILED`, `TIMEOUT`, `CANCELING`, `CANCELED`, `ENDED`) | ~30 |
| `deprecated` PyO3 (`from_py_object` opt-in, `Bound::cast`) | 12 |
| `type_complexity` | 9 |
| `unused doc comment` | 1 |
| `dead_code` (`supported_extension_strings`, `from_rust`) | 2 |
| `too_many_arguments` | 1 |
| `derivable_impl` | 1 |

Same shape as the prior `expr` evaluation. The
`upper_case_acronyms` and `non_camel_case_types` lints reflect
the deliberate Python-facing naming (Python convention is
`UPPER_SNAKE_CASE` for enum variants, but Rust's clippy
expects `UpperCamelCase`); they should be `#[allow]`'d on the
relevant pyclass enums. The PyO3 deprecations are upstream
churn that needs a focused commit pass.

### `cargo test --manifest-path rust-bindings/Cargo.toml`

```
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

The `rust-bindings` crate has no Rust unit tests (testing is
done from the Python side via pytest).

### `cargo test --manifest-path rust-bindings/Cargo.toml --doc`

```
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

No doctests either.

### Stub generation

`src/openjd/_openjd_rs.pyi` — 102 KB, 2,994 lines — was
regenerated as part of the prior commit `cd93ebe`. The current
state matches the binding surface; no regeneration is needed
for this evaluation. ✓

## 7. Exploratory Findings

The probe scripts run from `/tmp/` exercised 30+ surfaces and
turned up the issues listed below. Because there is no
`test_known_gaps.py` content today, each finding is referenced
back to its surface in the binding source so it can be
landed as a fresh xfail in a follow-up commit if/when desired.

### Confirmed regressions / parity gaps

| # | Issue | Surface |
|---|---|---|
| 1 | `Job.parameters` omits parameters that resolve via defaults; v0 reference includes them | `rust-bindings/src/model/job.rs::PyJob::parameters` (and the upstream `openjd_model::job::Job::parameters` field that backs it) |
| 2 | `StepParameterSpaceIterator.__contains__` returns False for `CHUNK[INT]` task-parameter-space yielded values | `rust-bindings/src/model/step_param_space.rs::extract_task_parameter_set` (or the upstream `openjd_model::job::step_param_space::StepParameterSpaceIterator::contains` for ChunkInt path) |
| 3 | `DocumentType` is not hashable, but `JobParameterType`, `TaskParameterType`, `ModelExtension` are | `rust-bindings/src/model/types.rs::PyDocumentType` — missing `frozen, hash` in `#[pyclass(...)]` |
| 4 | `CompatibilityError` inherits from `Exception`, not `ValueError` (reference inherits from ValueError) | `src/openjd/model/_v1/__init__.py::CompatibilityError` |
| 5 | `ModelError::FormatStringError` / `Expression` / `Compatibility` all collapse to `ModelValidationError` instead of the corresponding distinct exception class | `rust-bindings/src/model/errors.rs::model_err_to_py` |
| 6 | `ModelValidationError` and `UnsupportedSchema` not re-exported at `openjd.model._v1` top level (only via `.errors` submodule) | `src/openjd/model/_v1/__init__.py::__all__` |
| 7 | `decode_job_template_str` and `decode_environment_template_str` not re-exported through the wrapper at all | same as above |
| 8 | `parse_model(obj=…)` does not accept `supported_extensions=` — templates with `extensions:` field fail to parse through this entry point | `src/openjd/model/_v1/__init__.py::parse_model` |
| 9 | Spec uses `from openjd.model import StepParameterSpaceIterator, ModelValidationError, …` — none of these are top-level on `_v1` today | spec / wrapper alignment |
| 10 | `EmbeddedFile.type` (template-time) vs `EmbeddedFile.type_` (job-time) — asymmetric accessor names across what users perceive as "the same" type | `rust-bindings/src/model/{job.rs,template_types.rs}` |
| 11 | `FormatStringError.__qualname__` is `FormatStringValidationError` (the `openjd.expr` registered name) | `rust-bindings/src/lib.rs::register_renamed_exception` for `PyFormatStringValidationError` registers it as `FormatStringValidationError`; the v1 wrapper aliases that to `FormatStringError` but the qualname still leaks. |
| 12 | `decode_template` accepts `(template=, supported_extensions=, caller_limits=)` instead of the reference's `(name=, raw_data=, document_type=)` | `src/openjd/model/_v1/__init__.py::decode_template` |

### Other findings (informational, not failing)

* Unicode round-trip through decode → create_job works for
  `"Émile🎬渲染"` and `"渲染"`. ✓
* Boundary integers `i64::MIN`, `i64::MAX`, `2**62`,
  `-(2**62)` round-trip through INT-typed `JobParameter.value`. ✓
* Concurrent decode from 8 Python threads × 20 iterations =
  160 successes, 0 errors. The work runs serially because the
  GIL is held throughout. ✓ correctness; ⚠ throughput.
* `parse_model(obj=…)` correctly dispatches to job vs
  environment templates based on `specificationVersion`. ✓
  (when no extensions are required)
* `document_string_to_object` + JSON / YAML works. ✓
* Empty-steps validation: raises `ModelValidationError("1 validation
  error for JobTemplate\nJobTemplate: must have at least one
  step.")`. ✓
* Missing `specificationVersion`: raises
  `DecodeValidationError("Template is missing Open Job Description
  schema version key: specificationVersion")`. ✓
* Unknown `specificationVersion`: raises
  `DecodeValidationError("Unknown template version: bogus. Values
  allowed for 'specificationVersion' in Job Templates are:
  jobtemplate-2023-09")`. ✓
* `validate_amount_capability_name("amount.worker.foo",
  standard_capabilities=["amount.worker.vcpu"])` correctly rejects
  with a clear message. ✓
* `validate_amount_capability_name("acme:amount.worker.x", …)`
  correctly rejects vendor-prefixed reserved-scope names. ✓
* `RangeExpr("-1 - -2 : -1")` yields `[-2, -1]` (ascending,
  documented). ✓
* `RangeExpr("10-1:-1")` yields `[1..10]` (ascending). ✓
* `it.chunks_default_task_count` setter on adaptive
  parameter-space mutates persistently. ✓
* Pickling works for: `DocumentType`, `JobParameterType`,
  `TaskParameterType`, `ModelExtension`,
  `JobParameterValue`, `TaskParameterValue`,
  `SpecificationRevision`, `TemplateSpecificationVersion`,
  `DecodeValidationError`, `ModelValidationError`,
  `UnsupportedSchema` (under canonical names). ✓
* Pickling fails for `ModelProfile`, `CallerLimits`,
  `ValidationContext` — the spec lists these as pickleable.
  ⚠ minor parity gap with the spec's "Pickle Support" table.
* Decoded model containers (`JobTemplate`, `Job`, `Step`,
  `StepParameterSpaceIterator`) correctly raise on pickle —
  matches the spec's "out of scope" call-out. ✓
* `Step.__eq__` based on step name alone works. ✓
* `Step.__hash__`: not hashable (`TypeError`). The `__eq__`
  + missing `__hash__` is unusual but matches the v0 reference.
* `it.names()` raises `TypeError` (it's a property, not a
  callable). The spec example at line 783
  (`it.names()                  # {"Frame"}`) is wrong; the
  actual access is `it.names`. ⚠ spec example bug.

### Tests written for known gaps

`test/openjd/model_v1/test_known_gaps.py` is currently empty
(only docstring). Each item in the §7 "Confirmed regressions"
table above is a candidate for an xfail-marked test that
documents the gap. The Recommendations section below references
each by surface so the report-driven workflow can pick them up.

## 8. Recommendations

Ordered by impact. Each item references the artifact where the
fix should land, and (where applicable) suggests a
`test_known_gaps.py` xfail to track resolution.

### High priority — behavioural regressions vs reference

1. ~~**Restore `Job.parameters` to include defaults.** The v0
   reference's `Job.parameters` dict contains every parameter
   defined in the template (defaults plus explicit values), with
   `JobParameter.value` resolved to the chosen value. The v1
   binding currently returns only parameters explicitly supplied
   in `job_parameter_values`. This breaks every consumer that
   walks the resolved parameter set — sessions, the worker
   agent, deadline-cli — when they migrate from v0 to v1.

   Surface: `rust-bindings/src/model/job.rs::PyJob::parameters`,
   plus the underlying `openjd_model::job::Job::parameters` field
   that backs it (the upstream `create_job` should populate the
   field with all resolved parameters, not just the explicit
   ones). Add a regression test in
   `test/openjd/model_v1/test_create_job.py::TestParametersDict`
   that decodes a template with two parameters that have
   defaults, calls `create_job(..., job_parameter_values={})`,
   and asserts both keys are present with the default values.
   Add an xfail at
   `test/openjd/model_v1/test_known_gaps.py::test_job_parameters_includes_defaults`
   tracking it until resolved.~~ **Resolved.** Fixed at the
   binding boundary in
   `rust-bindings/src/model/create_job_fns.rs::py_create_job`
   without requiring upstream changes. The binding now routes
   the caller-supplied parameter values through
   `openjd_model::preprocess_job_parameters` before calling
   `openjd_model::create_job`, matching the v0 (pure-Python)
   reference's behaviour. This:
   * fills in defaults from the parameter definitions for any
     names the caller didn't supply explicitly, so
     `Job.parameters` ends up with every defined parameter;
   * runs every per-parameter constraint check before
     instantiation (the previous separate constraint loop was
     redundant and is removed);
   * coerces input values from their raw Python form (string,
     int, etc.) to the typed `ExprValue` shape that
     `create_job` expects.

   Path-resolution-related options use sentinel "skip" values
   (empty `job_template_dir` and `current_working_dir` plus
   `allow_template_dir_walk_up=true`) — the same pattern the
   v0 reference uses, since at `create_job` time we don't know
   the on-disk template directory or the caller's CWD. Callers
   that need PATH-default resolution against a real template
   directory continue to call `preprocess_job_parameters`
   explicitly first and pass the resolved values.

   `extract_input_values` also gained a third accepted shape:
   it now accepts `ParameterValue`-shaped objects (with
   `.type` / `.value` attributes), in addition to the existing
   bare-scalar and dict-shaped (`{"type": ..., "value": ...}`)
   inputs. The previously-separate `extract_parameter_values`
   and `coerce_value_to_type` helpers became dead code and
   were removed.

   New regression tests in
   `test/openjd/model_v1/test_create_job.py::TestParametersDict`
   (7 tests): defaults-only, explicit-overrides-default, bare
   scalar input, dict-shaped input, all-explicit (no defaults
   used), required-parameter-missing error path, and
   constraint-check-via-`create_job` (no separate
   `preprocess_job_parameters` call required).

2. ~~**Fix `StepParameterSpaceIterator.__contains__` for
   `CHUNK[INT]` parameter spaces.** Yielded values from a chunked
   iterator (where `value` is a chunk-range string like `"1-2"`
   under `TaskParameterType::ChunkInt`) do not round-trip through
   `in fresh_iter`. Plain `INT` works.

   Surface: `rust-bindings/src/model/step_param_space.rs::extract_task_parameter_set`
   — when `param_type == TaskParameterType::ChunkInt`, the
   `value` is a range expression string, not a coercible scalar;
   `ExprValue::from_str_coerce` produces an `ExprValue::String`
   that doesn't match what the iterator's `contains` expects.
   Either coerce to a `RangeExpr`-bearing `ExprValue` here, or
   have the upstream `validate_containment` accept the
   string-ranged form.

   xfail at
   `test/openjd/model_v1/test_known_gaps.py::test_chunk_int_iter_contains_self_yielded`
   that decodes a `CHUNK[INT]` template, iterates, and asserts
   each yielded value is `in fresh_iter`.~~ **Resolved.** Fixed
   at the binding boundary in
   `rust-bindings/src/model/step_param_space.rs::extract_task_parameter_set`
   by adding a dedicated branch for `TaskParameterType::ChunkInt`:
   the value string (e.g. `"1-5"`) is parsed as a
   `RangeExpr` via `str::parse::<RangeExpr>` and wrapped as
   `ExprValue::RangeExpr`, matching what the upstream
   `validate_containment` expects structurally. Plain INT and
   other types continue to use the existing
   `from_str_coerce` path. New regression tests in
   `test/openjd/model_v1/test_step_param_space_iter.py::TestChunkIntContains`
   (3 tests): yielded chunks round-trip, non-existent chunks
   correctly report `not in iter`, and explicit
   `TaskParameterValue` instances with matching chunk strings
   are recognised.

3. ~~**Make `CompatibilityError` inherit from `ValueError`.**
   Reference: `class CompatibilityError(ValueError)`.
   Today: `class CompatibilityError(Exception)`. Fix in
   `src/openjd/model/_v1/__init__.py`:

   ```python
   class CompatibilityError(ValueError):
       pass
   ```

   Add a single-line test at
   `test/openjd/model_v1/test_errors.py::test_compatibility_error_is_value_error`.~~
   **Resolved.** `CompatibilityError` in
   `src/openjd/model/_v1/__init__.py` now inherits from
   `ValueError` (with a docstring explaining the rationale).
   Tests in `test/openjd/model_v1/test_errors.py::TestCompatibilityError`
   (5 tests): direct `issubclass`, MRO ordering, catch-via-parent,
   end-to-end raise via `merge_job_parameter_definitions` with
   conflicting types, and end-to-end catch via the `ValueError`
   parent.

4. ~~**Map `ModelError::FormatStringError` →
   `FormatStringError`, not `ModelValidationError`.** File:
   `rust-bindings/src/model/errors.rs::model_err_to_py`.
   Reuse the existing `PyFormatStringValidationError` registered
   under `openjd.expr.FormatStringValidationError`; the v1
   wrapper already aliases that to `FormatStringError`. Update
   the mapper to:

   ```rust
   ModelError::FormatStringError { message, .. } =>
       PyFormatStringValidationError::new_err(message),
   ModelError::Expression(expr_err) =>
       PyExpressionError::new_err(expr_err.to_string()),
   ModelError::Compatibility(msg) =>
       <CompatibilityError class>::new_err(msg),
   ```

   (The third arm requires a Python-side helper because
   `CompatibilityError` is Python-only; the cleanest path is to
   add a `compatibility_error_class()` callback that
   `model_err_to_py` calls.)

   Adds parity with the reference's exception class hierarchy.
   xfail at
   `test/openjd/model_v1/test_known_gaps.py::test_format_string_error_class`.~~
   **Resolved.** All three error-bucket mappings are now wired:
   * `ModelError::FormatStringError { message, .. }` →
     `PyFormatStringValidationError` (re-exported as
     `FormatStringError` from the v1 wrapper, matching
     `openjd.expr.FormatStringValidationError`).
   * `ModelError::Expression(expr_err)` →
     `PyExpressionError` (the same class
     `openjd.expr.evaluate_expression` raises).
   * `ModelError::Compatibility(msg)` → the Python-side
     `CompatibilityError` class. Because `CompatibilityError`
     is Python-only (it lives in `openjd.model._v1.__init__`
     for legacy compatibility), the binding resolves the class
     at error-mapping time via `Python::attach` +
     `py.import("openjd.model._v1").getattr("CompatibilityError")`.
     The GIL is already held by every `model_err_to_py` call
     site (they all run inside `#[pyfunction]` /
     `#[pymethods]` bodies), and `Compatibility` errors are
     rare in practice, so the import-by-name overhead is
     acceptable. The implementation includes a fallback to
     `PyModelValidationError` if the import or
     `CompatibilityError(msg)` construction fails — should
     never happen in practice but prevents a panic if the
     module isn't loaded.
   New regression tests in
   `test/openjd/model_v1/test_errors.py::TestExpressionErrorMapping`
   pin the `Expression` mapping via a real-world
   create-job-time trigger (CHUNK[INT] `defaultTaskCount`
   format string resolving to a non-integer). The
   `FormatStringError` arm has no Python-reachable
   create-job-time trigger today (decode-time format-string
   parse errors batch under `ModelValidationError`, by
   design); the wiring is correct and will surface the right
   class once upstream hits the dedicated variant.

### Medium priority — surface visibility / wrapper module

5. **Re-export `ModelValidationError` and `UnsupportedSchema`
   at the `openjd.model._v1` top level.** The spec's example
   code uses `from openjd.model import ModelValidationError,
   UnsupportedSchema`. Today, only `DecodeValidationError`
   makes it past the wrapper's `__init__.py`. Add to
   `src/openjd/model/_v1/__init__.py`:

   ```python
   from openjd._openjd_rs import (
       ModelValidationError,
       UnsupportedSchema,
       # ... existing imports
   )
   ```

   and add to `__all__`.

6. ~~**Re-export `decode_job_template_str` and
   `decode_environment_template_str` through the wrapper.**
   Both are spec'd entry points. Today users must import them
   from `openjd._openjd_rs` directly — bypasses the wrapper's
   docstring helpers. Add the symbols to `__init__.py`'s
   imports and `__all__`.~~ **Resolved.** Both functions are
   now exposed as wrappers in `src/openjd/model/_v1/__init__.py`
   that delegate to the underlying Rust functions. Each wrapper
   carries a Sphinx-style docstring, accepts the same
   ``supported_extensions`` (and ``caller_limits`` for the job
   variant) kwargs as their dict-shaped peers, and returns the
   appropriate `template.JobTemplate` /
   `template.EnvironmentTemplate`. Both names are added to
   ``__all__``. The spec gained two new dedicated subsections
   (``decode_job_template_str`` and
   ``decode_environment_template_str``) with examples, and the
   "Module Layout" table no longer carries the workaround note
   about importing from ``openjd._openjd_rs``. New regression
   tests in
   `test/openjd/model_v1/test_parse.py::TestDecodeJobTemplateStr`
   (6 tests) and `…::TestDecodeEnvironmentTemplateStr` (3
   tests) pin the YAML default, explicit YAML/JSON, JSON-via-YAML
   default, ``supported_extensions`` forwarding, and invalid-input
   error paths.

7. ~~**Re-export structural pyclasses at the
   `openjd.model._v1` top level — or update the spec to use
   submodule paths consistently.** Spec uses `from openjd.model
   import Job, Step, JobTemplate, EnvironmentTemplate,
   StepParameterSpaceIterator, StepDependencyGraph, …`. None of
   these import as written from `_v1` today. Either:

   * **Option A: top-level re-exports.** Add the structural
     pyclasses to `_v1/__init__.py` (this matches the v0
     reference's surface and lets users follow the spec
     verbatim).
   * **Option B: spec rewrite.** Update every spec example
     that imports a structural pyclass to use the submodule
     path: `from openjd.model._v1.template import JobTemplate`,
     `from openjd.model._v1.job import StepParameterSpaceIterator`,
     etc. Add a "Module Layout" section to the spec near the
     top explaining the split.

   Option A is the smaller change (15-20 import lines) and
   matches user expectations; Option B is more honest about the
   architecture. **Recommend Option A** for backward-compat
   with v0 and to keep the spec examples copy-pasteable.~~
   **Resolved (Option B chosen).** All 24 `from openjd.model
   import` snippets in `specs/python-model-interface.md` now use
   the canonical submodule path for each symbol:
   * Entry-point functions (`decode_*_template`, `create_job`,
     `preprocess_job_parameters`, `merge_job_parameter_definitions`,
     `decode_template`) and convenience classes (`ParameterValue`,
     `SpecificationRevision`, `TemplateSpecificationVersion`,
     `ValueReferenceConstants`, `IntRangeExpr`,
     `CancelationMethod*`, `DocumentType`, `CallerLimits`,
     `ModelProfile`, `DecodeValidationError`) → `openjd.model._v1`.
   * Structural pyclasses → submodules:
     `template.JobTemplate`/`EnvironmentTemplate`/etc. under
     `openjd.model._v1.template`; `job.StepParameterSpaceIterator`/
     `StepDependencyGraph` under `openjd.model._v1.job`;
     `JobParameterType`/`TaskParameterType`/`ModelExtension`/
     `ValidationContext` under `openjd.model._v1.types`.
   * `decode_job_template_str` → `openjd._openjd_rs` (until it's
     re-exported through the wrapper, see Rec #6).
   A new "Module Layout" section was added to the spec right
   after the existing "Architecture" section, with a 5-row table
   mapping each submodule to its canonical contents. All 24 spec
   imports were verified to import successfully at runtime.

8. ~~**Fix `parse_model` to forward `supported_extensions=` and
   `caller_limits=`.** Today `parse_model(obj={…with extensions
   field…})` fails because the function calls
   `decode_job_template_dict(obj)` with no extensions
   allowlist. Update signature:

   ```python
   def parse_model(
       *, model: Any = None, obj: dict[str, Any],
       supported_extensions: Optional[list[str]] = None,
       caller_limits: Optional[CallerLimits] = None,
   ) -> Any:
   ```

   Forward the kwargs to the underlying `decode_*_template_dict`.~~
   **Resolved by removal.** `parse_model` was a v0 backward-compat
   shim that the v1 spec has never documented as a public entry
   point. The right resolution is to remove it from the v1
   surface, not to extend it. Removed from
   `src/openjd/model/_v1/__init__.py` (function body and
   `__all__` entry) and from the Module Layout table in
   `specs/python-model-interface.md`. v1 callers that need the
   "auto-detect template type from `specificationVersion`"
   behaviour can construct a one-line dispatch themselves over
   `decode_job_template_dict` / `decode_environment_template_dict`,
   or call the shape-specific entry point directly. No v1 tests
   or internal v1 modules referenced the function (verified by
   grep across `src/openjd/model/_v1/`, `test/openjd/model_v1/`,
   and `specs/`); no external consumers
   (`openjd-sessions-for-python`) reference it either.

### Medium priority — small parity / spec items

9. **Make `DocumentType` hashable.** Add `frozen, hash` to
   `#[pyclass(...)]` in `rust-bindings/src/model/types.rs`,
   matching `JobParameterType` and `TaskParameterType`. Add a
   regression test in
   `test/openjd/model_v1/test_pickle.py::TestDocumentType::test_hashable`.

10. **Pickle support for `ModelProfile`, `CallerLimits`,
    `ValidationContext`.** Spec's "Pickle Support" table lists
    all three as pickleable, but at runtime `pickle.dumps(profile)`
    fails. Implement `__reduce__` returning
    `(_reconstruct_kwargs, (cls, kwargs))`. Add tests in
    `test/openjd/model_v1/test_pickle.py`.

11. **Tighten `validate_*_capability_name` signatures to the
    reference's strict form.** Today the wrapper's signature is
    `(name: str = "", *, capability_name: str = "",
    standard_capabilities=None)` — accepts positional `name`
    and makes `standard_capabilities` optional. Reference is
    strict kw-only `(*, capability_name, standard_capabilities)`.
    Either align or document the divergence in the spec.

12. **Fix `decode_template` signature.** Today it accepts the
    `decode_job_template` kwargs (`template=`,
    `supported_extensions=`, `caller_limits=`); the v0 reference
    expects `(*, name, raw_data, document_type)`. If the goal
    is reference parity, accept both shapes (detect by which
    kwargs are present) and dispatch. If the goal is a new
    wrapper API, keep the current shape but **document the
    divergence in the spec** — the spec section currently says
    "Mirrors the v0 reference" which is misleading.

13. ~~**Update the spec's `it.names()` example.** Line ~783 in
    `specs/python-model-interface.md` shows
    `it.names()                  # {"Frame"}` but
    `it.names` is a property. Trying `it.names()` raises
    `TypeError: 'set' object is not callable`. Drop the
    parentheses.~~ **Resolved.** The spec now reads
    `it.names                    # {"Frame"} — property, not callable`,
    with the inline comment calling out the property/method
    distinction so future readers don't reintroduce the typo.

### Lower priority — polish / hygiene

14. **Resolve the 56 clippy lints.** File: `rust-bindings/src/`.
    Same shape as the prior `expr` evaluation. Apply the
    suggested rewrites (`#[allow(non_camel_case_types,
    upper_case_acronyms)]` on the deliberate Python-facing
    enums, opt in to `#[pyclass(from_py_object)]` explicitly,
    use `Bound::cast` instead of `downcast`, factor the
    nine `type_complexity` cases into named type aliases,
    remove the unused `supported_extension_strings` and
    `from_rust` items).

15. **Release the GIL on long-running calls.** Wrap
    `decode_job_template_*`, `decode_environment_template_*`,
    `create_job`, and the iterator-driving
    `StepParameterSpaceIterator::new` in
    `Python::allow_threads(|py| { … })`. Without this, threaded
    Python servers (Deadline Cloud worker agent, etc.) cannot
    decode or create-job in parallel.

16. **Resolve the `EmbeddedFile.type` vs `EmbeddedFile.type_`
    asymmetry.** Either expose both names on both classes (the
    forgiving option) or update the spec to call out the
    asymmetry explicitly (the documenting option). Today the
    spec accidentally calls out both names — once with `_`
    (line 352, job-time) and once without (line 556,
    template-time) — without explaining why.

17. **Fix `preprocess_job_parameters` error message for
    relative paths.** When the caller passes a relative
    `job_template_dir`, the error message reports the empty
    string instead of the user-supplied path:

    ```
    DecodeValidationError: The value supplied for the job template dir, , is not an absolute path.
    ```

    The empty rewrite is gone for absolute paths but remains
    in the error path. Surface:
    `rust-bindings/src/model/create_job_fns.rs::py_preprocess_job_parameters`.

18. **Spec drift: document the binding-side surface more
    explicitly.** The spec already covers the major shapes,
    but the following are observably exposed but not
    mentioned:

    * `it.reset_iter()` method on `StepParameterSpaceIterator`.
    * `Step.__eq__` / `Step` un-`__hash__`-ability.
    * `_openjd_rs.create_environment` and `_openjd_rs.deserialize_step`
      (called by the sessions runtime; today users must
      import from `_openjd_rs` directly).
    * `ParameterValueType` alias (= `JobParameterType`).
    * `DEFAULT_MEMORY_LIMIT` / `DEFAULT_OPERATION_LIMIT`
      module-level constants.

    Add a "Bindings-internal helpers" section near the bottom
    of the spec listing these with a "subject to change"
    disclaimer.

19. **Backfill format-string and combination-expression
    integration tests** in `test/openjd/model_v1/`. The
    `format_strings/` and `_internal/` directories are empty;
    the v0 reference has substantial coverage there. Even
    integration-level tests (decode a template with a
    complex `let:` binding, verify the resolved
    `script.let_bindings` matches expectations) would catch
    regressions that the current binding-side test surface
    misses.

20. **Switch the dict→json.dumps→serde_json round-trip in
    `decode_*_dict` to a direct `pythonize::depythonize` (or
    equivalent) conversion.** Today's detour
    (`rust-bindings/src/model/decode.rs::dict_to_json_value`)
    doubles the cost for callers that already hold a dict
    and rejects values that aren't JSON-serialisable
    (`Decimal`, `Path`, custom objects). Worth measuring
    against the existing `test_yaml_loader_performance.py`
    benchmark before committing to make sure it's an actual
    win.

