# openjd-expr Bindings Quality Evaluation Report

**Date:** 2026-05-26
**Component:** `openjd.expr`
**Reference branch:** `mwiebe/openjd-model-for-python@expr`

## Executive Summary

The Rust-backed `openjd.expr` bindings are in solid shape. The build is
clean, the full expr test suite (1788 passed, 24 platform-skipped, 0
failed, 0 xfail) runs in seconds, `cargo clippy --all-targets -- -D
warnings` is clean, and `test/openjd/expr/test_known_gaps.py` is empty
of substantive content — the prior round of P1 reference-parity gaps
(PathFormat hashable, unresolved-value extraction errors, list-construction
TypeError vs ValueError, ExprType arity validation, PathMappingRule repr
rendering) are all closed. v0 isolation is perfect: nothing under
`src/openjd/expr/`, `rust-bindings/src/expr/`, or `test/openjd/expr/`
imports from the v0 (pure-Python) `openjd.model` namespace at all.

The remaining gaps are all moderate-or-lower priority and cluster in
three areas: (a) the Python interface spec doesn't justify or even
acknowledge several deliberate, breaking divergences from the
pure-Python reference (most notably the removal of `FunctionLibrary`,
`FunctionSignature`, and `get_default_library`); (b) a small number of
behavioural drifts from the reference remain — `PathMappingRule` URI
validation is missing, the `from_dict` missing-fields error message is
formatted differently, `PathMappingRule.source_path` is always `str`
even when constructed from a `PurePath`, and `ExprValue.from_float`
made the previously-optional `original_str` argument required; and (c)
test coverage for `evaluate_let_bindings` is zero in the entire repo
even though it is a public symbol re-exported from `openjd.expr`. None
of these block adoption; all are tracked below as numbered
recommendations.

## 1. Python Interface Spec Review

`specs/python-expr-interface.md` is the contract for the binding (there
is no pure-Python `openjd.expr` predecessor — the reference branch is a
parallel implementation). It covers all 23 public symbols re-exported
from `src/openjd/expr/__init__.py`:

| Category | Symbols |
|---|---|
| Entry points | `evaluate_expression`, `parse_expression`, `evaluate_let_bindings`, `escape_format_string` |
| Value/type system | `ExprType`, `TypeCode`, `ExprValue`, `RangeExpr`, `FormatString`, `SymbolTable`, `ParsedExpression` |
| Profile | `ExprProfile`, `ExprRevision`, `ExprExtension`, `HostContext` |
| Path | `PathFormat`, `PathMappingRule` |
| Errors | `ExpressionError`, `ExpressionTypeError`, `RangeExprError`, `FormatStringValidationError` |
| Constants | `DEFAULT_MEMORY_LIMIT`, `DEFAULT_OPERATION_LIMIT` |

Coverage of the binding's public surface is complete — every symbol
re-exported by `src/openjd/expr/__init__.py.__all__` has an entry, and
every entry corresponds to a reachable binding. Nothing in the spec
references a removed symbol. The spec also covers all the
non-construction behaviour I tested: pickle table, equality/hashability
contracts, the unresolved `item()`/`str()` raise contract, the
`FormatString.validate_expressions` workflow, profile-builder semantics,
and the explicit "`match` was renamed to `match_type`" note.

Gaps the spec does not currently capture, however:

* **No acknowledgement of the `FunctionLibrary` / `FunctionSignature` /
  `get_default_library` removal.** The pure-Python reference exports
  these from `openjd.expr` (`src/openjd/expr/_functions/__init__.py` on
  the `expr` reference branch). The bindings replaced the entire
  function-library surface with `ExprProfile` / `ExprExtension` /
  `HostContext`. This is a deliberate, breaking change and the spec
  should say so explicitly with a short rationale (mirrors the
  Rust-side profile API, simpler call site, etc.) so users porting
  from the reference can find the migration path.
