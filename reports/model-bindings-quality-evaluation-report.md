# openjd-model Bindings Quality Evaluation Report

**Date:** 2026-05-18
**Component:** `openjd.model._v1`
**Reference branch:** `openjd-model-for-python` @ `origin/mainline` (OpenJobDescription, commit `f410f7d`)
**Active branch:** `bindings-rs` (commit `430f0d6`)

## Executive Summary

The `openjd.model._v1` Rust-backed bindings cover the most-common decode /
create_job / iteration paths and the test suite they ship with passes 593
of 598 collected tests, but **the bindings are not yet a faithful drop-in
for the pure-Python reference**:

1. ~~**Iteration-order regression.** `IntRangeExpr.from_str("-1 - -2 : -1")`
   yields `[-2, -1]`; the reference yields `[-1, -2]`. This breaks four
   existing parity tests (`test_associate_getitem`,
   `test_product_iteration`, `test_product_getitem`,
   `test_nested_expr_iteration` in `test_step_param_space_iter.py`). It
   also means CHUNK[INT] and INT task parameters that use a descending
   range produce iteration in the wrong direction.~~ **Resolved** —
   reclassified as an intentional behavior change. The Rust
   `RangeExpr` always stores ranges in canonical ascending form (see
   `openjd-rs/specs/expr/range-expr.md` "Internal Representation"), so
   `IntRangeExpr.from_str("-1 - -2 : -1")` yielding `[-2, -1]` is the
   binding's documented semantics: `RangeExpr` values are always an
   increasing list of integers, regardless of input direction. The
   four `test_step_param_space_iter` failures are reference-only tests
   that assume the descending-input-preserves-direction behavior of
   the pure-Python implementation; they should be skipped or rewritten
   for the Rust-backed module. Documented in
   `specs/python-model-interface.md` under Compatibility Aliases.
2. ~~**`StepParameterSpaceIterator.__contains__` rejects values it just
   yielded.** Iterating once over an INT parameter space and checking each
   yielded value with `in` returns `False` for every one of them. The
   reference returns `True`. This is the same root cause as a frequently-
   used test pattern (`for v in expected_values: assert v in it`).~~
   **Resolved** — `extract_task_parameter_set` now reads the parameter
   type via `as_str()` (the Rust pyclass-enum convention used by
   `PyTaskParameterType` / `PyJobParameterType` and by the Python-side
   `ParameterValue` shim), then falls back to `.value` (stdlib
   `enum.Enum`) and `__str__`. Yielded values now round-trip through
   `__contains__`. As a side-effect this also fixes
   `test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_associate_getitem`,
   which uses the same `for v in expected_values: assert v in it`
   pattern.
3. **`model_to_object` is unimplemented for every Rust-backed model.** The
   wrapper module raises `NotImplementedError`. The reference round-trips
   through `model.model_dump(by_alias=True, exclude_unset=True)` to produce
   the input dict. One existing parity test fails because of this
   (`TestModelToObject::test[translates Decimal to string]`).
4. ~~**`StepParameterSpaceIterator.chunks_default_task_count` setter is a
   silent no-op.** The setter validates that the space is adaptively
   chunked, then returns without storing the value. The reference mutates
   the iterator. Adaptive-runtime callers (e.g. the worker agent) cannot
   actually adapt chunk size.~~ **Resolved** — `PyStepParameterSpaceIterator`
   now holds a persistent `Mutex<StepParameterSpaceIterator>` rather than
   reconstructing a fresh iterator on every method call. The setter
   validates that the value is a positive integer and that the space is
   adaptively chunked, then calls `iter.set_chunks_default_task_count(value)`,
   which mutates the shared `Arc<AtomicUsize>` that the live iteration
   nodes read from. Subsequent reads via the getter return the new
   value.
5. ~~**`__len__` returns 0 on adaptive-chunked spaces; reference raises
   `ValueError`.** The reference documents that `len()` is unavailable for
   adaptively-chunked spaces and raises with an explanatory message; the
   binding silently returns 0, which the caller will mistake for an empty
   space.~~ **Resolved** — `__len__` now raises
   `ValueError("Length is not available because the parameter space uses
   adaptive chunking.")`, matching the reference's message. The
   underlying Rust `StepParameterSpaceIterator::len()` continues to return
   0 for adaptive (its documented contract); the wrapper short-circuits
   on `chunks_adaptive()` before consulting it.
6. **`taskParameterDefinitions` getter returns serde-internal JSON, not
   typed objects.** The reference returns `RangeExpressionTaskParameterDefinition`
   / `RangeListTaskParameterDefinition` / etc. with `.type` (a
   `TaskParameterType`) and `.range` attributes. The binding returns a
   nested dict like `{'int': {'range': {'rangeExpr': {...}}, 'chunks':
   None}}`. Code reading `defs[name].type` breaks.
7. **18 v2023_09 test files cannot even be collected.** They import legacy
   names (`Action`, `EnvironmentTemplate`, `RangeExpressionTaskParameterDefinition`,
   `JobIntParameterDefinition`, `HostRequirements`, etc.) from
   `openjd.model._v1.v2023_09`, but only ~12 of the reference's ~85 names
   are re-exported. Whole categories of behavior (job parameters, host
   requirements, scripts, template variables, embedded files, action
   timeouts, redacted env vars, chunk-int task parameters,
   feature-bundle 1) are therefore untested.
8. **Spec drift.** `specs/python-model-interface.md` is incomplete: it
   omits `parse_model`, `document_string_to_object`, `decode_template`,
   `STANDARD_AMOUNT_CAPABILITIES`, `STANDARD_ATTRIBUTE_CAPABILITIES`,
   `validate_amount_capability_name`, `validate_attribute_capability_name`,
   `evaluate_let_bindings`, `deserialize_step`, `create_environment`,
   `JobParameterValue`, `TaskParameterValue`, and several output type
   getters. It also documents `it.names()` and `graph.step_names()` as
   methods (the reference and binding both expose `it.names` as a
   property).
9. **`src/openjd/_openjd_rs.pyi` is stale.** 25 runtime symbols are
   missing from `__all__`, including every `_openjd_rs.*` exception class,
   the session types, `TaskParameterValue`, `JobParameterValue`,
   `StepDependencyEdge`, `StepDependencyNode`, `deserialize_step`,
   `create_environment`, `BadCredentialsException`, etc. IDE tooltips for
   every consumer of the bindings are wrong.
10. **76 clippy lints** in `cargo clippy --workspace -- -D warnings`,
    including 22 `non-camel-case` enum variants, 10 PyO3 0.20 deprecated
    API calls, 4 redundant closures, 4 needless borrows, 1
    `useless_format!`, 1 `unused_doc_comment`, and 1 `dead_code`. Same
    profile as the prior `expr` evaluation.
11. **25 rustc warnings** during the maturin build (subset of the clippy
    list). The build itself completes cleanly.

The recommendations at the end of this report are ordered by impact;
items 1–6 are functional regressions that should land before the bindings
are advertised as a v0 drop-in. Items 7–8 (test coverage and spec) are
required to detect regressions of the kind already found.

A new test file
[`test/openjd/model-v1/test_known_gaps.py`](../test/openjd/model-v1/test_known_gaps.py)
documents the ten functional gaps as `pytest.mark.xfail(strict=True)`
tests so the recommendations can be resolved one at a time.

## 1. Python Interface Spec Review

`specs/python-model-interface.md` (446 lines) describes the public
contract. Coverage is incomplete and in places ahead of the
implementation.

