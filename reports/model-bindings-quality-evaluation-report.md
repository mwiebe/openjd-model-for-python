# openjd-model Bindings Quality Evaluation Report

**Date:** 2026-05-26
**Component:** `openjd.model._v1`
**Reference branch:** `OpenJobDescription/openjd-model-for-python` `mainline` (commit `94129dc`)

## Executive Summary

The Rust-backed `openjd.model._v1` bindings are in good overall shape and
the core functionality is solid: the build is clean (no Rust warnings on
the default feature set), all `cargo clippy --all-targets -- -D warnings`
checks pass, the full test suite (2306 v0 + 905 v1 = 3211 tests) passes
with zero failures, the committed `_openjd_rs.pyi` stub matches what
`pyo3-stub-gen` produces, and v0 isolation is *perfect* — the v1 surface
contains zero imports from any v0 module across `src/openjd/model/_v1/`,
`rust-bindings/src/`, and `test/openjd/model_v1/`. Pickle round-trips work
for every type the spec says they should, and every Rust-backed pyclass
reports its user-facing module via `__module__` (verified by 100+
parametrized assertions in `test_pyclass_modules.py`). Recent work has
cleared a substantial set of previous report items — IntRangeExpr
removal, top-level error re-exports, exception hierarchy fixes,
`Job.parameters` defaults, CHUNK[INT] iterator parity, structural
`__eq__` on profile types, capability-name signature parity, EmbeddedFile
`.type` uniformity, and the `parse_model` removal are all already in
place and visible in the recent commit history.

The remaining gaps are concentrated on **job-time pyclass field
coverage** and a few **error-class shape divergences**. The Rust
`job::Step` struct exposes `host_requirements` and `job::EmbeddedFile`
exposes `runnable` and `end_of_line`, but the corresponding Python
getters on `PyStep` and the job-time `PyEmbeddedFile` are missing.
`StepDependencyGraph` lost v0's `max_indegree`/`max_outdegree` properties.
`StepParameterSpaceIterator` lost v0's `validate_containment()` method.
`JobParameter` exposes `param_type` but not the v0 alias `type`. The
typed errors `UnsupportedSchema` and `TokenError` diverge from v0 in
constructor shape and class hierarchy respectively. `Action.timeout`
returns `str` where v0 returns `int`. `merge_job_parameter_definitions`
returns `list[dict]` in v1 vs `list[JobParameterDefinition]` in v0,
which is a documentable design divergence (the v1 dict shape is more
minimal than the typed v0 form). Finally, the stub-gen-feature build
emits one `unused_imports` warning for `task_parameter.rs`. No P1
(security or correctness) issues were found.

## 1. Python Interface Spec Review

`specs/python-model-interface.md` is detailed (1,034 lines) and covers
the four-submodule layout (`_v1`, `_v1.template`, `_v1.job`, `_v1.types`,
`_v1.errors`), the entry-point functions, all 12 `Job*ParameterDefinition`
variants, the 5 task-parameter pyclasses, all 11 `*UserInterface`
pyclass variants, the `ModelProfile` / `ModelExtension` / `CallerLimits`
/ `ValidationContext` profile types, and the pickle-support contract.
It also documents intentional v0 divergences (Pydantic-vs-no-Pydantic,
RangeExpr ascending iteration, dropping `IntRangeExpr`, dropping
`parse_model`/`model_to_object`, "subject to change" bindings-internal
helpers) with rationale.

**Spec gaps found during evaluation:**

* The spec's `JobParameter` example reads
  `param.param_type` and `param.value`, but does **not** mention that v0
  exposed `param.type` and `param.description`. A v0 caller migrating
  to v1 cannot tell from the spec that `param.type` is gone (only
  `param_type` is documented). Either the spec should explicitly list
  the dropped accessors as "intentional divergence" or the binding
  should add a `.type` alias and a `.description` getter.