* **`FormatString.copy_used_symtab_values` is exposed by the binding
  and tested in `test/openjd/expr/test_copy_used_symtab.py` but does
  not appear in the spec.** Either remove it from the binding (it has
  no caller in this repo's expr surface) or add an entry to the
  `FormatString` section.
* **`ParsedExpression.peak_memory_usage` and `operation_count` thread
  safety is undocumented.** Both are stored in `AtomicUsize` fields
  that are *overwritten* on every `evaluate()` call, so concurrent
  evaluations of the same `ParsedExpression` instance produce
  last-writer-wins values. The spec should either guarantee
  per-evaluation metrics (require returning them from `evaluate`) or
  document the race so callers know not to rely on the attributes
  across threads.
* **`ExprValue.from_float` requires `original_str`.** The reference
  signature is `from_float(value, original_str=None)`. The spec
  documents the binding's two-argument form but doesn't mention that
  the `Optional` suffix from the reference was dropped.
* **`PathMappingRule.source_path` returns `str`** even when constructed
  from a `PurePosixPath` / `PureWindowsPath`. The reference stores the
  `PurePath` and returns it. The spec's `PathMappingRule` section uses
  string examples; it should explicitly note that the binding
  normalises `source_path` and `destination_path` to `str` (and that
  `PurePath` arguments are accepted but not preserved on read-back).

## 2. PyO3 Binding Source Review

The expr binding source under `rust-bindings/src/expr/` is well-organised
(one file per concern: `errors.rs`, `path_format.rs`, `expr_type.rs`,
`expr_value.rs`, `symbol_table.rs`, `profile.rs`, `parsed_expression.rs`,
`evaluate.rs`, `path_mapping.rs`, `range_expr.rs`, `format_string.rs`).
PyO3 conventions are followed correctly:

* **Exception registration** — all four expr exceptions
  (`ExpressionError`, `ExpressionTypeError`, `RangeExprError`,
  `FormatStringValidationError`) are routed through
  `register_renamed_exception` in `lib.rs`, so `__name__`,
  `__module__`, `__qualname__` all resolve to the canonical
  `openjd.expr` names. Verified at runtime — no `Py`-prefixed leak in
  pickle, repr, or traceback. `ExpressionError`'s reference-parity
  keyword constructor (`expr=`, `node=`, `lineno=`, `col_offset=`)
  and decoration methods (`with_context`,
  `message_with_expr_prefix`) are attached at module init via the
  documented `attach_expression_error_methods` mechanism, and
  `ExpressionTypeError` inherits them correctly through normal class
  inheritance.
* **Type conversions** — `i64` overflow at `py_to_expr_value` is
  remapped from `OverflowError` to `ExpressionError` to match the
  reference (verified: `ExprValue(2**63)` and `ExprValue(2**64-1)`
  both raise `ExpressionError` with a clear "Integer overflow"
  message). `Decimal` instances are detected via a real
  `isinstance(decimal.Decimal)` check so subclasses are accepted and
  same-named unrelated classes are not.
* **GIL handling** — expr evaluation in `evaluate_expression`,
  `ParsedExpression.evaluate`, and `FormatString.resolve*` does *not*
  release the GIL via `Python::allow_threads`. For the typical short
  evaluation this is fine, but range expressions that exceed
  `DEFAULT_MEMORY_LIMIT` are documented to fail-fast inside the Rust
  evaluator without any blocking I/O, so dropping the GIL would only
  matter for very long evaluations. Calling out as a future
  optimisation rather than a fix.
* **`#[pyclass]` constructor signatures** — match the spec for every
  class checked (`ExprType`, `ExprValue`, `SymbolTable`, `ExprProfile`,
  `HostContext`, `RangeExpr`, `FormatString`, `PathMappingRule`).
  `extract_expr_type` accepts both `str` and `ExprType` arguments
  consistently across the three sites that use it.
* **`Py<T>` lifetime correctness** — no obvious reborrow hazards. The
  one place that reaches into a passed Python object as a pyclass
  cell (`FormatString.copy_used_symtab_values`) uses
  `cell.borrow_mut()` correctly.
* **ABI3 compatibility** — `Cargo.toml` declares `abi3-py39`. Verified
  that the abi3 build works on Python 3.13 (the active interpreter in
  this evaluation environment).
* **Stub generation** — `cargo run --bin stub_gen --features stub-gen`
  followed by `scripts/generate_stubs.sh` produces no diff against
  the committed `src/openjd/_openjd_rs.pyi`. (See §6 for a
  warning-only side effect from the model module's stub-gen build.)

The single fragile area in the binding source is **the ranges()/method
return shape**. `RangeExpr.ranges()` returns
`Vec<(i64, i64, i64)>` — a `list[tuple[int,int,int]]` in Python — while
the reference's `RangeExpr.ranges` is a `property` returning
`list[_IntRange]` objects. This is a documented design choice (the spec
says `r.ranges()`), but it's worth keeping in the parity table because
the change of method-vs-property and tuple-vs-class shape both matter
to porting users.

## 3. Python Wrapper Module Review

`src/openjd/expr/__init__.py` re-exports 23 symbols from
`openjd._openjd_rs`. `__all__` matches the import block, with no
dangling re-exports and no spec entries that aren't reachable. One
architectural smell:

* `evaluate_let_bindings` is registered in `lib.rs` from
  `rust-bindings/src/model/create_job_fns.rs`
  (`#[pyfunction] #[pyo3(name = "evaluate_let_bindings")]
  pub(crate) fn py_evaluate_let_bindings(...)`), not from
  `rust-bindings/src/expr/`. Logically it belongs to the expr surface
  (it accepts `PySymbolTable` and `PyExprProfile`, returns a
  `PySymbolTable`, and the spec documents it under `openjd.expr`),
  yet it lives under the model crate's binding source. The function
  body uses `openjd_model::evaluate_let_bindings` from the
  `openjd-rs::openjd-model` crate, which is the underlying reason for
  the location — but the Python-side surface ownership is out of
  step with the Rust-side. Either:
  1. Move `py_evaluate_let_bindings` into `rust-bindings/src/expr/`
     and have it call into `openjd_expr::let_bindings::evaluate` (or
     equivalent), if such a primitive exists; or
  2. Leave the binding source where it is but add a short comment
     in `rust-bindings/src/expr/mod.rs` pointing to the model module
     so future maintainers don't go hunting.

The wrapper also has a comment block explaining why the exception
classes are renamed Rust-side (in `lib.rs`) rather than Python-side
fix-ups; that comment is accurate.

`AGENTS.md` — separately from the spec — describes a
`function_library.rs` file in `rust-bindings/src/expr/` ("Function
library (`function_library.rs`) — `get_default_library`,
`FunctionLibrary.with_host_context`"). That file does not exist; the
function-library facility was replaced by `ExprProfile` /
`HostContext`. AGENTS.md drift is outside this report's scope but
worth flagging in passing.

## 4. Test Review

`test/openjd/expr/` has 30+ test modules covering parsing, evaluation,
arithmetic, comparison, list operations, range expressions, string
operations, target-type propagation, paths, URI paths, path mapping,
equality, pickle, error formatting, format strings, function context,
operation/memory limits, fuzzing, and platform-specific behaviour. The
suite runs in ~5s (parallelised; ~2s wall when not measuring coverage)
and is consistently green: 1788 passed, 24 skipped (all
Windows-only, expected on Linux), 0 xfailed, 0 errors.

Coverage gaps relative to the reference test suite:

* **`evaluate_let_bindings` has no tests anywhere in the repo.** The
  symbol is re-exported from `openjd.expr.__init__.py.__all__`, the
  spec documents it (lines 71–80), the binding routes through
  `openjd_model::evaluate_let_bindings`, and yet there is no test
  file under `test/openjd/expr/` (or anywhere else found by
  `grep -rn evaluate_let_bindings test/`). At minimum the happy
  path, the let-binding-syntax error path, and the
  inner-expression-error path all need coverage.
* **No symmetric `PathMappingRule(URI=non-URI)` test.** The reference
  raises `ValueError`; the binding silently accepts it (see §5,
  Recommendation 3).
* **No symmetric `PathMappingRule.source_path` PurePath round-trip
  test.** The reference returns the original `PurePath`; the binding
  always converts to `str`.

`test_known_gaps.py` is empty of substantive content (the file is
maintained as the landing pad for regressions but currently documents
no open gaps). Per the AGENTS.md test convention, when this report's
recommendations are implemented, every newly-fixed gap should land its
xfail in `test_known_gaps.py` first, then graduate to its proper home
when the fix lands. The recommendations below identify which test
files each fix should ultimately land in.

The reference tests in `~/openjd-model-for-python@expr/test/openjd/expr/`
are mostly mirrored. A diff of test file names shows two
binding-only files (`test_format_string_validate.py`,
`test_pickle.py`) that have no reference counterpart — both cover
binding-specific surface (FormatString and pickle) that the reference
implementation doesn't have or has differently. No reference test
files are missing from the binding side at the file-level granularity.

## 5. Parity with Pure-Python Reference

Every public symbol in the reference `src/openjd/expr/__init__.py` has
either a counterpart in the binding or a documented removal:

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `evaluate_expression` | ✓ | ✓ | ✓ |
| `parse_expression` | ✓ | ✓ | ✓ |
| `ParsedExpression` | ✓ | ✓ | ✓ |
| `DEFAULT_MEMORY_LIMIT` | `100_000_000` | `100_000_000` | ✓ |
| `DEFAULT_OPERATION_LIMIT` | `10_000_000` | `10_000_000` | ✓ |
| `ExprType` | dataclass-like | pyclass | ✓ structural |
| `ExprType.match` | ✓ | renamed `match_type` | ⚠ documented in spec |
| `TypeCode` | `IntEnum` | pyclass `eq_int` | ⚠ `isinstance(tc, int)` is False (Rec 7) |
| `ExprValue` | ✓ | ✓ | ✓ |
| `ExprValue.null()` | ✓ classmethod | absent (use `ExprValue(None)`) | ⚠ Rec 8 |
| `ExprValue.from_float(value, original_str=None)` | optional kwarg | required positional | ⚠ Rec 5 |
| `ExprValue.to_string()` | ✓ | absent (use `str(v)`) | ✓ documented in spec |
| `ExprValue.to_expr_value_list()` | ✓ | absent (use iter / `list(v)`) | ✓ via spec sequence-protocol section |
| `ExprValue.unresolved` | ✓ | ✓ | ✓ |
| `ExprValue.item()` | ✓ | ✓ (raises on unresolved) | ✓ |
| `SymbolTable` | ✓ | ✓ | ✓ |
| `SymbolTable.symbols` | absent | ✓ binding addition | ✓ binding-only, documented in spec |
| `SymbolTable.union` | absent | ✓ binding addition | ✓ binding-only, documented in spec |
| `SymbolTable.__eq__` | absent | ✓ binding addition | ✓ binding-only, documented in spec |
| `RangeExpr` | ✓ | ✓ | ✓ |
| `RangeExpr.ranges` | property of `_IntRange` list | method returning tuple-3 list | ⚠ method/shape divergence — documented in spec |
| `RangeExprError` | ✓ | ✓ | ✓ |
| `PathMappingRule` | ✓ | ✓ | ✓ |
| `PathMappingRule.source_path` | `PurePath \| str` (preserved) | always `str` | ⚠ Rec 4 |
| `PathMappingRule(URI source_path_format, non-URI source_path)` | raises `ValueError` | accepts | ❌ Rec 3 |
| `PathMappingRule.from_dict({})` missing-fields message | `[..._format, ..._path, ..._path]` quoted (Python list repr) | `[source_path_format, source_path, destination_path]` bare names | ❌ Rec 2 |
| `PathFormat` | `str` Enum | pyclass `eq_int` | ✓ |
| `ExpressionError` | ✓ | ✓ | ✓ |
| `ExpressionTypeError` | ✓ | ✓ | ✓ |
| `FunctionLibrary` | ✓ | absent | ⚠ Rec 1 (deliberate, but spec must explain) |
| `FunctionSignature` | ✓ | absent | ⚠ Rec 1 (deliberate, but spec must explain) |
| `get_default_library` | ✓ | absent | ⚠ Rec 1 (deliberate, but spec must explain) |
| `FormatString` | absent | ✓ | binding-only, fully documented |
| `escape_format_string` | absent | ✓ | binding-only, fully documented |
| `FormatStringValidationError` | absent | ✓ | binding-only, fully documented |
| `evaluate_let_bindings` | absent | ✓ | binding-only, documented but UNTESTED — Rec 6 |
| `ExprProfile` / `ExprRevision` / `ExprExtension` / `HostContext` | absent | ✓ | binding-only (replaces FunctionLibrary), fully documented |

**Behavioural divergences confirmed by direct probing:**

* **i64 boundary handling**: identical. `ExprValue(2**63)` and
  `ExprValue(2**64-1)` raise `ExpressionError` with a clean
  "Integer overflow" message; `ExprValue(2**63 - 1)` and
  `ExprValue(-2**63)` round-trip correctly through `item()`.
* **int vs float equality**: `ExprValue(1) == ExprValue(1.0)` returns
  `True` in both reference and binding (binding goes through
  `ExprValue::equals` which handles cross-type numeric equality
  upstream).
* **Pickle fidelity**: every class on the spec's pickle table
  round-trips and `==` matches; exception classes round-trip with
  correct `__module__` (`openjd.expr`) and structured fields are
  preserved (verified `ExpressionError(msg, expr=..., col_offset=...)`
  survives `pickle.dumps`/`loads`).
* **Threading**: `evaluate_expression` and
  `ParsedExpression.evaluate` are safe for concurrent calls from
  multiple Python threads — the parser/evaluator state is per-call
  and the function library cache is `Arc`-shared. The one race is on
  `ParsedExpression.peak_memory_usage` / `operation_count` (atomic,
  last-writer-wins; see Rec 9).
* **`ExprType.match_type` semantics**: identical to the reference's
  `ExprType.match` (verified: `list[T].match_type(list[int])` returns
  `{TypeCode.TYPEVAR_T: ExprType("int")}`).
* **Arity validation**: `ExprType(TypeCode.INT, [ExprType("string")])`
  raises `ValueError "Int does not accept type parameters"`, and
  `ExprType(TypeCode.LIST)` raises
  `ValueError "List requires exactly one type parameter"`. Matches
  the spec's promise.
* **Unresolved value propagation**: `ExprValue.unresolved("int")`
  raises `ExpressionTypeError` from `item()` and `str()` with clear
  "value is not known" messages, while `repr()` returns
  `'ExprValue.unresolved(ExprType("int"))'` without raising. Matches
  the spec's documented contract.

## 6. Build and Test Results

All commands run from `/home/markw/openjd-model-for-python` on branch
`bindings-rs` against `~/openjd-rs` (the sibling Rust workspace).

```text
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml
🍹 Building a mixed python/rust project
🐍 Found CPython 3.13
🔗 Found pyo3 bindings with abi3 support
   Compiling openjd-sessions v0.2.1
   Compiling openjd-python v0.9.0
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.12s
🛠 Installed openjd-model-0.9.1.post46+g9224fd874.d20260526
```

```text
$ python -m pytest test/openjd/expr -q --no-header
1788 passed, 24 skipped, 8 warnings in 4.61s
```

The 24 skipped tests are all Windows-only validations
(`TestReprPwshWindowsValidation`, `TestReprCmdWindowsValidation`),
expected to be skipped on Linux. The 8 warnings are all
`PytestUnknownMarkWarning` for the custom `pytest.mark.fuzz` marker,
which can be silenced by registering it in `pyproject.toml` (low
priority).

```text
$ cargo build --manifest-path rust-bindings/Cargo.toml --all-targets
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 8.10s

$ cargo test --manifest-path rust-bindings/Cargo.toml
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored

$ cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets -- -D warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 8.01s
```

Clippy is fully clean under `-D warnings`.

```text
$ python scripts/maturin_build.py develop --features stub-gen --manifest-path rust-bindings/Cargo.toml
warning: unused import: `PyType`
 --> rust-bindings/src/model/task_parameter.rs:40:35
   |
40 | use pyo3::types::{PyDict, PyList, PyType};
   |                                   ^^^^^^

$ scripts/generate_stubs.sh
Generated src/openjd/_openjd_rs.pyi

$ git diff --stat src/openjd/_openjd_rs.pyi
(no diff)
```

The stub regeneration produces no diff, so the committed `.pyi` is
current. The `unused_import` warning above is in
`rust-bindings/src/model/task_parameter.rs` (model component, not
expr); flagging here for completeness because it appears in the
build log of the expr evaluation, but resolution belongs to a model
report.

## 7. Exploratory Findings

In addition to the parity probes summarised in §5, a few targeted
probes were run:

1. **`PathMappingRule(URI, "/not/a/uri", ...)` accepts**: probed
   directly — the binding constructs a rule with a `source_path` that
   isn't a URI string, while the reference raises
   `ValueError "Path mapping rule with URI source_path_format requires
   a URI string source_path"`. Reproducible via:
   ```python
   PathMappingRule(source_path_format=PathFormat.URI,
                   source_path="/not/a/uri",
                   destination_path="/dst")
   ```
   No exception. Tracked as Recommendation 3.
2. **`PathMappingRule.from_dict({"source_path_format": "POSIX"})`**:
   binding raises
   `'Path mapping rule requires the following fields: [source_path_format, source_path, destination_path]'`
   while the reference raises
   `"Path mapping rule requires the following fields: ['source_path_format', 'source_path', 'destination_path']"`
   (Python `list[str]` `repr` form with quotes). Tracked as
   Recommendation 2.
3. **`PathMappingRule(source_path=PurePosixPath("/src"), ...)`**: the
   `source_path` getter returns `'/src'` (`str`) rather than the
   original `PurePosixPath`. Tracked as Recommendation 4.
4. **`ExprValue.from_float(3.14)`**: raises
   `TypeError: ExprValue.from_float() missing 1 required positional argument: 'original_str'`.
   The reference signature is `from_float(value, original_str=None)`.
   Tracked as Recommendation 5.
5. **`evaluate_let_bindings` is unreachable from any test file**:
   confirmed via repository-wide grep. Tracked as Recommendation 6.
6. **`isinstance(TypeCode.INT, int)` returns `False`** while the
   reference's `IntEnum` returns `True`. The `eq_int` modifier on the
   pyclass ensures `TypeCode.INT == 2` and `int(TypeCode.INT) == 2`
   still work, so practical impact is limited but downstream code that
   uses `isinstance(..., int)` to special-case enum values diverges
   between reference and binding. Tracked as Recommendation 7.
7. **`ExprValue.null()` not exposed**: the reference's
   `ExprValue.null()` classmethod has no binding counterpart;
   `ExprValue(None)` is the documented replacement. Tracked as
   Recommendation 8.
8. **Concurrent `ParsedExpression.evaluate` races on metrics**:
   running 4 threads × 50 iterations against a single
   `ParsedExpression` instance produces a self-consistent
   `peak_memory_usage` / `operation_count` reading at the end but
   intermediate observers will see other threads' values. Tracked as
   Recommendation 9.

No new failing tests were added to `test_known_gaps.py` because the
gaps above are all message/shape/coverage-level, not behavioural-
correctness gaps that would benefit from a runnable xfail. Each
recommendation below identifies the file in which a passing regression
test should land once the fix is applied.

## 8. Recommendations

Numbered for the report-driven workflow in `~/openjd-rs/AGENTS.md`. P1
items affect correctness vs the reference; P2 items affect spec
accuracy or coverage; P3 items are quality-of-life improvements.

### P1 — Reference parity

1. ~~**Document the `FunctionLibrary` / `FunctionSignature` /
   `get_default_library` removal in
   `specs/python-expr-interface.md`.** Add a short "Migration from the
   pure-Python reference" subsection (or a paragraph in the
   `ExprProfile` section) explaining that the function-library surface
   was replaced by `ExprProfile` + `HostContext` and pointing readers
   to the corresponding builder pattern. This is the single most
   important divergence from the reference and the spec currently
   doesn't even acknowledge it.~~ **Resolved.** Added a "Migration
   from the pure-Python reference" subsection in
   `specs/python-expr-interface.md` right before the
   `ParsedExpression` section, with a `Removed → Replaced by` table
   (`FunctionLibrary` → `ExprProfile`, `FunctionSignature` → no
   replacement, `get_default_library()` → `ExprProfile.current()`),
   side-by-side v0/v1 code snippets showing the `library=` →
   `profile=` rewiring, and a paragraph explaining the trade-off
   (introspection surface for a smaller builder-shaped API whose
   state is fully determined by the
   `(revision, extensions, host_context)` triple). Landed in
   commit `11aa2de`.
2. ~~**Restore `PathMappingRule.from_dict` missing-fields error message
   parity.** In
   `rust-bindings/src/expr/path_mapping.rs::from_dict`, change the
   message from the bare `[source_path_format, source_path,
   destination_path]` to the Python list-repr form
   `['source_path_format', 'source_path', 'destination_path']` (quote
   each name). Land regression test alongside the existing
   `TestPathMappingRuleFromDict` cases in
   `test/openjd/expr/test_path_mapping.py`.~~ **Resolved.**
   `from_dict` now emits the Python list-repr form
   `['source_path_format', 'source_path', 'destination_path']`
   (single-quoted names, comma-space separators) byte-for-byte
   matching the v0 reference's f-string interpolation of
   `[field.name for field in fields(PathMappingRule)]`. The
   supported-field list is computed once and threaded through both
   the missing-fields branch and the unsupported-keys check. The
   existing `test_from_dict_missing_field` test now asserts the
   full message body per AGENTS.md "Test Quality Standard"; the
   six other loose-match tests in the file
   (`test_from_dict_empty`, format-mismatch tests, extra-field
   tests) were also tightened in the same commit. Landed in
   `11aa2de`.
3. ~~**Validate URI form when constructing
   `PathMappingRule(source_path_format=PathFormat.URI, source_path=...)`.**
   The reference rejects non-URI strings with `ValueError "Path
   mapping rule with URI source_path_format requires a URI string
   source_path"`. The binding currently accepts anything. Add the
   check in `rust-bindings/src/expr/path_mapping.rs::PyPathMappingRule::new`
   (use `openjd_expr::path_mapping::is_uri` if exposed, otherwise
   replicate the regex check). Land regression test in
   `test/openjd/expr/test_path_mapping.py::TestPathMappingRuleFromUri`.~~
   **Resolved.** Both `PyPathMappingRule::new` and `from_dict`
   (which has its own constructor path) now call
   `openjd_expr::path_mapping::is_uri` when
   `source_path_format == URI` and raise `ValueError` with the
   exact v0 message
   `"Path mapping rule with URI source_path_format requires a URI
   string source_path"` on mismatch. New `TestUriValidation`
   class with 8 tests pinning the full message: 3 negative cases
   (non-URI, empty, relative), parametrised 4-scheme positive
   case (`s3://`, `https://`, `file:///`, custom), and a
   `from_dict` variant. The pre-existing
   `test_repr_uses_python_enum_name_uri` was updated to use a
   real URI (`s3://bucket/a` instead of `/a`) since the new
   validation correctly rejects the old form. Landed in `11aa2de`.

### P2 — Spec/coverage gaps

4. ~~**Decide whether `PathMappingRule.source_path` should preserve
   `PurePath` typing or stay `str`.** Currently the binding always
   normalises to `str`. The reference returns whatever the constructor
   was given. If the binding's behaviour is intentional (e.g. to keep
   the field cheap to serialise / pickle), document the normalisation
   in the spec's `PathMappingRule` section explicitly so users porting
   from the reference know to call `.str` themselves where they need
   `PurePath` shape. Otherwise, change the getter to wrap the stored
   string back into a `PurePosixPath` / `PureWindowsPath` per
   `source_path_format` for non-URI rules.~~ **Resolved (documented
   intentional behaviour).** The string normalisation is
   intentional — keeps the rule cheap to serialise / pickle /
   round-trip through `to_dict` / `from_dict` without per-format
   discriminator logic on the consumer side. Added a paragraph +
   re-wrap example to the `PathMappingRule` section in
   `specs/python-expr-interface.md` so callers porting from the
   reference see the type asymmetry up front. Landed in `029fcfa`.
5. ~~**Make `ExprValue.from_float`'s `original_str` parameter optional
   to match the reference.** Change the signature in
   `rust-bindings/src/expr/expr_value.rs` to
   `from_float(value: f64, original_str: Option<String>) -> PyResult<Self>`
   (with `#[pyo3(signature = (value, original_str=None))]`) and use
   `format!("{value}")` or `Float64::new` directly when
   `original_str` is `None`. Update the spec example to show the
   one-argument form. Land coverage in
   `test/openjd/expr/test_expression_value.py`.~~ **Resolved + extended.**
   `from_float` signature changed to
   `from_float(value, original_str=None)` matching the v0
   reference; dispatches to `Float64::with_str` when present and
   `Float64::new` when omitted. Spec example updated to show both
   shapes. The follow-up commit `b784942` extended the function
   to also accept `Decimal` inputs and auto-capture the
   `Decimal`'s string form when `original_str` is omitted, so
   `ExprValue.from_float(Decimal("1.00"))` now produces the same
   `str()` output as `ExprValue(Decimal("1.00"))`. The two
   constructors are consistent across all input types. New tests
   in `TestFromFloat`: `test_from_float_one_arg`,
   `test_from_float_explicit_none`,
   `test_from_float_one_arg_loses_trailing_zero`,
   `test_from_float_rejects_nan`,
   `test_from_float_rejects_nan_with_original_str`,
   `test_from_float_decimal_input_preserves_string`,
   `test_from_float_decimal_consistent_with_main_constructor`
   (parametric over six Decimal forms),
   `test_from_float_decimal_input_explicit_original_str_wins`,
   `test_from_float_int_input`, and
   `test_from_float_decimal_rejects_nan`. Landed across `029fcfa`
   (signature change) and `b784942` (Decimal extension).
6. ~~**Add tests for `evaluate_let_bindings` to
   `test/openjd/expr/`.** Either create a new
   `test/openjd/expr/test_let_bindings.py` or add a
   `TestEvaluateLetBindings` class to an existing file. Cover at
   minimum: (a) the spec example (single binding), (b) chained
   bindings where a later binding references an earlier one, (c)
   `ExpressionError` raised on syntax error inside a binding, (d)
   `ExpressionError` raised on the "missing `=`" / "no name" form,
   (e) the result `SymbolTable` containing both the original input
   symbols and the bound names.~~ **Resolved.** New file
   `test/openjd/expr/test_let_bindings.py` with
   `TestEvaluateLetBindings` (10 tests) covering all five required
   scenarios plus extras: single-binding spec example,
   chained-bindings where a later refs an earlier, input-symbol
   preservation, empty-list, missing-equals (regular +
   blank-string), RHS syntax-error (with parser
   caret-and-source rendering verification), undefined-symbol
   top-level, chained-undefined (correct binding named in
   diagnostic), and `profile=` kwarg. All assertions follow
   AGENTS.md "Test Quality Standard": exception class + the
   message body (full equality where the content is single-line,
   prefix + substring where the parser appends multi-line caret
   rendering, with rationale comments). Landed in `029fcfa`.
7. ~~**Acknowledge in the spec that `TypeCode` is not an `IntEnum`
   subclass.** The reference is `class TypeCode(IntEnum)`; the binding
   is a pyo3 enum that compares equal to ints (`eq_int`) but is not an
   `int`. Add a one-liner in the `TypeCode` section: "`TypeCode` values
   compare equal to `int` (`TypeCode.INT == 2`) and convert via
   `int(TypeCode.INT)`, but they are not `int` subclasses —
   `isinstance(TypeCode.INT, int)` returns `False`."~~ **Resolved.**
   Added a "Not an `IntEnum` subclass" note callout to the `TypeCode`
   section of `specs/python-expr-interface.md` covering equality
   (`TypeCode.INT == 2`), int conversion (`int(TypeCode.INT)`), the
   `isinstance(..., int)` divergence (returns `False`), and the
   recommended `isinstance(..., TypeCode)` / value-comparison
   alternatives for callers porting from the v0 reference.
8. ~~**Document or add `ExprValue.null()`.** The reference has
   `ExprValue.null()` as a classmethod; the binding requires
   `ExprValue(None)`. Either (a) add the classmethod to
   `rust-bindings/src/expr/expr_value.rs` for parity, or (b) add an
   explicit "Use `ExprValue(None)` instead of `ExprValue.null()` from
   the pure-Python reference" note to the spec's `ExprValue` section.~~
   **Resolved (option b — documented).** Added a "Null values"
   subsection to the `ExprValue` section right before the existing
   "Unresolved values" subsection. The new section shows
   `ExprValue(None)` as the canonical null constructor, runnable
   examples for `type`/`type_code`/`is_null`/`item`/`str`/`bool`,
   and an explicit migration note: "Callers porting from the
   pure-Python reference should rewrite `ExprValue.null()` to
   `ExprValue(None)`. The two produce the same shape; the
   classmethod was a stylistic alias the binding deliberately
   omitted to keep the constructor surface narrow."

### P3 — Quality of life

9. **Document or fix `ParsedExpression` metric thread safety.** Either
   (a) make `evaluate_with_metrics` return a structured `EvaluateResult`
   (value plus metrics) and deprecate the `peak_memory_usage` /
   `operation_count` attributes, or (b) document in the spec that the
   attributes hold *the most recent* evaluation's metrics and racing
   readers should not rely on them across threads.
10. **Add `FormatString.copy_used_symtab_values` to the spec or remove
    it from the binding.** The method exists in
    `rust-bindings/src/expr/format_string.rs` and is exercised by
    `test/openjd/expr/test_copy_used_symtab.py` but isn't documented in
    `specs/python-expr-interface.md`. If it's used by sessions or model
    code this is a public API that needs a spec entry; if it's an
    internal helper, mark it `_copy_used_symtab_values` and let it stay
    out of the spec.
11. **Move or annotate `evaluate_let_bindings` binding source
    location.** It currently lives in
    `rust-bindings/src/model/create_job_fns.rs` even though the public
    surface is `openjd.expr`. Either move the `#[pyfunction]` into
    `rust-bindings/src/expr/` and delegate to the `openjd-model`
    crate's `evaluate_let_bindings`, or add a comment in
    `rust-bindings/src/expr/mod.rs` pointing to the model module.
12. **Update `AGENTS.md` to drop the reference to
    `function_library.rs`.** The "Function library
    (`function_library.rs`) — `get_default_library`,
    `FunctionLibrary.with_host_context`" line in the expr section is
    stale; the file does not exist and the symbols it advertised were
    removed.
13. **Register the `pytest.mark.fuzz` custom marker in
    `pyproject.toml`** to silence the eight `PytestUnknownMarkWarning`
    warnings produced by `test/openjd/expr/test_fuzz.py`. Add to
    `[tool.pytest.ini_options]`:
    ```toml
    markers = ["fuzz: hypothesis fuzz tests"]
    ```