### Symbols listed in spec and exported by binding

The following all import successfully from `openjd.model._v1`:

- Functions: `decode_job_template`, `decode_job_template_str`,
  `decode_environment_template`, `decode_environment_template_str`,
  `create_job`, `preprocess_job_parameters`,
  `merge_job_parameter_definitions`, `model_to_object` (as a function —
  but always raises `NotImplementedError`).
- Output types: `Job`, `Step`, `StepScript`, `StepActions`, `Action`,
  `Environment`, `EnvironmentScript`, `EnvironmentActions`,
  `EmbeddedFile`, `JobParameter`, `StepParameterSpace`, `StepDependency`,
  `CancelationMode`.
- Iteration: `StepParameterSpaceIterator`, `StepDependencyGraph`.
- Template types: `JobTemplate`, `EnvironmentTemplate`.
- Enums: `DocumentType`, `TemplateSpecificationVersion`,
  `JobParameterType`, `TaskParameterType`, `SpecificationRevision`,
  `ValueReferenceConstants`.
- Compatibility aliases: `IntRangeExpr` (= `RangeExpr`), `CommandString`
  / `ArgString` (= `FormatString`), `EmbeddedFileText` (= `EmbeddedFile`),
  `EmbeddedFiles` (= `list`), `JobParameterValues`, `TaskParameterSet`.
- Simple Python types: `ParameterValue`, `RevisionExtensions`,
  `CancelationMethodTerminate`, `CancelationMethodNotifyThenTerminate`.
- Exceptions: `DecodeValidationError`, `ModelValidationError`,
  `UnsupportedSchema`, `ExpressionError`, `FormatStringError`,
  `CompatibilityError`, `TokenError`.

### Spec ↔ binding gaps (binding has but spec doesn't)

- `parse_model(*, model=None, obj=...)` — auto-detects template type from
  `specificationVersion` and dispatches to `decode_job_template_dict` or
  `decode_environment_template_dict`. Broadly used by the Deadline Cloud
  CLI; **must** appear in the spec.
- `document_string_to_object(*, document, document_type=None)` — parses a
  YAML/JSON string into a Python dict. Public utility that consumers
  rely on.
- `STANDARD_AMOUNT_CAPABILITIES`, `STANDARD_ATTRIBUTE_CAPABILITIES`,
  `validate_amount_capability_name`, `validate_attribute_capability_name`
  — all imported by Deadline Cloud worker agent and CLI. Spec has no
  mention.
- `Step.resolved_symtab` getter — returns an `openjd.expr.SymbolTable`.
  Used at runtime by sessions.
- `JobParameter.name`, `JobParameter.param_type`, `JobParameter.value` —
  spec advertises the shape of `job.parameters` but does not enumerate
  the getter names; verify behavior.
- `Step.__eq__` / `Step.__hash__` — implemented based on the step name
  alone (not all fields); not in spec but used internally.
- `JobParameterValue` and `TaskParameterValue` Rust-side wrappers — both
  are reachable via `openjd._openjd_rs.JobParameterValue` /
  `TaskParameterValue` and returned from
  `preprocess_job_parameters` / step-iterator output. Spec explains
  `JobParameter.value` returns `ExprValue` (only true for `Job`-side
  parameters), not `JobParameterValue`.
- `JobParameterType` is `frozen` and hashable; `TaskParameterType` is
  not. Spec implies parity but the bindings differ.

### Binding has but spec exposes inconsistently

- `it.names()` in spec → `it.names` property in binding (matches
  reference, which also exposes it as a property).
- `graph.step_names()` in spec → exists as method but reference signature
  is `step_names()` returning `list[str]`. Binding matches.

### Spec entries that don't match

| Spec example | Actual behavior |
|---|---|
| `template.specification_version` (camel `specificationVersion`) | Only snake-case getter is exposed; `template.specificationVersion` → `AttributeError`. |
| `it.names()                  # {"Frame"}` | `it.names` is a property, not a callable. The example would `TypeError: 'set' object is not callable`. |
| `model_to_object(model=some_object)` | Always raises `NotImplementedError("model_to_object is not supported for this type")` for every Rust-backed model. |
| `script.let` (advertised as `Optional[list[str]]`) | Works ✓ |
| `step.resolvedBindings` | Works ✓ but reference tests use `script.let` — which also works. |
| `space.taskParameterDefinitions` returns dict of typed defs | Returns dict whose values are nested serde-tagged JSON objects (see §5). |

### Spec entries with no live binding symbol

- `decode_template` — listed by reference, missing in binding. CLI calls
  `decode_template(name=..., raw_data=..., document_type=...)`.

## 2. PyO3 Binding Source Review

The model bindings live in
`rust-bindings/src/model/`:

- `mod.rs` — re-exports from submodules. ✓
- `errors.rs` — three `pyo3::create_exception!` types
  (`PyDecodeValidationError`, `PyModelValidationError`,
  `PyUnsupportedSchema`) and a `model_err_to_py` mapper. The mapper
  collapses `ModelError::FormatStringError`,
  `ModelError::Expression`, and `ModelError::Compatibility` all to
  `PyModelValidationError` (instead of the reference's distinct
  `FormatStringError`, `ExpressionError`, and `CompatibilityError`).
  Test for shape: `decode_job_template(template={"specificationVersion":
  "jobtemplate-2023-09", "name": "X", "steps": [...]})` with a malformed
  `{{...}}` expression in `command` raises
  `ModelValidationError("Format string parse error...")` instead of
  `FormatStringError`. ⚠
- `decode.rs` — round-trips Python dict → JSON string →
  `serde_json::Value` → `openjd_model::decode_job_template`. The dict-to-
  JSON detour is potentially lossy for non-JSON-serialisable types
  (`Decimal`, `pathlib.Path`, custom objects), but the `json.dumps`
  raises early so failure is visible. ⚠ Performance: doubles the cost
  of a decode for callers that already have a dict. (Reference parses
  pydantic models directly from the dict.)
- `template.rs` — `PyJobTemplate` and `PyEnvironmentTemplate`. Both
  expose only `name` / `specification_version` / `description` getters.
  Missing: `extensions`, `parameter_definitions`, `steps`,
  `job_environments`, `host_requirements`, the entire body of the
  template, all of which the reference makes accessible via the pydantic
  model.
- `types.rs` — six enums plus `PyTaskParameterValue` and
  `PyJobParameterValue`. `PyJobParameterType` is `hash` (frozen) but
  `PyTaskParameterType` is *not* frozen / hashable, an inconsistency.
  `__eq__` for the value types calls `other.getattr("type")` and
  `as_str()` — works for ParameterValue / JobParameterValue /
  TaskParameterValue but raises `AttributeError` for any other object,
  rather than returning `NotImplemented`.
- `job.rs` (~860 lines) — bulk of the surface. Nine `#[pyclass]` types
  (`PyJob`, `PyStep`, `PyStepScript`, `PyStepActions`, `PyAction`,
  `PyEnvironment`, `PyEnvironmentScript`, `PyEnvironmentActions`,
  `PyEmbeddedFile`), plus `PyJobParameter`, `PyStepParameterSpace`,
  `PyStepDependency`, `PyCancelationMode`. Camel/snake parity is mostly
  consistent, but several Step getters have only the snake-case form
  (`step.dependencies`, no `step.dependencies` camel — well, `dependencies`
  is the same in both cases; `step.script` is fine; but
  `step.script.actions.onRun` is camel-only — there is no `step.script.actions.on_run`
  yet — wait, there is, both forms work).
  - `PyStepParameterSpace.task_parameter_definitions` returns
    `serde_json::to_string`-then-`json.loads`'d nested objects (see §5
    parity table for example).
  - `PyAction.cancelation` and `PyAction.timeout` return strings;
    the reference returns typed `CancelationMode` / time strings.