* The spec's `Step` example covers `name / description / script /
  parameterSpace / stepEnvironments / dependencies / resolvedBindings /
  resolved_symtab` but **omits `host_requirements`/`hostRequirements`**.
  v0's job-time `Step` has `hostRequirements` and the Rust `job::Step`
  struct still carries `host_requirements: Option<HostRequirements>`,
  so the binding can expose it. Either the spec should explicitly drop
  the field with a rationale, or the binding should add the getter.
* The spec's `EmbeddedFile` (job-time) example shows
  `name / type / filename / data` but does **not** mention
  `runnable` or `endOfLine`. v0 exposes both, the Rust
  `job::EmbeddedFile` struct carries both, the *template-time* binding
  exposes both, and the spec is silent on the job-time version. This is
  almost certainly an omission — see Recommendations.
* The spec's `StepDependencyGraph` documents only `topo_sorted()` and
  `step_names()`. v0's API also has `max_indegree`, `max_outdegree`,
  and `step_node(*, stepname=)` (kw-only). The v1 binding has
  `step_node` accepting both positional and keyword args (a superset)
  but no degree properties.
* The spec's `StepParameterSpaceIterator` documents seven members
  (`__len__`, `__getitem__`, iteration, `names`, `chunks_*`,
  `reset_iter`) but does **not** mention v0's `validate_containment()`
  method — silently dropped without a recommended replacement.
* `merge_job_parameter_definitions` is shown by example but the spec
  does not document the return type. v0 returns
  `list[JobParameterDefinition]` (typed objects with full
  per-variant constraint info); v1 returns `list[dict]` with only
  `name / type / default / source / [objectType] / [dataFlow]`.
  This is a meaningful design divergence and deserves a paragraph in
  the spec.
* The spec acknowledges `decode_template` as a deprecated alias for
  `decode_job_template`. Confirmed implemented.
* The spec describes the dict-input conversion shim (with the
  `pythonize`-vs-`json.dumps` measurement). Confirmed implemented.

**Spec-vs-binding alignment that *is* correct:**

* All 111 Rust-backed pyclasses listed in `EXPECTED_MODULES`/
  `EXPECTED_EXCEPTION_MODULES` in `test_pyclass_modules.py` resolve to
  the spec'd module path (covered by 100+ tests in that file).
* `decode_*_template_str` re-exported through `_v1` matches the spec.
* `ModelValidationError` and `UnsupportedSchema` re-exported at top
  level matches the spec ("Also re-exports … for top-level
  convenience").
* The five `*TaskParameter` job-time variants map 1:1 to the Rust
  `TaskParameter` enum, as documented in the spec's "Field shapes"
  table.
* The 12 `Job*ParameterDefinition` variants are all listed in the
  spec table and all wired in.
* The 11 `*UserInterface` variants are all listed and all wired in.
* `EmbeddedFile.type` is documented as returning the spec string
  (`"TEXT"`), and the binding uses `.type` (not `.type_`) on both
  template-time and job-time pyclasses, matching the recent
  `EmbeddedFile.type` parity commit.

## 2. PyO3 Binding Source Review

`rust-bindings/src/model/` — 14 files, ~225 KB total. Per-file notes:

* **`mod.rs`** — Re-export hub; clean.
* **`errors.rs`** — Three `create_exception!` macros (Decode/Model/
  Unsupported), all registered via `register_renamed_exception` in
  `lib.rs` so canonical names appear in `__module__` and tracebacks.
  `model_err_to_py` correctly maps `FormatStringError` →
  `PyFormatStringValidationError`, `Expression` → `PyExpressionError`,
  `Compatibility` → the Python-side `CompatibilityError` (looked up
  dynamically since it's a Python class). Per the recent
  hierarchy-parity commit (`0e592b9`), this is correct.
* **`types.rs`** — `DocumentType`, `TemplateSpecificationVersion`,
  `JobParameterType`, `TaskParameterType`, `JobParameterValue`,
  `TaskParameterValue`. All have `__reduce__` for pickle and `name`
  getters where useful. Note: `PyTemplateSpecificationVersion` is
  declared with `module = "openjd._openjd_rs"` (not
  `openjd.model._v1.types`) by intentional design — see comment in
  `test_pyclass_modules.py` — so the Python-side str-Enum shim can
  live at the public name without a pickle conflict.
  `PyTaskParameterValue` and `PyJobParameterValue` use
  `call_method0("as_str")` plus attribute fallback in `__eq__`, which
  accepts both Rust enum and v0-Pydantic-Enum shapes for compatibility.
* **`profile.rs`** — `SpecificationRevision`, `ModelExtension`,
  `ModelProfile`, `CallerLimits`, `ValidationContext`. All five have
  `__reduce__` and (where relevant) `__eq__`. `to_expr_profile` is
  a thin shim around the upstream Rust function. The `from_strings`
  classmethod handles unknown extension names via
  `pyo3::exceptions::PyValueError::new_err`, which matches the spec.
* **`template.rs`** — `JobTemplate` and `EnvironmentTemplate`. Both
  expose snake_case + camelCase aliases for `specification_version`,
  `job_environments`, and `parameter_definitions`, which matches the
  spec's "Both snake_case and camelCase property accessors are
  provided." Clean.
* **`template_types.rs`** — Template-time pyclasses. ~995 lines.
  `PyEmbeddedFile` (template-time) exposes `runnable` and
  `endOfLine`/`end_of_line` correctly, with reasonable
  `__reduce__` shapes. ✓
* **`job.rs`** — Job-time pyclasses. **The job-time `PyEmbeddedFile`
  is missing `runnable` and `end_of_line` getters even though the Rust
  struct has both fields populated.** **The job-time `PyStep` is
  missing the `host_requirements` getter even though the Rust struct
  has the field.** **The job-time `PyJobParameter` is missing a
  `.type` alias for `.param_type`.** All three are easy fixes — see
  Recommendations.
* **`step_param_space.rs`** — `StepParameterSpaceIterator`. The
  inner iterator state is held under `Mutex<…>` because pyclass types
  must be `Sync`. Random-access (`__getitem__`) builds a fresh,
  non-mutating iterator so it doesn't disturb the persistent cursor.
  The setter for `chunks_default_task_count` rejects zero and
  non-adaptive spaces with the same messages as v0. **Missing**:
  `validate_containment(params)` — see Recommendations.
* **`step_dependency_graph.rs`** — `StepDependencyGraph`,
  `StepDependencyNode`, `StepDependencyEdge`. **Missing**:
  `max_indegree` and `max_outdegree` properties — see Recommendations.
  The `step_node` method accepts both positional and keyword args
  (which is a v0 superset) but the spec doesn't mention this; minor.
* **`task_parameter.rs`** — Five typed pyclasses + `TaskChunksDefinition`.
  Lines 575-581 contain a `#[cfg(not(feature = "stub-gen"))] use PyType
  as _;` workaround intended to silence an unused-import warning when
  stub-gen is disabled — **but the warning fires when stub-gen *is*
  enabled** (verified at line 40, `pyo3::types::{PyDict, PyList, PyType}`
  imports `PyType` which is unused throughout the file). Minor; fix is
  to either drop `PyType` from the import list entirely or invert the
  cfg flag.
* **`step_param_space_def.rs`**, **`job_param_defs.rs`**,
  **`user_interfaces.rs`** — Template-time variants. Clean. Cover
  every variant the spec lists.
* **`create_job_fns.rs`** — `py_create_job`, `py_preprocess_job_parameters`,
  `py_merge_job_parameter_definitions`, `py_evaluate_let_bindings`,
  `py_create_environment`, `py_deserialize_step`. The `py_create_job`
  function deliberately routes through `preprocess_job_parameters`
  internally to fill defaults (matching v0 behaviour); this is well
  commented and matches the recent `Job.parameters includes defaults`
  fix. The `py_preprocess_job_parameters` function preserves the
  user-supplied `job_template_dir` in the error path (per the recent
  `preprocess_job_parameters error names the user-supplied path`
  commit) and rewrites `current_working_dir == "."` to `""` for the
  upstream join semantics — both behaviours documented inline.
* **`decode.rs`** — Four decode entry points. Clean.

**`rust-bindings/src/lib.rs`** — registers 64+ model pyclasses,
six model entry-point functions, and three exception classes via
`register_renamed_exception`. All registrations are present and
mapped to the right module strings. ✓

**ABI3 / GIL / type-conversion concerns:**

* `Cargo.toml` declares `abi3-py39`. No Python C-API features beyond
  ABI3 are used.
* The bindings hold the GIL across all calls. Decode and create
  operations are CPU-bound and short-lived for typical templates, so
  releasing the GIL would not help. (This matches the same decision
  in the expr bindings.)
* `int` ↔ `i64`/`u64`/`usize` conversion is via PyO3's defaults,
  with `Option<i64>` fields for size limits. No quiet truncation seen.
* `pathlib.Path` ↔ `PathBuf` is used in `py_preprocess_job_parameters`;
  the `.to_str().unwrap_or("")` pattern silently drops non-UTF-8 paths.
  Acceptable on Linux/macOS; on Windows where `Path` can be UTF-16,
  this would lose information — but that's an upstream Rust crate
  limitation, not a binding-side bug.

## 3. Python Wrapper Module Review

`src/openjd/model/_v1/__init__.py` (657 lines) re-exports decode/create
functions, pickleable Python-side compat shims (`ParameterValue`,
`RevisionExtensions`, `CancelationMethod*`, `TokenError`,
`CompatibilityError`), str-Enum shims for `SpecificationRevision` and
`TemplateSpecificationVersion`, capability-validation helpers, and
legacy `openjd.expr` re-exports. Recent cleanup commits (top-level
re-export of `ModelValidationError`/`UnsupportedSchema`, capability
signature kw-only fix, `decode_*_template_str` re-export, drop of
`IntRangeExpr` and `parse_model`) are all visible.

`src/openjd/model/_v1/template.py`, `job.py`, `types.py`, `errors.py`
each re-export the right subset from `openjd._openjd_rs` and provide
short aliases (`Action = TemplateAction`, etc.) where the template-time
and job-time names collide. Both surfaces match the spec's submodule
table at line 67.

`src/openjd/model/_v1/v2023_09/__init__.py` — empty / placeholder file
(coverage 0%). Only kept to allow `from openjd.model._v1 import v2023_09`
to succeed. Acceptable; no spec entry mentions it as part of the public
surface.

**Wrapper-module gaps:**

* `__init__.py` defines a Python-only `TokenError(Exception)` class
  — but **v0's `TokenError` inherits `ExpressionError` (which inherits
  `ValueError`)**, so v0 callers that catch `ExpressionError` to handle
  `TokenError` will silently miss it under v1. The spec table lists
  `TokenError | Exception` so the spec and wrapper agree, but the
  v0 reference disagrees. See Rec #?.
* The same `__init__.py` does not export a top-level `IntRangeExpr`
  alias for `RangeExpr`. The recent `refactor(model)!: drop
  IntRangeExpr alias from openjd.model._v1` commit explicitly removed
  it — confirmed; v0 callers that import `IntRangeExpr` from
  `openjd.model._v1` will break, but the spec acknowledges this
  ("Earlier versions exposed an ``IntRangeExpr`` alias … Use
  ``openjd.expr.RangeExpr`` directly instead.").

## 4. Test Review

`test/openjd/model_v1/` contains 22 test files covering 905 assertions,
all passing. Coverage is good across the surface:

* **Decode/parse**: `test_parse.py`, `test_template_types.py`,
  `test_create_job.py`, `test_environment_template.py` (via
  test_create_job).
* **Validation paths**: `test_errors.py`, `test_create_job.py`.
* **Iteration**: `test_step_param_space_iter.py` (520 lines).
* **Job parameters**: `test_job_param_defs.py`, `test_task_parameter.py`,
  `test_user_interfaces.py`, `test_merge_job_parameters.py`.
* **Pickle**: `test_pickle.py` covers every type the spec promises is
  pickleable.
* **Pyclass module attributes**: `test_pyclass_modules.py` (~100
  parametrized cases, plus regression guards).
* **Capabilities**: `test_capabilities.py` (matches v0 case-by-case).
* **Step graph**: `test_step_dependency_graph.py`.
* **Range expr**: `test_range_expr.py`.
* **Misc**: `test_fuzz.py`, `test_symbol_table.py`, `test_importable.py`,
  `test_version_enums.py`, `test_step_param_space_def.py`,
  `test_rust_model_bindings.py`.

`test_known_gaps.py` previously contained no substantive tests; this
evaluation has added 9 xfail tests for the parity gaps documented in
§5/§7.

**Tests in v0 reference that have no obvious analogue in v1:**

* `test/openjd/model/v2023_09/test_step_host_requirements.py` —
  no v1 equivalent. Naturally — v1's job-time `Step` doesn't expose
  `host_requirements`. Closely tied to Rec #2.
* `test/openjd/model/v2023_09/test_chunk_int_task_parameter_type.py`
  — no v1 equivalent at this name, but `test_step_param_space_iter.py`
  and `test_task_parameter.py` cover CHUNK[INT] in detail.
* `test/openjd/model/v2023_09/test_environments.py` — environments
  are exercised through `test_create_job.py` and
  `test_template_types.py` in v1 but not in a dedicated file.
* `test/openjd/model/v2023_09/test_job_template.py` — exercised
  through `test_template_types.py`.
* `test/openjd/model/_internal/*` — v0 internals (combination expr,
  param-space dim validation, range expr, variable reference
  validation). v1 has these as Rust-side tests in `openjd-rs`, which
  is the right place for them.
* `test/openjd/model/test_convert_pydantic_error.py` — irrelevant
  for v1 (no Pydantic).

The v0 → v1 test-parity coverage is strong; missing tests align with
intentional surface-area changes (no Pydantic, no `host_requirements`
gap currently being exposed).

## 5. Parity with Pure-Python Reference

| Symbol | Reference (v0) | Binding (v1) | Status |
|---|---|---|---|
| `decode_job_template` | `(*, template, supported_extensions=None)` returns `JobTemplate` | `(*, template, supported_extensions=None, caller_limits=None)` returns `template.JobTemplate` | ✓ (superset) |
| `decode_environment_template` | `(*, template, supported_extensions=None)` | same | ✓ |
| `decode_template` | deprecated alias | same | ✓ |
| `decode_job_template_str` / `decode_environment_template_str` | n/a (v0 only had `document_string_to_object` + decode) | re-exported through `_v1` | ✓ (added) |
| `document_string_to_object` | accepts `document_type` param | same; v1 wraps `yaml.load` and raises `DecodeValidationError` on parse failure | ✓ |
| `create_job` | `(*, job_template, job_parameter_values, environment_templates=None)` | `(*, job_template, job_parameter_values, environment_templates=None, validation_context=None)` | ✓ (superset) |
| `preprocess_job_parameters` | takes `job_template_dir, current_working_dir` as positional kw-only | same | ✓ |
| `merge_job_parameter_definitions` | returns `list[JobParameterDefinition]` (typed) | returns `list[dict]` with limited keys | ⚠ (return type narrowed) |
| `parse_model` | available | dropped per recent commit | ✓ (intentional, spec'd) |
| `model_to_object` | available | dropped | ✓ (intentional, spec'd) |
| `validate_amount_capability_name` / `validate_attribute_capability_name` | `(*, capability_name, standard_capabilities)` | same shape | ✓ |
| `STANDARD_AMOUNT_CAPABILITIES` / `STANDARD_ATTRIBUTE_CAPABILITIES` | dict constants | same | ✓ |
| `Job.name / .description / .revision / .extensions / .steps / .parameters / .job_environments` | all present | all present (revision returns `"2023-09"`) | ✓ |
| `Step.name / .description / .script / .stepEnvironments / .parameterSpace / .dependencies` | all present | all present | ✓ |
| `Step.hostRequirements` | present | **missing** on job-time `Step` (Rust struct has the field) | ❌ (Rec #2) |
| `Step.resolvedBindings / .resolved_symtab` | n/a (v0 didn't have these) | present | ✓ (added) |
| `Step.__eq__` / `.__hash__` (by name) | works (default Pydantic) | explicitly by-name | ✓ |
| `StepScript.actions / .embeddedFiles` | present | present (plus EXPR-only `.let`) | ✓ |
| `StepActions.onRun` | present | present | ✓ |
| `Action.command / .args / .timeout / .cancelation` | `command: FormatString`, `timeout: Optional[int \| FormatString]`, `cancelation: Optional[CancelationMethodTerminate \| CancelationMethodNotifyThenTerminate]` | `command: FormatString`, `timeout: Optional[str]`, `cancelation: Optional[CancelationMode]` | ⚠ (timeout int vs str; CancelationMode unified) |
| `EmbeddedFile.name / .type / .filename / .data` | all present | all present | ✓ |
| `EmbeddedFile.runnable` | present | **missing** on job-time | ❌ (Rec #3) |
| `EmbeddedFile.endOfLine` / `.end_of_line` | `endOfLine` present | **missing** on job-time | ❌ (Rec #4) |
| `JobParameter.type` | `JobParameterType` enum | only `.param_type` (string spec name) | ❌ (Rec #1) |
| `JobParameter.value` | bare value (int/str/...) | `ExprValue` (use `.item()`) | ⚠ (documented divergence) |
| `JobParameter.description` | present | **missing** (Rust struct doesn't carry it either) | ⚠ (Rec #5; upstream gap) |
| `StepParameterSpace.taskParameterDefinitions` | `dict[str, TaskParameterDefinition]` | `dict[str, IntTaskParameter \| Float… \| ChunkInt…]` | ✓ (typed-class names diverge by design) |
| `StepParameterSpace.combination` | present | present | ✓ |
| `StepParameterSpaceIterator.__len__ / __iter__ / __next__ / __getitem__ / __contains__` | all present | all present | ✓ |
| `StepParameterSpaceIterator.names` (property) | present | present | ✓ |
| `StepParameterSpaceIterator.chunks_adaptive / chunks_parameter_name / chunks_default_task_count` | all present | all present | ✓ |
| `StepParameterSpaceIterator.reset_iter` | present | present | ✓ |
| `StepParameterSpaceIterator.validate_containment(params)` | present | **missing** | ❌ (Rec #6) |
| `StepDependencyGraph(*, job)` | present | present | ✓ |
| `StepDependencyGraph.step_node(*, stepname=)` | kw-only | accepts both positional and kw-only | ✓ (superset) |
| `StepDependencyGraph.topo_sorted()` | present | present | ✓ |
| `StepDependencyGraph.max_indegree / max_outdegree` | properties | **missing** | ❌ (Rec #7) |
| `StepDependencyGraph.step_names()` | n/a | present | ✓ (added) |
| `StepDependencyGraphNode / StepDependencyGraphStepToStepEdge` | dataclasses | aliased to v1's `StepDependencyNode` / `StepDependencyEdge` | ✓ |
| `DocumentType.YAML / .JSON` | `enum.Enum` | Rust pyclass enum | ✓ |
| `JobParameterType` (12 variants) | `str`-Enum | Rust pyclass enum (12 variants), `.as_str()` returns spec form | ✓ |
| `TaskParameterType` (5 variants incl. `CHUNK_INT` → `"CHUNK[INT]"`) | str-Enum | Rust pyclass enum, `.as_str()` returns spec form | ✓ |
| `SpecificationRevision.v2023_09` | str-Enum (also has `UNDEFINED`) | str-Enum (no `UNDEFINED`) + `.to_rust()` shim | ✓ (UNDEFINED dropped per "purely for internal testing" docstring; not a public-API loss) |
| `TemplateSpecificationVersion.{JOBTEMPLATE_v2023_09,ENVIRONMENT_v2023_09}` | str-Enum (also `UNDEFINED`) | str-Enum (no `UNDEFINED`) | ✓ (same rationale) |
| `ParameterValue` | dataclass | Python class accepting `(*, type, value)` | ✓ |
| `ParameterValueType` | alias for `JobParameterType` | alias for `JobParameterType` (recent commit) | ✓ |
| `RevisionExtensions(spec_rev, supported_extensions)` | dataclass | compat shim with `.to_profile()` | ✓ (legacy compat) |
| `CancelationMethodTerminate / CancelationMethodNotifyThenTerminate` | typed Pydantic models | Python compat shims with `mode` and `notify_period_in_seconds` | ✓ |
| `ValueReferenceConstants` | str-Enum | str-Enum (same prefixes) | ✓ |
| `CommandString / ArgString` | aliases for `FormatString` | aliases for `FormatString` | ✓ |
| `EmbeddedFileText / EmbeddedFiles` | aliases | aliases | ✓ |
| `DecodeValidationError` | `ValueError` subclass | `ValueError` subclass, registered with canonical module | ✓ |
| `ModelValidationError` | `ValueError` subclass | same | ✓ |
| `UnsupportedSchema` | `ValueError`, constructor `(version: str)`, sets `_version` attr, message wraps | `ValueError`, plain `(msg: str)`, no `_version` attr | ❌ (Rec #8) |
| `ExpressionError` | `ValueError` subclass | same | ✓ |
| `FormatStringError` (alias for `FormatStringValidationError`) | `ValueError` subclass | same | ✓ |
| `CompatibilityError` | `ValueError` subclass | `ValueError` subclass (Python-side class) | ✓ (recent commit) |
| `TokenError` | inherits `ExpressionError` (so MRO includes `ValueError`) | inherits `Exception` directly | ❌ (Rec #9) |
| `version` (str) | exported | exported | ✓ |

Behavioural divergences (not in the table):

* **Validation error message format**: v0 produces Pydantic's
  `1 validation errors for JobTemplate\nsteps[0] -> script -> ...:\n\tString must be at least 1 characters long`
  (with a "1 validation errors" plural typo); v1 produces
  `1 validation error for JobTemplate\nsteps[0] -> script -> ...:\n\tmust not be empty.`
  (singular and reworded). The path-prefixed format is preserved
  (Rec for spec callout). The exception class also differs: v0 wraps
  pydantic `ValidationError` in `DecodeValidationError`; v1 raises
  `ModelValidationError`. Both are `ValueError` subclasses.
* **Parameter constraint errors**: v0 says
  `"Value (100) for parameter Count must be at most 10."`; v1 says
  `"Parameter 'Count': value 100 exceeds maximum 10"`. Both are
  `DecodeValidationError`.
* **Iteration / equality**: parameter-space iteration produces
  `dict[str, ParameterValue]` in v0 and `dict[str, TaskParameterValue]`
  in v1 (different Python class names, equivalent behaviour). The
  iterator's items compare equal via per-class `__eq__` in both
  surfaces.

## 6. Build and Test Results

```
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml
… clean (cargo build, then maturin develop, no warnings, abi3 wheel built)

$ python scripts/maturin_build.py develop --features stub-gen --manifest-path rust-bindings/Cargo.toml
warning: unused import: `PyType`
  --> rust-bindings/src/model/task_parameter.rs:40:35
   |
40 | use pyo3::types::{PyDict, PyList, PyType};
   |                                   ^^^^^^

$ scripts/generate_stubs.sh
Generated src/openjd/_openjd_rs.pyi
$ diff before.pyi src/openjd/_openjd_rs.pyi
(no diff)

$ cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets -- -D warnings
… clean (Finished `dev` profile [unoptimized + debuginfo] target(s))

$ hatch run test-subset test/openjd/model_v0
2306 passed in 5.24s

$ hatch run test-subset test/openjd/model_v1
905 passed in 3.78s    # before this evaluation
905 passed, 9 xfailed in 3.39s  # after the 9 xfails in test_known_gaps.py landed
```

The committed `_openjd_rs.pyi` matches what `pyo3-stub-gen` produces.
The full `hatch run test` (3211 tests) passes with 94% coverage.

## 7. Exploratory Findings

I ran the standard probes from the eval-bindings skill plus targeted
ones for the model surface:

1. **Pickle round-trip for every spec'd type**:
   `DocumentType`, `JobParameterType`, `TaskParameterType`,
   `ModelExtension`, `ModelProfile`, `CallerLimits`,
   `ValidationContext`, `JobParameterValue`, `TaskParameterValue`,
   the five typed task-parameter pyclasses, `TaskChunksDefinition`,
   `ChunkIntTaskParameter`, the three exception classes,
   `SpecificationRevision`, `TemplateSpecificationVersion` —
   **all 20 round-trip cleanly with `__eq__` returning True**
   (exceptions naturally compare unequal under Python's default
   semantics, but unpickle to the right class with the right
   message). ✓

2. **Validation error parity probe**: ran the same 5 invalid templates
   against v0 and v1 (missing schema version, invalid version, env
   version on job, empty steps, empty command, unsupported extension).
   Got the schema-version cases byte-identical, parameter constraint
   cases reworded but path-prefix-format preserved, exception class
   `DecodeValidationError` → `ModelValidationError` for the wrapping
   layer.

3. **Capability-validation parity**: confirmed the v0 / v1
   implementations behave the same on literal strings, expressions
   short-circuit (literal FormatString validates the raw form,
   non-literal short-circuits), reserved scopes get a vendor-prefix
   error, and the regex matches identically. ✓

4. **Job-time field probe**: walked every documented attr on
   `Job / Step / StepScript / StepActions / Action / Environment /
   EnvironmentScript / EnvironmentActions / EmbeddedFile / JobParameter`
   and compared with v0. Found the gaps documented in §5
   (host_requirements, runnable, end_of_line, JobParameter.type,
   Action.timeout type).

5. **`StepDependencyGraph` API probe**: found `max_indegree` /
   `max_outdegree` missing.

6. **`StepParameterSpaceIterator` API probe**: found
   `validate_containment` missing.

7. **Module-attribute probe** (`test_pyclass_modules.py` already
   covers this in tests): every Rust pyclass reports the right
   user-facing module under `__module__` / `__qualname__` / `repr`.
   All 100+ assertions pass.

8. **v0 isolation grep**: the three commands from the skill all
   return zero matches across `src/openjd/model/_v1/`,
   `rust-bindings/src/`, and `test/openjd/model_v1/`. ✓

9. **stub-gen diff**: regenerated `_openjd_rs.pyi` with
   `cargo run --bin stub_gen` (via `scripts/generate_stubs.sh`) and
   diffed against committed — zero diff. ✓

The 9 xfail tests landed in `test/openjd/model_v1/test_known_gaps.py`
cross-reference the Recommendations section below.

## 8. Recommendations

Numbered for the report-driven workflow. Resolve by striking through
with `~~ ... ~~ **Resolved.**` as items are addressed.

### P1 — Reference-parity gaps (job-time field coverage)

1. **Expose `JobParameter.type`** on the v1 binding as a getter that
   returns the `JobParameterType` enum (or, if the spec's "string spec
   name" preference for `param_type` is intentional, add a `.type`
   alias returning the same string). v0 callers, including `openjd-cli`
   (`hatch run python -c "from openjd.cli ..."`), read
   `param.type`. The current `param.param_type` getter alone breaks
   them silently. (`rust-bindings/src/model/job.rs::PyJobParameter`,
   `test/openjd/model_v1/test_known_gaps.py::test_job_parameter_has_type_alias`)

2. **Expose `Step.host_requirements` / `hostRequirements`** on the
   v1 job-time `PyStep`. The Rust `job::Step` struct already has the
   field; add a getter returning `Option<HostRequirements>` plus a
   camelCase alias, then update the spec's job-time `Step` example to
   list it. (`rust-bindings/src/model/job.rs::PyStep`,
   `specs/python-model-interface.md` job-time `Step` section,
   `test/openjd/model_v1/test_known_gaps.py::test_step_exposes_host_requirements`)

3. **Expose `EmbeddedFile.runnable`** on the v1 job-time
   `PyEmbeddedFile`. Field is in the Rust struct, exposed on
   template-time `PyEmbeddedFile`, and used by `openjd-sessions` to
   set the executable bit when materialising the file. Without it,
   v1-driven sessions cannot honour `runnable: True` from the
   template. (`rust-bindings/src/model/job.rs::PyEmbeddedFile`,
   `specs/python-model-interface.md` job-time `EmbeddedFile` section,
   `test/openjd/model_v1/test_known_gaps.py::test_embedded_file_exposes_runnable`)

4. **Expose `EmbeddedFile.endOfLine` / `end_of_line`** on the v1
   job-time `PyEmbeddedFile`. Same rationale as Rec #3 — the field
   is in the Rust struct and on the template-time pyclass, but the
   job-time pyclass omits it. Sessions need it to convert line
   endings before writing the file. (Same files as Rec #3,
   `test/openjd/model_v1/test_known_gaps.py::test_embedded_file_exposes_end_of_line`)

### P2 — Reference-parity gaps (smaller surface)

5. **Decide and document `JobParameter.description`**. v0 carries
   `description` from the parameter definition into the materialised
   `JobParameter`; the Rust `job::JobParameter` struct
   (`openjd-rs/crates/openjd-model/src/job/mod.rs`) doesn't. Either
   add the field upstream and expose it, or document the dropping
   rationale in the spec. (Rust crate + binding; not a v1-only fix.)

6. **Add `StepParameterSpaceIterator.validate_containment(params)`**.
   v0 exposes a method that raises a specific `ValueError` if `params`
   does not match a position in the iterator's space. v1 has the same
   underlying capability via `__contains__` but no equivalent of the
   structured-error variant. Implement as a thin wrapper over the
   Rust iterator's `contains()` plus a message-construction helper.
   (`rust-bindings/src/model/step_param_space.rs`,
   `test/openjd/model_v1/test_known_gaps.py::test_step_parameter_space_iterator_validate_containment`)

7. **Add `StepDependencyGraph.max_indegree` and `.max_outdegree`**
   properties. v0 callers (notably the dependencies-graph
   visualiser in `openjd-cli`) read these directly. Implement as
   `O(V)` walks over `_nodes` like the v0 reference. (`rust-bindings/
   src/model/step_dependency_graph.rs`,
   `test/openjd/model_v1/test_known_gaps.py::test_step_dependency_graph_max_degree_properties`)

8. **Reconcile `UnsupportedSchema` constructor with v0**. v0:
   `UnsupportedSchema(version_str)` produces
   `str(e) == "Unsupported schema version: {version_str}"` and
   exposes `e._version`. v1: `UnsupportedSchema(msg)` is a plain
   `ValueError` with whatever message Rust crafted. Either:
   (a) wrap the Rust message in the v0-style template string and
       expose `_version`; or
   (b) document the divergence in the spec's Exceptions section.
   Option (a) is friendlier for v0 callers but couples the binding
   to the v0 message format. (`rust-bindings/src/model/errors.rs`,
   `specs/python-model-interface.md` Exceptions section,
   `test/openjd/model_v1/test_known_gaps.py::test_unsupported_schema_constructor_parity`)

9. **Restore `TokenError → ExpressionError` inheritance**. v0
   defines `TokenError(ExpressionError)`, so `except ExpressionError`
   catches it. v1's wrapper module defines `TokenError(Exception)`
   directly. Fix: change `class TokenError(Exception)` →
   `class TokenError(ExpressionError)` in
   `src/openjd/model/_v1/__init__.py`, then update the spec's
   Exceptions table from `TokenError | Exception` to
   `TokenError | ExpressionError` (transitively `ValueError`).
   (`src/openjd/model/_v1/__init__.py`,
   `specs/python-model-interface.md` Exceptions section,
   `test/openjd/model_v1/test_known_gaps.py::test_token_error_inherits_expression_error`)

10. **Decide `Action.timeout` shape**. v0 returns `int` for integer
    timeouts and `FormatString` for format-string timeouts (under
    FEATURE_BUNDLE_1). v1 returns `str` (always — the FormatString's
    `raw()`). Either:
    (a) parse the raw form and return `int` when it matches `^\d+$`,
        otherwise the FormatString itself; or
    (b) return the FormatString object (matching template-time
        Action's shape) so callers can both read `.raw()` and
        `.resolve(...)` against it; or
    (c) keep returning `str` and document the divergence in the spec.
    The current shape is the strange middle ground: stringified, but
    not a FormatString. Recommend (b) for symmetry with template-time
    `Action.timeout` (`Optional[FormatString]`).
    (`rust-bindings/src/model/job.rs::PyAction::timeout`,
    `specs/python-model-interface.md` job-time Action section,
    `test/openjd/model_v1/test_known_gaps.py::test_action_timeout_int_round_trip`)

### P3 — Spec / build polish

11. **Document the `merge_job_parameter_definitions` return shape**.
    The spec example shows `merged = merge_job_parameter_definitions(...)`
    but doesn't specify the return type. v0 returns
    `list[JobParameterDefinition]`; v1 returns `list[dict]` with
    `name / type / default / source / objectType? / dataFlow?`.
    Either:
    (a) reshape the binding to return the typed definitions; or
    (b) document the dict shape in the spec with the
        rationale (the underlying Rust crate's
        `merge_job_parameter_definitions` returns a struct with
        `source`, `name`, `param_type`, `default`, `object_type`,
        `data_flow`; the v1 binding flattens it to a dict for the
        same reason `preprocess_job_parameters` returns a dict).
    Option (b) is consistent with the binding's existing dict
    output for `preprocess_job_parameters`.
    (`specs/python-model-interface.md`
    `merge_job_parameter_definitions` subsection,
    `rust-bindings/src/model/create_job_fns.rs::py_merge_job_parameter_definitions`)

12. **Remove the unused `PyType` import in `task_parameter.rs`**
    (line 40). The cfg-gated `use PyType as _;` workaround at line
    581 only suppresses the warning under `--no-default-features`;
    when stub-gen is enabled the warning fires. Either drop
    `PyType` from the import list and remove the `as _;` line, or
    invert the `cfg` predicate to apply when stub-gen *is*
    enabled. Today the `cargo build --features stub-gen` log is
    not fully clean. (`rust-bindings/src/model/task_parameter.rs`)

13. **Spec callout: "1 validation error" vs "1 validation errors"**
    and the "Parameter 'X': value Y exceeds maximum Z" vs "Value (Y)
    for parameter X must be at most Z." rewording in
    `ModelValidationError` / `DecodeValidationError` messages. The
    v0 reference's pluralisation typo and Pydantic-derived phrasing
    are not preserved; downstream tooling that matches messages
    exactly will break. The v1 messages are *better* (correct
    pluralisation, more concise) but a one-paragraph note in the
    spec's "Validation error format" subsection saying "messages
    are not byte-identical to v0 — match by exception class and
    field path, not the literal message" would help v0 callers
    migrate. (`specs/python-model-interface.md` — add a new
    "Migration notes" subsection or extend the existing
    Pydantic-vs-no-Pydantic discussion.)

14. **Spec gap: `StepDependencyGraph.step_node` accepts both
    positional and keyword `stepname`** in v1, but v0 is kw-only.
    The v1 superset is fine, but the spec should mention the
    accepted call shapes. Minor.
    (`specs/python-model-interface.md` `StepDependencyGraph` section)

15. **Spec gap: `SpecificationRevision.UNDEFINED` /
    `TemplateSpecificationVersion.UNDEFINED` removal**. v0 carried
    these "purely for internal testing" sentinels. v1 dropped both.
    Add a one-line note in the spec's Enums section so callers that
    pattern-match on the enum's `.values()` know to expect a smaller
    set.
    (`specs/python-model-interface.md` Enums subsection)