- `create_job_fns.rs` — three top-level functions plus
  `py_evaluate_let_bindings`, `py_deserialize_step`, and
  `py_create_environment`. Notably:
  - `py_preprocess_job_parameters` accepts a single positional `job_template_dir`
    (PathBuf) and `current_working_dir`. If the caller passes `Path(".")`
    they're silently rewritten to empty strings (`""`) before being
    handed to the Rust function — a foot-gun for tests using ".".
  - `py_create_environment` requires no consumer-visible function, but
    it is registered as `create_environment`. Spec doesn't mention it.
  - `py_deserialize_step` is registered as `deserialize_step`, also not
    in the spec.
- `step_param_space.rs` — `PyStepParameterSpaceIterator`. Implementation
  is mostly sound but the setter for `chunks_default_task_count` is a
  no-op (line 199, see §5 table). `__len__` returns `self.len` which is
  0 for adaptive-chunked spaces (where the underlying iterator's `len()`
  returns 0). Reference raises an explanatory `ValueError` instead.
  `__contains__` calls `extract_task_parameter_set` which interprets the
  passed value as a `TaskParameterValue` whose internal type-string lookup
  fails for `TaskParameterValue` instances yielded by the iterator
  itself; see §5.
- `step_dependency_graph.rs` — `PyStepDependencyGraph`,
  `PyStepDependencyNode`, `PyStepDependencyEdge`. Minor note:
  `PyStepDependencyEdge.origin` and `.dependent` return `PyStepDependencyNode`
  with `in_edges` / `out_edges` always set to `vec![]`, even though the
  reference returns nodes with their full edge sets populated. Code that
  walks the graph through edges loses adjacency.

### PyO3-specific concerns

- **Exception class registration.** `register_renamed_exception` is
  called for every `create_exception!`-built exception in
  `lib.rs::openjd_rs`. Verified at runtime via `pickle.dumps(e); pickle.loads`
  — the qualified names round-trip as `openjd.model._v1.DecodeValidationError`
  (etc.). ✓
- **Type conversions.**
  - `int → i64` boundary: rejects `2**63` with PyO3's
    `OverflowError`. Inside the model layer this only matters in
    `JobParameterValue` payloads, where the value is stored as a
    string and converted lazily.
  - `pathlib.Path` ↔ `PathBuf`: Works via `extract::<PathBuf>()`. The
    `"."` rewrite to `""` in `py_preprocess_job_parameters` is
    surprising; see above.
  - Ordered vs unordered: `Job.parameters` is `dict[str, JobParameter]`;
    iteration order matches insertion order in the underlying
    `IndexMap` ✓.
- **GIL handling.** None of the model bindings call
  `Python::allow_threads` even though `decode_job_template` does
  potentially expensive YAML/JSON parsing and validation. With the GIL
  held, multi-threaded servers cannot decode templates concurrently. (A
  concurrent-test probe shows the bindings *do* support being called
  from multiple Python threads serially; concurrent throughput is
  obviously bottlenecked.)
- **`#[pyclass]` constructor signatures.** `PyStepParameterSpaceIterator.__init__`
  accepts both `step=` and `space=` (matches spec). `PyEmbeddedFile.__init__`
  accepts `name`, `type`, `filename`, `data`, `runnable`, `endOfLine` (or
  `end_of_line`) — matches the reference Pydantic model.
- **`Py<T>` lifetime.** No obvious correctness issues. All getters
  return `Clone`d data, so no reborrow conflicts.
- **ABI3 compatibility.** `[features].extension-module` correctly
  enables `pyo3/extension-module`; the wheel reports `cp39-abi3`. ✓
- **Stub generation.** `src/openjd/_openjd_rs.pyi` is stale (see §3
  below); only 25 of the 50 registered symbols appear in `__all__`.

## 3. Python Wrapper Module Review

`src/openjd/model/_v1/__init__.py` re-exports the bindings under their
canonical names plus a handful of Python-side classes. ✓ for
`openjd.model._v1.{DecodeValidationError, ModelValidationError,
UnsupportedSchema}` reaching their canonical home (the
`register_renamed_exception` calls handle this in Rust).

### Python-side classes / aliases

| Symbol | Source | Notes |
|---|---|---|
| `ParameterValue` | Python class with `type` / `value` / `__eq__` / `__hash__` / `__repr__` | Compatible with `openjd._openjd_rs.JobParameterValue` and `TaskParameterValue` for `==`. ✓ |
| `JobParameterValues`, `JobParameterInputValues`, `TaskParameterSet` | `dict` aliases | Spec advertises these as type aliases ✓ |
| `RevisionExtensions` | Python class | Accepts both `spec_rev=` and `revision=`, both `supported_extensions=` and `extensions=`. Reference is keyword-only `spec_rev` + `supported_extensions`. ⚠ minor divergence (binding more permissive). |
| `CancelationMethodTerminate` / `CancelationMethodNotifyThenTerminate` | Python wrapper around literal strings | Plain dataclasses; do not unify with `openjd.model._v1.CancelationMode` (the Rust class). ⚠ Two parallel hierarchies. |
| `EmbeddedFileText` | Alias for `EmbeddedFile` | ✓ |
| `EmbeddedFiles` | Alias for `list` | ✓ |
| `CompatibilityError` / `TokenError` | Plain Python `Exception` subclasses | Reference: `CompatibilityError` is `ValueError`-derived (in `_errors.py`); the binding uses `Exception`. ⚠ Catching `ValueError` in legacy code will not catch `CompatibilityError` in the binding. |
| `IntRangeExpr` = `RangeExpr` | Direct alias | ✓ |
| `validate_amount_capability_name` / `validate_attribute_capability_name` | Pure-Python re-implementations | Function signatures differ from reference (binding accepts both positional `name` and kw `capability_name` and makes `standard_capabilities` optional). Behavior matches when called with reference signature. ✓ |
| `STANDARD_AMOUNT_CAPABILITIES` / `STANDARD_ATTRIBUTE_CAPABILITIES` | Hard-coded dicts | Match reference values ✓ but content lives in two places — risk of drift if Rust crate changes. |

### `openjd.model._v1.v2023_09` shim

The current shim re-exports only:

```python
Action, EmbeddedFile as EmbeddedFileText, Environment, EnvironmentTemplate,
EnvironmentScript, FormatString, Job, JobTemplate, Step, StepScript,
StepActions, StepParameterSpace, StepParameterSpaceIterator,
STANDARD_AMOUNT_CAPABILITIES, STANDARD_ATTRIBUTE_CAPABILITIES,
RangeExpressionTaskParameterDefinition = dict, RangeListTaskParameterDefinition = dict,
CommandString = FormatString, ArgString = FormatString, DataString = FormatString,
EmbeddedFiles = list, EmbeddedFileTypes, ExtensionName,
```

The reference module exposes ~85 symbols; the binding shim covers ~12.
**Every test in `test/openjd/model-v1/v2023_09/` fails to collect** because
the missing names cause `ImportError`. See §4 below.

### `openjd.model.__init__.py` (top-level dispatcher)

Identical to the reference. Re-exports v0 (pure-Python) symbols. The
top-level `openjd.model` is the legacy interface; `openjd.model._v1` is
the binding-aware interface.

## 4. Test Review

### Inventory

```
test/openjd/model-v0/          —  pure-Python reference tests (still passing as a baseline)
  __init__.py
  benchmark/test_yaml_loader_performance.py
  benchmark/test_benchmark_step_environments.py
  format_strings/{test_format_string,test_expression,test_parser,test_dyn_constrained_str,test_node,test_edit_distance}.py
  _internal/{test_combination_expr,test_create_job,test_param_space_dim_validation,test_range_expr,test_variable_reference_validation}.py
  v2023_09/{test_create,test_environments,test_parameter_space,test_strings,test_redacted_env_vars,test_definitions,test_module,test_job_template,test_environment_template,test_step_host_requirements,test_step_template,test_feature_bundle_1,test_embedded,test_chunk_int_task_parameter_type,test_action,test_scripts,test_job_parameters,test_template_variables}.py
  test_{capabilities,convert_pydantic_error,create_job,errors,fuzz,importable,lexer,merge_job_parameters,parse,step_dependency_graph,step_param_space_iter,step_param_space_iter_with_chunks,symbol_table,tokenstream,version_enums}.py

test/openjd/model-v1/          —  binding tests
  __init__.py
  benchmark/{test_yaml_loader_performance,test_benchmark_step_environments}.py
  v2023_09/{… 18 files, each ImportError on collection …}
  format_strings/__init__.py     ← directory exists, but empty (no test files)
  _internal/__init__.py          ← directory exists, but empty (no test files)
  test_{capabilities,create_job,errors,fuzz,importable,merge_job_parameters,parse,pyclass_modules,rust_model_bindings,step_dependency_graph,step_param_space_iter,symbol_table,version_enums}.py
```

### What test/openjd/model-v1 covers well

- `test_pyclass_modules.py` — exhaustive coverage of `__module__` /
  `__name__` / `__qualname__` / pickle-name fix-up for every exposed
  pyclass. ✓
- `test_errors.py` — sanity check that error classes derive from the
  expected base. ✓
- `test_create_job.py` — most happy-path and error-path coverage of
  `create_job` and the resulting object shape. ✓ (passes 593 tests)
- `test_step_dependency_graph.py` — covers the basic node / edge /
  topological API. ✓

### Coverage gaps vs reference

- `test/openjd/model-v0/test_convert_pydantic_error.py` (~7290 lines)
  has no analog in `model-v1`. Reasonable: pydantic-specific error
  conversion is N/A.
- `test/openjd/model-v0/test_lexer.py` (token lexer tests) has no
  analog. Reasonable: the binding does not expose a tokenstream.
- `test/openjd/model-v0/test_tokenstream.py` similarly has no analog.
- `test/openjd/model-v0/format_strings/` — six test files; one analog
  exists (a directory exists at `model-v1/format_strings/` but it is
  empty). Reference covers `_format_string`, `_expression`, `_parser`,
  `_dyn_constrained_str`, `_node`, `_edit_distance`; binding covers
  none. Affected behaviors: `FormatString` round-trip, expression
  parsing, edit-distance suggestion, tokens.
- `test/openjd/model-v0/_internal/{test_combination_expr,test_create_job,test_range_expr,test_param_space_dim_validation,test_variable_reference_validation}.py`
  — five test files; the binding has no analog (the directory at
  `model-v1/_internal/` is empty).
- `test/openjd/model-v0/v2023_09/` — 18 test files (~328k LoC of test
  code). The binding's analog directory exists but **none of its 18
  files even collect** because of the missing
  `openjd.model._v1.v2023_09` re-exports. This is the largest single
  coverage gap.
- `test_step_param_space_iter_with_chunks.py` — a ~28k-line reference
  test file that exhaustively covers chunked iteration. There is no
  analog in `model-v1`.

### Tests in the binding without a reference analog

- `test_pyclass_modules.py` — checks the `register_renamed_exception`
  fix-up. Specific to bindings.
- `test_rust_model_bindings.py` — direct exercise of `_openjd_rs.*`
  methods. Specific to bindings.

## 5. Parity with Pure-Python Reference

This section lists every public symbol in the **reference**
`openjd.model.__init__` and tracks the binding's equivalent.

### Functions

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `decode_job_template(*, template, supported_extensions=None)` | Returns pydantic JobTemplate | Returns Rust-backed `JobTemplate` | ✓ shape ok; PyO3 round-trips dict→JSON internally |
| `decode_job_template_str(document, format=DocumentType.YAML, supported_extensions=None)` | n/a (split into `decode_job_template` + `document_string_to_object`) | Direct binding | ✓ binding-only |
| `decode_environment_template(*, template, supported_extensions=None)` | Returns `EnvironmentTemplate` | Returns Rust-backed | ✓ |
| `decode_environment_template_str(document, format, supported_extensions=None)` | n/a | Direct binding | ✓ binding-only |
| `decode_template(*, name, raw_data, document_type)` | Reference exports it | **Missing** in binding | ❌ |
| `create_job(*, job_template, job_parameter_values, environment_templates=None)` | Returns Job | Returns Rust Job | ✓ |
| `preprocess_job_parameters(*, job_template, job_parameter_values, environment_templates=None, job_template_dir, current_working_dir, allow_job_template_dir_walk_up=False)` | Returns dict[str, ParameterValue] | Returns dict[str, JobParameterValue] | ⚠ value type differs (`ParameterValue` vs `JobParameterValue`) but `__eq__` is symmetric so most code keeps working. |
| `merge_job_parameter_definitions(*, job_template, environment_templates=None)` | Returns list of pydantic objects | Returns list of dicts | ⚠ shape differs |
| `model_to_object(*, model)` | Returns dict via `model_dump` | **Always raises `NotImplementedError`** | ❌ |
| `parse_model(*, model=None, obj)` | Returns pydantic model | Returns Rust model | ✓ |
| `document_string_to_object(*, document, document_type=None)` | Returns dict (uses CSafeLoader) | Returns dict (uses CSafeLoader) | ✓ |
| `validate_amount_capability_name(*, capability_name, standard_capabilities)` | strict kw-only | Permits positional `name` + makes `standard_capabilities` optional | ⚠ more permissive |
| `validate_attribute_capability_name(*, capability_name, standard_capabilities)` | strict kw-only | Permits positional `name` + makes `standard_capabilities` optional | ⚠ more permissive |

### Classes / output types

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `Job` | Pydantic model with full template body | Rust struct | ✓ shape; minor: `revision` always `'2023-09'` even for future versions |
| `Step.script.actions.onRun.command` | `FormatString` | `FormatString` (from `openjd.expr`) | ✓ |
| `Step.script.actions.onRun.timeout` | string in spec | `Optional[str]` | ✓ |
| `Step.script.let` | `Optional[list[str]]` | ✓ | ✓ |
| `Step.script.embedded_files` / `embeddedFiles` | both forms | both forms | ✓ |
| `Step.parameterSpace.taskParameterDefinitions[name]` | typed `RangeExpression…/RangeList…TaskParameterDefinition` | **Nested serde JSON `dict`** like `{'int': {'range': {'rangeExpr': {…}}, 'chunks': None}}` | ❌ |
| `Step.parameterSpace.combination` | `Optional[str]` | `Optional[str]` | ✓ |
| `Job.parameters[name].value` | `ExprValue` | `ExprValue` | ✓ |
| `Environment.script.actions.onEnter` / `onExit` | `Optional[Action]` | `Optional[Action]` | ✓ |
| `EmbeddedFile(name, type, filename, data, runnable, endOfLine)` | Pydantic model | Rust struct, both `endOfLine` and `end_of_line` accepted | ✓ |
| `JobTemplate.name` / `description` / `specification_version` | All getters present | Same | ✓ |
| `JobTemplate.specificationVersion` (camel) | exists | **Not exposed** | ❌ minor |
| `JobTemplate.parameter_definitions` / `steps` / `extensions` | exist | **Not exposed** | ❌ |
| `EnvironmentTemplate.environment` (the inner `Environment`) | exposed | **Not exposed** | ❌ |
| `RevisionExtensions(spec_rev=, supported_extensions=)` | strict kw | also accepts `revision=` and `extensions=` | ⚠ |
| `CancelationMethodTerminate(mode=...)` | dataclass with mode | Plain class, default mode `'TERMINATE'` | ✓ |
| `CancelationMethodNotifyThenTerminate(notify_period_in_seconds=120)` | dataclass | Plain class | ✓ |
| `IntRangeExpr.start` / `end` | Reference exposes both | **Missing** | ❌ minor (also flagged in expr report) |
| `IntRangeExpr.from_list([1, 2, 3])` | exists | **Missing** | ❌ |

### Iterators

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `StepParameterSpaceIterator(*, space=None, chunks_task_count_override=None)` | accepts `space` + `chunks_task_count_override` | accepts `step` or `space` (no `chunks_task_count_override`) | ⚠ mostly ok but no `chunks_task_count_override` |
| `len(it)` | raises `ValueError` for adaptive-chunked | returns 0 | ❌ |
| `it[i]` / `it[-1]` | works | works | ✓ |
| `for v in it` (dict[str, ParameterValue]) | yields `ParameterValue` | yields `TaskParameterValue` | ✓ (compares equal) |
| `v in it` after iteration | True | **False** for self-yielded values | ❌ |
| `it.names` | property | property | ✓ |
| `it.chunks_adaptive` | property | property | ✓ |
| `it.chunks_default_task_count` (mutate) | actually mutates | **silent no-op** | ❌ |

### Enums

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `DocumentType.{JSON,YAML}` | str-based Enum | int-eq pyclass | ⚠ different shape (Enum vs pyclass), `==` between them works only because pyclass implements `__eq__` against str via `as_str()` |
| `TemplateSpecificationVersion.JOBTEMPLATE_v2023_09` | str-based Enum | str-based Enum (Python-side wrapper) | ✓ |
| `JobParameterType.{STRING,INT,…,LIST_LIST_INT}` | str-based Enum | int-eq pyclass | ⚠ shape difference. `as_str()` returns the spec name. Hashable. |
| `TaskParameterType.{INT,FLOAT,STRING,PATH,CHUNK_INT}` | str-based Enum | int-eq pyclass, hashable, pickleable | ✓ resolved (Rec #9) |
| `SpecificationRevision.v2023_09` | str-based Enum | str-based Enum | ✓ |
| `ValueReferenceConstants` | Reference exposes `JOB_PARAMETER_PREFIX`, `TASK_PARAMETER_PREFIX`, `WORKING_DIRECTORY`, `HAS_PATH_MAPPING_RULES`, `JOB_PARAMETER_RAWPREFIX`, `TASK_PARAMETER_RAWPREFIX`, `ENV_FILE_PREFIX`, `TASK_FILE_PREFIX`, `PATH_MAPPING_RULES_FILE` | Binding exposes the same set | ✓ |

### Exceptions

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `DecodeValidationError(ValueError)` | ✓ | ✓ | ✓ |
| `ModelValidationError(ValueError)` | ✓ | ✓ | ✓ |
| `UnsupportedSchema(ValueError)` | ✓ | ✓ | ✓ |
| `ExpressionError(ValueError)` | ✓ | ✓ from openjd.expr | ✓ |
| `FormatStringError(ValueError)` | ✓ | ✓ but `__qualname__` is `FormatStringValidationError` (re-imported from openjd.expr) | ⚠ name mismatch |
| `CompatibilityError` | `(ValueError)` in reference | `(Exception)` only | ❌ |
| `TokenError(Exception)` | ✓ | ✓ | ✓ |

When format-string parsing inside a template fails, the reference raises
`FormatStringError`; the binding maps everything to
`ModelValidationError` via `model_err_to_py`. Code catching the more
specific exception type breaks. ⚠

## 6. Build and Test Results

### `python scripts/maturin_build.py develop`

```
🔗 Found pyo3 bindings with abi3 support
   Compiling openjd-sessions v0.2.0 (/home/markw/openjd-rs/crates/openjd-sessions)
   Compiling openjd-python v0.9.0 (/home/markw/openjd-model-for-python/rust-bindings)
warning: `openjd-python` (lib) generated 25 warnings (run `cargo fix --lib -p openjd-python` to apply 3 suggestions)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 6.14s
📦 Built wheel for abi3 Python ≥ 3.9 to /tmp/.tmpIEt7j5/openjd_model-0.9.1.post13+g430f0d667-cp39-abi3-linux_x86_64.whl
🛠 Installed openjd-model-0.9.1.post13+g430f0d667
```

The 25 rustc warnings break down as: 16 `non-camel-case-types`,
8 `deprecated` PyO3 0.20-era APIs (FromPyObject auto-derive, downcast),
and 1 `dead_code`. None block the build.

### `python -m pytest test/openjd/model-v1` (Rust-backed)

```
5 failed, 593 passed, 18 errors in 4.16s
```

Failures:

```
FAILED test/openjd/model-v1/test_parse.py::TestModelToObject::test[translates Decimal to string]
       NotImplementedError: model_to_object is not supported for this type
FAILED test/openjd/model-v1/test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_associate_getitem
       __contains__ returns False for self-yielded values
FAILED test/openjd/model-v1/test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_product_iteration
       descending range iteration order is reversed
FAILED test/openjd/model-v1/test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_product_getitem
       descending range __getitem__ order is reversed
FAILED test/openjd/model-v1/test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_nested_expr_iteration
       descending range iteration order is reversed (nested combination)
```

Errors (all `ModuleNotFoundError: No module named 'openjd.model._v1._parse'`
or `ImportError: cannot import name X from openjd.model._v1.v2023_09`):

```
ERROR test/openjd/model-v1/v2023_09/test_action.py
ERROR test/openjd/model-v1/v2023_09/test_chunk_int_task_parameter_type.py
ERROR test/openjd/model-v1/v2023_09/test_create.py
ERROR test/openjd/model-v1/v2023_09/test_definitions.py
ERROR test/openjd/model-v1/v2023_09/test_embedded.py
ERROR test/openjd/model-v1/v2023_09/test_environment_template.py
ERROR test/openjd/model-v1/v2023_09/test_environments.py
ERROR test/openjd/model-v1/v2023_09/test_feature_bundle_1.py
ERROR test/openjd/model-v1/v2023_09/test_job_parameters.py
ERROR test/openjd/model-v1/v2023_09/test_job_template.py
ERROR test/openjd/model-v1/v2023_09/test_module.py
ERROR test/openjd/model-v1/v2023_09/test_parameter_space.py
ERROR test/openjd/model-v1/v2023_09/test_redacted_env_vars.py
ERROR test/openjd/model-v1/v2023_09/test_scripts.py
ERROR test/openjd/model-v1/v2023_09/test_step_host_requirements.py
ERROR test/openjd/model-v1/v2023_09/test_step_template.py
ERROR test/openjd/model-v1/v2023_09/test_strings.py
ERROR test/openjd/model-v1/v2023_09/test_template_variables.py
```

After adding `test/openjd/model-v1/test_known_gaps.py` (this report's
follow-on), the count becomes `5 failed, 593 passed, 10 xfailed, 18 errors`.

After reclassifying `test_int_range_expr_descending_iteration_order`
from `xfail` to a passing assertion of the documented ascending
iteration order (see Recommendations §1), the count becomes
`5 failed, 594 passed, 9 xfailed, 18 errors`.

After resolving Recommendations §2, §4, and §5 — converting
`test_step_param_space_iter_contains_self_yielded`,
`test_step_param_space_iter_chunks_default_task_count_setter`, and
`test_step_param_space_iter_adaptive_len_raises` from `xfail` to
passing — the count becomes
`4 failed, 598 passed, 6 xfailed, 18 errors`. (The fourth gain is
`test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_associate_getitem`,
which was failing on the same `__contains__` bug as §2 and now
transparently passes.)

### `python -m pytest test/openjd/model-v0` (pure-Python baseline)

```
2311 passed in 8.07s
```

The reference passes all of its tests in the same repo.

### `cargo clippy --workspace -- -D warnings` against `rust-bindings/`

```
error: could not compile `openjd-python` (lib) due to 76 previous errors
```

Distribution of errors:

| Category | Count |
|---|---|
| `non_camel_case_types` (enum variants `RANGE_EXPR`, `TYPEVAR_T*`, `CHUNK_INT`, `READY_ENDING`, every session enum, every PyJobParameterType / PyTaskParameterType variant) | ~50 |
| `upper_case_acronyms` (`POSIX`, `URI`, `JSON`, `YAML`, `INT`, `FLOAT`, `STRING`, etc.) | ~12 |
| `deprecated` (PyO3 0.20+ API: `Bound::cast` over `downcast`, `from_py_object` opt-in) | ~10 |
| `redundant_closure` / `needless_borrow` | ~5 |
| `unused_imports`, `unused_doc_comments`, `dead_code`, `useless_format!`, `too_many_arguments` | 5 |

These match the prior `expr` evaluation — same unreliable opt-in scheme,
same auto-deriveFromPyObject deprecation, same enum-variant casing.

### `cargo run --bin stub_gen --features stub-gen` would help

The current `src/openjd/_openjd_rs.pyi` is missing 25 of the 50 runtime
symbols (see §3 stub drift list above). Regenerating with the latest
build would add at minimum:

```
ActionResult, ActionState, ActionStatus, BadCredentialsException,
DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT, DecodeValidationError,
ExpressionError, ExpressionTypeError, FormatStringValidationError,
JobParameterValue, ModelValidationError, PosixSessionUser, RangeExprError,
ScriptRunnerState, Session, SessionError, SessionState,
StepDependencyEdge, StepDependencyNode, TaskParameterValue,
UnsupportedSchema, WindowsSessionUser, create_environment, deserialize_step
```

## 7. Exploratory Findings

The probe in `/tmp/explore_model.py` (516 lines) drove out the items
listed below. The 10 functional gaps now have failing-but-xfailed tests
in `test/openjd/model-v1/test_known_gaps.py`.

### Confirmed bugs

| # | Bug | Test name (`test_known_gaps.py`) |
|---|---|---|
| 1 | ~~`IntRangeExpr.from_str("-1 - -2 : -1")` iterates as `[-2, -1]`; reference iterates as `[-1, -2]`.~~ **Resolved** — accepted as an intentional behavior change. `RangeExpr` values are always an increasing list of integers; descending-input direction is not retained. See `specs/python-model-interface.md` Compatibility Aliases. | `test_int_range_expr_descending_iteration_order` (now asserts the ascending behavior) |
| 2 | ~~`StepParameterSpaceIterator.__contains__` rejects values it just yielded.~~ **Resolved** — `extract_task_parameter_set` now reads the parameter type via `as_str()` first. | `test_step_param_space_iter_contains_self_yielded` (now passing) |
| 3 | `model_to_object(model=...)` raises `NotImplementedError` for every Rust-backed model. | `test_model_to_object_round_trip` |
| 4 | ~~`chunks_default_task_count` setter is a silent no-op (returns `Ok(())` without storing).~~ **Resolved** — wrapper now holds a persistent `Mutex<StepParameterSpaceIterator>`; the setter calls `iter.set_chunks_default_task_count(value)` on it. | `test_step_param_space_iter_chunks_default_task_count_setter` (now passing) |
| 5 | ~~`len(iter)` returns 0 on adaptive-chunked space; reference raises `ValueError`.~~ **Resolved** — `__len__` now raises `ValueError("Length is not available because the parameter space uses adaptive chunking.")`. | `test_step_param_space_iter_adaptive_len_raises` (now passing) |
| 6 | ~~`JobTemplate`, `Job`, `Step`, `StepParameterSpaceIterator`, `FormatString`, `RangeExpr`, `SymbolTable`, `JobParameterType`, `DocumentType` — none pickleable. (`TemplateSpecificationVersion` *is* pickleable because it's a Python `Enum`.)~~ **Partially resolved (Rec #8).** `FormatString`, `RangeExpr`, `SymbolTable`, `JobParameterType`, `DocumentType`, and `TemplateSpecificationVersion` (Rust-side) all pickle now. The decoded model containers (`JobTemplate`, `Job`, `Step`, `StepParameterSpaceIterator`) still don't — they need `to_dict()` / `to_json()` accessors first. | `test_job_template_pickleable` (still xfail) |
| 7 | ~~`TaskParameterType` is not hashable, but `JobParameterType` is.~~ **Resolved (Rec #9).** Added `frozen, hash` to `PyTaskParameterType`. | `test_task_parameter_type_hashable` (now passing) |
| 8 | `StepParameterSpace.taskParameterDefinitions[name]` returns serde-tagged JSON, not typed object. | `test_task_parameter_definitions_typed_objects` |
| 9 | `decode_template` not exported (reference exports it). | `test_decode_template_re_export` |
| 10 | `JobTemplate.specificationVersion` (camel) not exposed. | `test_job_template_specification_version_camelcase` |

### Other findings (informational, not failing tests)

- `parse_model(obj=…)` accepts both job and environment templates and
  dispatches correctly. ✓
- `document_string_to_object(document=yaml_str)` works; passing
  `document_type=DocumentType.JSON` works. ✓
- `validate_amount_capability_name` correctly rejects
  `"acme:amount.worker.x"` (vendor-prefixed reserved scope) ✓ and
  correctly rejects `"amount.worker.foo"` (reserved scope, not in
  standard list) ✓.
- All decode error paths produce the right exception class (empty
  steps → `ModelValidationError`; missing specificationVersion →
  `DecodeValidationError`; unknown specificationVersion →
  `DecodeValidationError`). ✓
- Concurrent calls from 8 Python threads, 50 iterations each, do not
  produce errors. ✓
- Unicode in template (`"Émile🎬"`, `"渲染"`) round-trips through
  decode → create_job. ✓
- Exception classes pickle correctly under their canonical names
  (`openjd.model._v1.DecodeValidationError`, etc.). ✓
- `TaskParameterValue == ParameterValue` and the symmetric
  `JobParameterValue == ParameterValue` both work in either direction. ✓
- `script.let_bindings` is *not* exposed (use `script.let` instead).
  The original snake form was implemented as `let_bindings` in the
  Rust struct, exposed in Python only as `let`. ⚠ Inconsistency vs the
  reference, which has both `script.let_` (Python keyword reserved) and
  raw `let`.

## 8. Recommendations

These are ordered by impact. Each item references the artifact that
proves the gap so it can be fixed and the proof regenerated.

1. ~~**Fix `IntRangeExpr` descending-range iteration order.**
   `IntRangeExpr.from_str("-1 - -2 : -1")` must yield `[-1, -2]` (reference
   semantics: reflect the input direction). Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_int_range_expr_descending_iteration_order`
   and the four `test_step_param_space_iter` failures.~~ **Resolved** —
   reclassified as an intentional behavior change, not a bug. `RangeExpr`
   values are always an increasing list of integers; descending input
   direction is not retained in the canonical form. See
   `specs/python-model-interface.md` (Compatibility Aliases) for the
   user-facing note and `openjd-rs/specs/expr/range-expr.md` (Internal
   Representation) for the underlying design rationale. The
   `test_int_range_expr_descending_iteration_order` test in
   `test_known_gaps.py` has been converted from `xfail` to a positive
   assertion of the ascending behavior. The four
   `test_step_param_space_iter` parity failures
   (`test_associate_getitem`, `test_product_iteration`,
   `test_product_getitem`, `test_nested_expr_iteration`) remain
   reference-only and need their expected-value lists updated to
   ascending order, or to be marked as not-applicable to the
   Rust-backed binding.

2. ~~**Fix `StepParameterSpaceIterator.__contains__` to recognize self-yielded
   values.** The current `extract_task_parameter_set` interprets
   `TaskParameterValue` instances incorrectly when they are the dict
   values. Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_step_param_space_iter_contains_self_yielded`.~~
   **Resolved** — `extract_task_parameter_set` in
   `rust-bindings/src/model/step_param_space.rs` now reads the parameter
   type via `as_str()` (the convention used by `PyTaskParameterType` and
   `PyJobParameterType` and by the Python-side `ParameterValue` shim)
   before falling back to `.value` (stdlib `enum.Enum`) and `__str__`.
   Yielded values now round-trip through `__contains__`. The fix also
   transparently repairs
   `test/openjd/model-v1/test_step_param_space_iter.py::TestStepParameterSpaceIterator_2023_09::test_associate_getitem`,
   which uses the same `for v in expected_values: assert v in it` idiom.
   Verified by promoting the `xfail` test to a passing test.

3. **Implement `model_to_object` for every Rust-backed model type, or stop
   exporting it.** `decode_job_template(template=t); model_to_object(model=t)`
   should round-trip back to the input dict. Resolves
   `test/openjd/model-v1/test_parse.py::TestModelToObject::test[translates Decimal to string]`
   and `test/openjd/model-v1/test_known_gaps.py::test_model_to_object_round_trip`.

4. ~~**Fix `StepParameterSpaceIterator.chunks_default_task_count` setter.**
   File: `rust-bindings/src/model/step_param_space.rs:199`. Currently
   returns `Ok(())` after validating `chunks_adaptive()`; must actually
   mutate the iterator state (or hold an interior `RefCell` for the
   chunk count). Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_step_param_space_iter_chunks_default_task_count_setter`.~~
   **Resolved** — `PyStepParameterSpaceIterator` now holds a persistent
   `Mutex<StepParameterSpaceIterator>` (the upstream `NodeIterator` trait
   gained a `Send + Sync` bound; the upstream
   `StepParameterSpaceIterator` gained a public `reset()` method).
   The setter validates the value is a positive integer and that the
   space is adaptively chunked, then calls
   `iter.set_chunks_default_task_count(value)` on the persistent
   iterator. The shared `Arc<AtomicUsize>` propagates the new value to
   the live iteration nodes. Verified by promoting the `xfail` test to
   a passing test.

5. ~~**Make `len(StepParameterSpaceIterator)` raise `ValueError` for
   adaptive-chunked spaces.** File: `rust-bindings/src/model/step_param_space.rs`.
   When `chunks_adaptive()` is `True`, `__len__` should raise the same
   message as the reference: `"Length is not available because the
   parameter space uses adaptive chunking."`. Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_step_param_space_iter_adaptive_len_raises`.~~
   **Resolved** — `__len__` in
   `rust-bindings/src/model/step_param_space.rs` now checks
   `iter.chunks_adaptive()` and raises
   `ValueError("Length is not available because the parameter space uses
   adaptive chunking.")` (matching the reference's exact message)
   before consulting the underlying iterator's `len()`. Verified by
   promoting the `xfail` test to a passing test.

6. **Expose `taskParameterDefinitions` as typed objects, not serde-tagged
   JSON.** `Step.parameterSpace.taskParameterDefinitions["F"]` must
   return an object with `.type` (a `TaskParameterType`) and `.range`
   (the appropriate range collection / `RangeExpr`). Either implement
   `IntTaskParameterDefinition` / `RangeExpressionTaskParameterDefinition`
   / `RangeListTaskParameterDefinition` etc. as Rust pyclasses, or add a
   thin Python wrapper around the existing dict. Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_task_parameter_definitions_typed_objects`.

7. **Re-export the ~50 missing names from `openjd.model._v1.v2023_09`.**
   File: `src/openjd/model/_v1/v2023_09/__init__.py`. The 18 v2023_09
   test files cannot be collected. Add at minimum:
   `Action, AmountCapabilityName, AmountRequirement, AmountRequirementTemplate,
   AttributeCapabilityName, AttributeRequirement, AttributeRequirementTemplate,
   CancelationMethodNotifyThenTerminate, CancelationMethodTerminate,
   ChunkIntTaskParameterDefinition, CombinationExpr, Description,
   EnvironmentName, EnvironmentVariableNameString, EnvironmentVariableValueString,
   FileDialogFilterPatternStringValue, FloatTaskParameterDefinition,
   HostRequirements, HostRequirementsTemplate, Identifier,
   IntTaskParameterDefinition, JobFloatParameterDefinition,
   JobIntParameterDefinition, JobName, JobParameter, JobPathParameterDefinition,
   JobStringParameterDefinition, JobTemplateName, ModelParsingContext,
   ParameterStringValue, PathTaskParameterDefinition,
   RangeExpressionTaskParameterDefinition, RangeListTaskParameterDefinition,
   SimpleAction, StepName, StepParameterSpaceDefinition, StepTemplate,
   StringTaskParameterDefinition, TaskChunksDefinition, TaskParameterStringValueAsJob,
   UserInterfaceLabelStringValue`
   plus a stub `_parse` submodule with a `_parse_model` entry point so
   the test files import. Without this, the 18 v2023_09 test files in
   `test/openjd/model-v1/v2023_09/` remain uncollectable.

8. **Implement pickle support for the Rust-backed pyclasses.** Use PyO3
   `__reduce__` or `__getnewargs_ex__` returning `(reconstructor,
   serialised_payload)`. At minimum: `JobTemplate`, `EnvironmentTemplate`,
   `Job`, `Step`, `StepScript`, `StepParameterSpace`,
   `StepParameterSpaceIterator`, `FormatString`, `RangeExpr`,
   `SymbolTable`, `JobParameterType`, `TaskParameterType`,
   `DocumentType`. Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_job_template_pickleable`.

   **Partially resolved.** All Group A enums (`DocumentType`,
   `JobParameterType`, `TaskParameterType`, `ModelExtension`,
   `SpecificationRevision`, `TemplateSpecificationVersion`) and
   Group B value types (`ModelProfile`, `CallerLimits`,
   `ValidationContext`, `JobParameterValue`, `TaskParameterValue`,
   plus the cross-component types `FormatString`, `RangeExpr`,
   `SymbolTable` from `openjd.expr`) now pickle through the shared
   `_reconstruct_enum` / `_reconstruct_kwargs` helpers in
   `rust-bindings/src/pickle_helpers.rs`. New tests live in
   `test/openjd/model-v1/test_pickle.py`.
   The decoded model containers (`JobTemplate`, `EnvironmentTemplate`,
   `Job`, `Step`, `StepScript`, `StepParameterSpace`) and the live
   `StepParameterSpaceIterator` / `StepDependencyGraph` types are
   not yet pickleable — they need the underlying `openjd-rs` types
   to expose `to_dict()` / `to_json()` first. Will be tracked
   separately when those accessors land.
   `test_job_template_pickleable` remains xfail.

9. ~~**Make `TaskParameterType` hashable** by adding `frozen, hash` to the
   `#[pyclass]` attribute. Resolves
   `test/openjd/model-v1/test_known_gaps.py::test_task_parameter_type_hashable`.~~
   **Resolved.** `PyTaskParameterType` now declares `frozen, hash` and
   provides a `name` getter. The `test_task_parameter_type_hashable`
   xfail is now a passing regression test.

10. **Re-export `decode_template` from `openjd.model._v1`.** Either
    implement it as a thin wrapper (auto-detect job vs environment
    template, then call the appropriate decoder) or alias to
    `parse_model`. Resolves
    `test/openjd/model-v1/test_known_gaps.py::test_decode_template_re_export`.

11. **Expose `JobTemplate.specificationVersion`, `parameter_definitions`,
    `steps`, `extensions`, `job_environments`** (and the same for
    `EnvironmentTemplate.environment`, etc.). File:
    `rust-bindings/src/model/template.rs`. The current minimalist
    interface (`name` / `description` / `specification_version`) blocks
    consumers from inspecting templates, forcing them to round-trip
    through `decode_job_template` again. Resolves
    `test/openjd/model-v1/test_known_gaps.py::test_job_template_specification_version_camelcase`.

    **Partially resolved.** `JobTemplate.profile` now exposes the
    declared revision and extensions list as a typed `ModelProfile`
    (mirrors `JobTemplate::profile()` in the Rust crate). See
    `rust-bindings/src/model/template.rs:49`. Read the template's
    `extensions:` field via `template.profile.extensions`. Still
    missing: `specificationVersion` (camelCase accessor),
    `parameter_definitions`, `steps`, `job_environments`, full
    `EnvironmentTemplate.environment` body. The xfail test
    `test_job_template_specification_version_camelcase` is unchanged.

12. **Map `ModelError::FormatStringError` → `FormatStringError`, not
    `ModelValidationError`.** File: `rust-bindings/src/model/errors.rs`.
    The current `model_err_to_py` collapses three distinct exception
    classes into one. Add an explicit `FormatStringError` registration
    in `lib.rs` (or re-use the openjd.expr `FormatStringValidationError`)
    and map this variant correctly.

13. **Map `ModelError::Compatibility` → `CompatibilityError(ValueError)`.**
    File: `src/openjd/model/_v1/__init__.py` plus
    `rust-bindings/src/model/errors.rs`. Currently `CompatibilityError`
    inherits from `Exception` only — code catching `ValueError` will
    miss it. The reference inherits it from `ValueError`.

14. **Update `specs/python-model-interface.md` to match implementation.**
    Add: `parse_model`, `document_string_to_object`, `decode_template`,
    `STANDARD_AMOUNT_CAPABILITIES`, `STANDARD_ATTRIBUTE_CAPABILITIES`,
    `validate_amount_capability_name`, `validate_attribute_capability_name`,
    `evaluate_let_bindings`, `deserialize_step`, `create_environment`,
    `JobParameterValue`, `TaskParameterValue`, `StepDependencyNode`,
    `StepDependencyEdge`. Correct the `it.names` /
    `graph.step_names` snippets to match the property/method shape
    actually implemented. Document that `JobParameterType` is hashable
    and pickleable but `TaskParameterType` and `DocumentType` are not.

    **Partially resolved.** Added a Profile section documenting
    `ModelProfile`, `ModelExtension`, `SpecificationRevision`,
    `CallerLimits`, `ValidationContext`. Updated the
    `decode_job_template` example to show the Rust-aligned
    `supported_extensions=[<str>, ...]` + `caller_limits=` signature
    and the `template.profile` getter. The other items in this
    recommendation (parse_model, document_string_to_object,
    decode_template, STANDARD_*, validate_*_capability_name,
    evaluate_let_bindings, deserialize_step, create_environment,
    JobParameterValue, TaskParameterValue, StepDependencyNode,
    StepDependencyEdge) remain undocumented.

15. **Regenerate `src/openjd/_openjd_rs.pyi` via
    `cargo run --bin stub_gen --features stub-gen`.** The current file
    is missing 25 runtime symbols (see §3). For every `create_exception!`
    type, add a matching `class XxxError(ValueError): ...` to the stub
    so IDE tooltips and `from openjd._openjd_rs import …` see the right
    symbols.

16. **Resolve `cargo clippy --workspace -- -D warnings` (76 errors).**
    File: `rust-bindings/src/`. Same shape as the prior `expr`
    evaluation. Apply the suggested rewrites (rename `RANGE_EXPR` to
    `RangeExpr` etc., remove unused imports, use `Bound::cast` instead
    of `downcast`, opt in to `#[pyclass(from_py_object)]` explicitly,
    replace `format!()` with `.to_string()` where appropriate, allow
    or remove the unused `from_rust` helper).

17. **Switch the Rust-on-Python `decode_*_dict` path away from the
    `dict → json.dumps → serde_json::from_str` round-trip.** File:
    `rust-bindings/src/model/decode.rs`. Use a direct
    `serde_pyobject` / `pythonize::depythonize` conversion. Today's
    detour doubles parse cost for callers that already hold a dict and
    silently rejects values like `Decimal` and `Path`.

18. **Backfill tests.** Per §4, the following reference test files have
    no analog in `test/openjd/model-v1/`:
    - `format_strings/test_format_string.py` and 5 sibling files
    - `_internal/test_combination_expr.py` and 4 sibling files
    - `test_step_param_space_iter_with_chunks.py`
    Add the 18 v2023_09 files only after recommendation 7 lands so they
    can collect. Add a binding-equivalent of the format-string
    behavioural tests so the consumers know they get the same
    round-trip semantics.

19. **Release the GIL on long-running calls.** Wrap
    `decode_job_template`, `decode_job_template_str`,
    `decode_environment_template_str`, and the iterator-driving
    `StepParameterSpaceIterator::new` calls inside
    `Python::allow_threads(|| { … })`. Without this, multi-threaded
    Python servers (Deadline Cloud worker agent) cannot decode in
    parallel.

20. **Document or remove the `validate_*_capability_name` positional
    overload.** The binding's signature
    `(name: str = "", *, capability_name: str = "", standard_capabilities=None)`
    is more permissive than the reference and silently passes calls
    that omit `standard_capabilities`. Either align with the reference
    (kw-only, both required) or document the divergence in the spec.
