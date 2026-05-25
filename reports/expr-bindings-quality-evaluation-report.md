# openjd-expr Bindings Quality Evaluation Report

**Date:** 2026-05-25
**Component:** `openjd.expr`
**Reference branch:** `openjd-model-for-python` @ `mwiebe/expr` (fork)
**Binding commit:** `8f19e4d` (`bindings-rs` branch)

## Executive Summary

The Rust-backed `openjd.expr` bindings are in very good shape and are a
near-faithful drop-in for the pure-Python reference. All 1,765 tests pass
cleanly, every public symbol promised by `specs/python-expr-interface.md`
is present and importable, every value-shaped type implements the
equality and pickle contracts the spec advertises, and clippy is clean
across `rust-bindings/src/expr/` (every clippy warning the workspace
emits today comes from `model/` or `sessions/`, not `expr/`). Lint —
ruff, black, mypy — is fully green.

The remaining gaps are six concrete behaviour divergences from the
pure-Python reference, all newly captured as xfail tests in
`test/openjd/expr/test_known_gaps.py`. Five are exception-class /
no-error-raised mismatches on edge cases (`ExprValue.unresolved(...)
.item()` and `str(...)`, mixed-type list construction, and
`ExprType(TypeCode.UNRESOLVED)` arity validation); one is a missing
`hash` on `PathFormat` that breaks pickle/dict-key consistency with the
other binding-side enums (`TypeCode`, `ExprRevision`). All of these are
small and localised. There are no spec-omission gaps, no missing
binding-side tests against reference behaviour, no PyO3 hygiene issues,
and no parity gaps in the larger-scope surfaces (parsing, evaluation,
format-string resolution, path mapping, range expressions, profiles).

## 1. Python Interface Spec Review

`specs/python-expr-interface.md` (522 lines) describes the public
API completely and accurately. Every symbol the spec advertises is
exposed by `src/openjd/expr/__init__.py` and registered by
`rust-bindings/src/lib.rs`; every binding-registered symbol appears in
the spec.

Coverage cross-check (spec → binding):

| Spec section | Spec symbol | Bound? |
|---|---|---|
| Functions | `evaluate_expression` | ✓ |
| Functions | `parse_expression` | ✓ |
| Functions | `evaluate_let_bindings` | ✓ (registered via `model::create_job_fns`, re-exported through `openjd.expr.__init__`) |
| Functions | `escape_format_string` | ✓ |
| Types | `ExprType` | ✓ |
| Types | `TypeCode` (16 variants) | ✓ — every spec'd variant present |
| Types | `ExprValue` | ✓ |
| Types | `SymbolTable` | ✓ |
| Types | `ExprRevision` | ✓ |
| Types | `ExprExtension` | ✓ (`.ALL` returns `[]` today, by design) |
| Types | `HostContext` | ✓ |
| Types | `ExprProfile` | ✓ |
| Types | `ParsedExpression` | ✓ |
| Types | `PathFormat` | ✓ |
| Types | `PathMappingRule` | ✓ |
| Types | `RangeExpr` | ✓ |
| Types | `FormatString` | ✓ |
| Exceptions | `ExpressionError` | ✓ |
| Exceptions | `ExpressionTypeError` | ✓ |
| Exceptions | `RangeExprError` | ✓ |
| Exceptions | `FormatStringValidationError` | ✓ |
| Constants | `DEFAULT_MEMORY_LIMIT` | ✓ (= 100,000,000) |
| Constants | `DEFAULT_OPERATION_LIMIT` | ✓ (= 10,000,000) |

Reverse direction (binding → spec): no binding-registered Python-public
symbols are absent from the spec. `_reconstruct_expr_value`,
`_reconstruct_enum`, `_reconstruct_kwargs` are intentionally
underscore-prefixed pickle helpers and correctly excluded from the spec.

The spec's "Equality and hashability" callouts on `PathMappingRule`,
`FormatString`, `HostContext`, `ExprProfile`, `SymbolTable`, and
`RangeExpr` are honoured by the bindings (verified by 43 tests in
`test_equality.py`). The "Pickle Support" table is also honoured (22
tests in `test_pickle.py`). The spec is silent on `ExprValue` /
`PathFormat` hashability, but see §7 (Exploratory Findings) and §8
(Recommendations) for the inconsistency this leaves.

The spec does not document the binding's intentional addition of
`SymbolTable.symbols` (vs. the reference's `keys` only),
`SymbolTable.union(*others)`, or `RangeExpr.from_list`; all three
appear in the spec under their respective type sections and are
covered by tests, so this is not a spec gap.

## 2. PyO3 Binding Source Review

`rust-bindings/src/expr/` contains 12 files totalling ~95 KB; one
helper module (`pickle_helpers.rs`) is shared with `model` and
`sessions`. Per-file findings:

* **`mod.rs`** — clean `pub(crate) mod` / `pub(crate) use` re-export
  hub. No issues.
* **`lib.rs`** (registration only) — every expr `#[pyclass]` is
  `add_class`-registered with the public name; every exception is
  registered through `register_renamed_exception` so `__module__`,
  `__name__`, `__qualname__` all read `openjd.expr.<Name>`
  (verified at runtime — see §7). Pickle-helper functions
  `_reconstruct_enum` / `_reconstruct_kwargs` are exposed as private
  module-level functions so existing pickled bytes can still load.
  `pyo3_log::Logger` install at module init bridges Rust crate
  targets (`openjd_expr`) to Python's `openjd.expr` logger
  hierarchy.
* **`profile.rs`** — `PyExprRevision`, `PyExprExtension`,
  `PyHostContext`, `PyExprProfile`. All implement the spec's
  equality/hash contract; `host_context_eq` / `host_context_hash`
  helpers are factored out cleanly because `openjd_expr::HostContext`
  doesn't derive `PartialEq`/`Hash`, and `ExprProfile.__hash__`
  canonicalises the extension set as a sorted-by-debug-repr `Vec`
  to avoid `HashSet` iteration-order instability. `__reduce__` for
  every type round-trips through the documented constructor or
  classmethod.
* **`format_string.rs`** — `PyFormatString` and
  `escape_format_string`. `validate_expressions` is exposed (resolved
  one of the previous report's P2 items). `__eq__` and `__hash__`
  reduce to the raw input string per spec contract. `__reduce__`
  through the constructor.
* **`parsed_expression.rs`** — `PyParsedExpression` plus the
  `parse_expression` pyfunction. `peak_memory_usage` and
  `operation_count` use `AtomicUsize` so the metric reads after
  evaluation are GIL-free; the type is intentionally not pickleable
  per spec.
* **`evaluate.rs`** — `evaluate_expression` and the
  `profile_for_call` helper that resolves an optional `profile=` to
  a `FunctionLibrary` via the upstream per-profile cache. Note that
  `library=` was removed in commit `8f19e4d`; only `profile=`
  remains. The function uses the upstream `Arc<FunctionLibrary>`
  cache so concurrent calls with the same profile share an
  allocation.
* **`errors.rs`** — `PyExpressionError` / `PyExpressionTypeError` /
  `PyRangeExprError` / `PyFormatStringValidationError` declared via
  `create_exception!`, plus `attach_expression_error_methods` which
  installs the reference's keyword constructor and decoration
  methods (`with_context`, `message_with_expr_prefix`) onto
  `ExpressionError` at module init by compiling them as Python
  `function` objects so the descriptor protocol binds them to
  instances correctly. The trick is documented in detail at the top
  of the file. `ExpressionTypeError` inherits the methods through
  normal class inheritance.
* **`symbol_table.rs`** — `PySymbolTable`. `__eq__` recurses
  through subtables via the helper `symbol_table_eq`, which walks
  the underlying `openjd_expr::SymbolTable` (which doesn't derive
  `PartialEq`). Not hashable, intentionally — `__setitem__` makes
  the type mutable. `__repr__` walks top-level keys in sorted order
  for determinism. `__reduce__` flattens to a `dict[str,
  ExprValue]` of all dotted leaf paths, which round-trips through
  `__init__`.
* **`path_mapping.rs`** — `PyPathMappingRule`. Implements `__eq__`
  and `__hash__` over the three fields. The minor cosmetic point in
  §7 is that `__repr__` formats `source_path_format` via `{:?}`,
  which prints the underlying Rust enum's debug name (`Posix`)
  rather than the user-facing Python enum name (`POSIX`).
* **`expr_value.rs`** — `PyExprValue`, `_reconstruct_expr_value`,
  `PyExprValueIter`, plus the `py_to_expr_value` /
  `expr_value_to_py` conversion helpers. The `Unresolved(_) =>
  py.None()` arm in `expr_value_to_py` is the root cause of the
  `.item()` and `str()` divergences in §7.
* **`expr_type.rs`** — `PyExprType` and `PyTypeCode`. Note the
  `unreachable!` panic on a future `TypeCode` variant addition: the
  binding will surface a panic at the boundary rather than silently
  collapse to `ANY`, which is correct per the comments. `__reduce__`
  through the spec-form string.
* **`path_format.rs`** — `PyPathFormat`. **The only PyO3 issue
  found in this audit:** the `#[pyclass(...)]` config has `eq,
  eq_int` but **no `hash`**. Compare to `PyTypeCode` which is
  `#[pyclass(..., hash, ...)]`. As a result `hash(PathFormat.POSIX)`
  raises `TypeError`. See §7 / §8 / `test_known_gaps.py`.
* **`range_expr.rs`** — `PyRangeExpr` plus `PyRangeExprIter`.
  `__eq__` and `__hash__` defer to the underlying Rust impls.
  `__reduce__` through the canonical string form.

PyO3-specific concerns (per the SKILL.md checklist):

* **Exception class registration** — every `create_exception!`
  exception in `errors.rs` is registered through
  `register_renamed_exception` in `lib.rs`. Verified at runtime that
  all four expose `__module__ = 'openjd.expr'`, `__name__ =
  '<PublicName>'`, `__qualname__ = '<PublicName>'`. Pickled error
  bytes correctly contain `openjd.expr` (verified for
  `FormatStringValidationError` and `ExpressionError` round-trip).
* **Type conversions** — `int` / `i64` boundary is handled
  explicitly: `py_to_expr_value` maps PyO3's `OverflowError` to
  `ExpressionError("Integer overflow: …")` so the error class
  matches the reference contract for out-of-range integers.
  `Decimal` conversion goes through real `isinstance(decimal_cls)`
  rather than a name check, so user `Decimal` subclasses are
  accepted and unrelated `Decimal`-named classes are not.
  `pathlib.Path` conversion in `path_mapping.rs::extract_path_arg`
  validates POSIX vs Windows pathlib types against the format kwarg.
* **GIL handling** — expr evaluation is fast and CPU-bound; no
  `Python::allow_threads` is needed and none is used. Concurrent
  evaluation from 10 threads succeeds (smoke probe — see §7).
* **`#[pyclass]` constructor signatures** — every `#[new]`
  signature matches the spec. `PyExprValue::new(value, type=None,
  path_format=None)`, `PyPathMappingRule::new(*, source_path_format,
  source_path, destination_path)`, `PyExprProfile::new(revision=None,
  *, extensions=None, host_context=None)` are all aligned.
* **ABI3 compatibility** — `Cargo.toml` declares `abi3-py39`. No
  Python C-API leaks observed.
* **Stub generation** — `src/openjd/_openjd_rs.pyi` is up to date
  for every expr symbol (verified by `grep` for class/function
  declarations).

## 3. Python Wrapper Module Review

`src/openjd/expr/__init__.py` (75 lines) is a flat re-export from
`openjd._openjd_rs`. Every symbol promised by the spec is in `__all__`
and the spec's import paths resolve. The module-level docstring
intentionally points out that no Python-side fix-up is needed for
exception class names because `register_renamed_exception` runs
Rust-side, and that the `ExpressionError` keyword constructor /
decoration methods are installed Rust-side via
`attach_expression_error_methods`.

`__all__` length is 23, matching the 23 spec-listed symbols (4
functions + 14 types + 4 exceptions + 2 constants — note the spec
file counts `evaluate_let_bindings` separately under "Functions"
even though it shares import surface with model). No internal-only
names leak.

`py.typed` is present; the package is mypy-clean (`hatch run typing`
reports 0 issues).

## 4. Test Review

`test/openjd/expr/` contains 32 test files with a total of 1,765
passing tests + 24 skipped + 6 xfail, run by
`hatch run test-subset test/openjd/expr` in 5 seconds wall clock.
Five files are binding-specific extras over the reference test set:

| File | Tests | Purpose |
|---|---:|---|
| `test_copy_used_symtab.py` | 9 | Pinning the binding-only `FormatString.copy_used_symtab_values` method (no reference equivalent). |
| `test_equality.py` | 43 | Pinning the eq/hash contract on `PathMappingRule`, `FormatString`, `HostContext`, `ExprProfile`, `SymbolTable`. |
| `test_format_string_validate.py` | 14 | Pinning `FormatString.validate_expressions` and the `FormatStringValidationError` class. |
| `test_pickle.py` | 22 | Pickle round-trip for every spec-listed value type. |
| `test_known_gaps.py` | 6 (xfail) | Failing tests for the gaps in §7. |

The remaining 27 files are 1:1 with reference test files. Test counts
per file are at parity or exceed the reference, with two exceptions:

* **`test_types.py`**: 113 binding tests vs. 122 reference tests.
  Of the 9 missing reference tests, several import private-only
  helpers (`from openjd.expr._types import T1`) or use
  reference-only shortcut constants (`ExprType.INT`,
  `ExprType.LIST_INT`) that are explicitly absent from the binding
  per spec policy ("The binding deliberately does not expose
  class-level shortcut constants…"). Five of the genuinely
  behaviour-portable cases are now in `test_known_gaps.py` (see §7).
* **`test_uri_paths.py`**: 35 binding tests vs. 73 reference tests.
  The reference test set imports `from openjd.expr._uri_path import
  is_uri, split_uri, uri_parts, …` — pure-Python helpers that are
  not part of the public contract and have no exposed Python
  equivalent in the bindings. The Rust crate exposes these as
  internal helpers used by the path operators, but they are not
  spec-public, so the test loss here is by design and not a gap.

Test organisation follows clear behaviour-domain groupings (paths
separate from URI paths separate from path mapping; types separate
from values; arithmetic, comparison, lists, strings each in their
own file). Every error-formatting test asserts on the full message
text, not just on the exception class — matching the project's
"assert on full error message content" standard from `AGENTS.md`.

## 5. Parity with Pure-Python Reference

Symbol-by-symbol comparison against `mwiebe/openjd-model-for-python`
`expr` branch (the pure-Python reference whose `openjd.expr` package
the bindings replace):

| Symbol | Reference | Binding | Status |
|---|---|---|---|
| `evaluate_expression(expr, *, values=, profile=, target_type=, memory_limit=, operation_limit=, path_format=)` | `library=` (replaced by `profile=`) | profile-only | ✓ — spec calls out `library=`→`profile=` consolidation, intentional in `8f19e4d` |
| `parse_expression(expr)` | same | same | ✓ |
| `evaluate_let_bindings(bindings, symtab, *, profile=)` | takes `library=` (in `model.__init__`) | takes `profile=`, lives in `openjd.expr` | ✓ — moved to expr package per §1, profile-only |
| `escape_format_string(value)` | from `model._format_strings` | from `openjd.expr` | ✓ — relocated per spec |
| `ExprType` | construction from string + TypeCode + class shortcut constants | string + TypeCode (no shortcut consts) | ✓ — shortcuts intentionally absent per spec |
| `ExprType.match_type` | `match` (Python keyword) | `match_type` (renamed for Rust parity) | ✓ — spec calls out the rename |
| `ExprType(TypeCode.UNRESOLVED)` | raises `ValueError("exactly one type parameter")` | accepted | ⚠ — see §7, gap #5 |
| `TypeCode` (16 variants) | same | same | ✓ |
| `ExprValue(value, type=, path_format=)` | accepts `evaluator=` kwarg also | no `evaluator=` (Pydantic-side concept) | ✓ — intentional drop |
| `ExprValue.unresolved(t)` | classmethod | classmethod | ✓ |
| `ExprValue.from_float(value, original_str)` | n/a (Pydantic uses `Decimal`) | staticmethod | ✓ — binding-only, by design |
| `ExprValue.null()` | classmethod | not exposed | ⚠ — minor; `ExprValue(None)` works |
| `ExprValue.unresolved(...).item()` | raises `ExpressionTypeError` | returns `None` | ⚠ — see §7, gap #2 |
| `str(ExprValue.unresolved(...))` | raises `ExpressionTypeError` | returns `'<unresolved[T]>'` | ⚠ — see §7, gap #3 |
| `ExprValue([1, "hello"])` | raises `TypeError("incompatible types")` | raises `ValueError` | ⚠ — see §7, gap #4 |
| `ExprValue([unresolved, 42])` | raises `TypeError("Cannot construct…")` | raises `ValueError` | ⚠ — see §7, gap #4 |
| `SymbolTable(source=)` | same | adds positional `init=` and keyword `source=` (back-compat) | ✓ |
| `SymbolTable.keys` | top-level set | same | ✓ |
| `SymbolTable.symbols` | n/a | dotted-path leaves set | ✓ — binding-side enrichment, in spec |
| `SymbolTable.union(*others)` | n/a | accepts SymbolTable / dict | ✓ — binding-side enrichment, in spec |
| `SymbolTable.__eq__` | n/a (no `__eq__`) | recursive value equality | ✓ — binding-side enrichment, in spec |
| `SymbolTable.__hash__` | n/a | intentionally not hashable | ✓ |
| `PathFormat` | `str` Enum (`PathFormat.POSIX`, `WINDOWS`, `URI`) | `#[pyclass]` enum, eq+eq_int | ⚠ — not hashable; see §7, gap #1 |
| `PathFormat.name` | inherits from `str` | explicit getter | ✓ |
| `PathMappingRule(*, source_path_format, source_path, destination_path)` | requires PurePosixPath/PureWindowsPath at construction | accepts str or pathlib | ✓ — more permissive; spec example uses str |
| `PathMappingRule.from_dict / to_dict` | same | same | ✓ |
| `PathMappingRule.apply(path, output_format=)` | apply only | apply + apply_with_format | ✓ — superset |
| `PathMappingRule.__eq__ / __hash__` | inherits from frozen dataclass | manual impl on three fields | ✓ |
| `PathMappingRule.__repr__` | `PathMappingRule(source_path_format=<PathFormat.POSIX: 'POSIX'>, …)` | `PathMappingRule(source_path_format=Posix, …)` | ⚠ — see §7, gap #6 (cosmetic) |
| `RangeExpr` (constructor, `start`, `end`, `len`, `__contains__`, `__iter__`, `__getitem__`, `ranges()`, `from_list`, eq+hash) | dataclass | matches | ✓ |
| `RangeExpr.from_list([])` | `ValueError` | `ValueError("Range expression cannot be empty")` | ✓ |
| `FormatString` (lives in `_format_strings` in reference, in `openjd.expr` in binding) | `FormatStringError` exception | `FormatStringValidationError` (different name) | ✓ — binding-side rename per spec; the `validate_expressions` method exposes the new error class explicitly |
| `FormatString.resolve(*, symtab, library=, target_type=, path_format=)` | `library=` | `*, profile=` | ✓ — profile-only consolidation |
| `FormatString.resolve_string` | n/a (returns ExprValue always) | string-only return | ✓ — binding-side ergonomics, in spec |
| `FormatString.validate_expressions` | n/a (rfc-only on Rust side) | exposed | ✓ — binding-side, in spec |
| `FormatString.copy_used_symtab_values` | n/a | exposed | ✓ — binding-side, used by sessions |
| `FormatString.__eq__ / __hash__` | inherits from `str` (subclass of `DynamicConstrainedStr`) | on `raw()` | ✓ — spec contract |
| `ExprProfile`, `ExprRevision`, `ExprExtension`, `HostContext` | n/a | new in binding | ✓ — binding-side, in spec |
| `ParsedExpression.evaluate(values=, profile=, …)` | `library=` | `profile=` | ✓ — profile-only |
| `ParsedExpression.peak_memory_usage / operation_count` | same | same | ✓ |
| `ExpressionError(message, *, expr=, node=, lineno=, col_offset=)` | dataclass-style | `attach_expression_error_methods` | ✓ — message format matches |
| `ExpressionError.with_context / message_with_expr_prefix` | methods | methods | ✓ |
| `RangeExprError`, `FormatStringValidationError` | `RangeExprError`, `FormatStringError` | same / renamed | ✓ |
| `DEFAULT_MEMORY_LIMIT`, `DEFAULT_OPERATION_LIMIT` | 100 MB, 10 M | identical values | ✓ |
| Pickle round-trip for all value types | covered by reference's pydantic glue | covered by 22 tests in `test_pickle.py` | ✓ |
| `FunctionLibrary`, `FunctionSignature`, `get_default_library` | exposed | **removed in `8f19e4d`** | ✓ — intentional per spec ("…profile= is the single way to configure evaluation") |

Symbol-level summary: **all 23 spec-public symbols exposed and
behaviorally aligned with the reference**, modulo six small
behaviour gaps (one missing hash, four exception-class mismatches,
one cosmetic repr) captured in `test_known_gaps.py` and listed in
§7 / §8.

## 6. Build and Test Results

```
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml
Finished `dev` profile [unoptimized + debuginfo] target(s) in 5.84s
📦 Built wheel for abi3 Python ≥ 3.9 to /home/markw/openjd-model-for-python/target/wheels/openjd_model-…-cp39-abi3-linux_x86_64.whl
🛠 Installed openjd-model-…
```
(The `scripts/maturin_build.py develop` invocation is run via
`hatch run test-subset` per the project's normal flow; the
extension was successfully rebuilt before tests.)

```
$ hatch run test-subset test/openjd/expr
============================== test session starts ===============================
collected 1795 items

test/openjd/expr/test_arithmetic.py ............................................. 55 passed
…
test/openjd/expr/test_known_gaps.py xxxxxx                                      6 xfailed
…
============= 1765 passed, 24 skipped, 6 xfailed, 8 warnings in 4.70s =============
```

```
$ hatch run lint
cmd [1] | ruff check src test
All checks passed!
cmd [2] | black --check --diff src test
All done! ✨ 🍰 ✨
154 files would be left unchanged.
cmd [3] | mypy src test
Success: no issues found in 103 source files
```

```
$ cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets
…
warning: `openjd-python` (lib) generated 56 warnings (run `cargo clippy --fix --lib -p openjd-python` to apply 1 suggestion)
warning: `openjd-python` (lib test) generated 56 warnings (56 duplicates)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.41s
```

The 56 clippy warnings are workspace-wide; **zero are in
`rust-bindings/src/expr/`**. Filtered output (`grep -E "src/expr/"`)
returns no matches. Every warning is in `model/types.rs`,
`model/profile.rs`, `model/job.rs`, `model/step_dependency_graph.rs`,
`sessions/types.rs`, or `sessions/session_user.rs`. Those are
issues for the model and sessions evaluations, not this report.

Stub-gen check: `src/openjd/_openjd_rs.pyi` already contains every
expr symbol — `ExprExtension`, `ExprProfile`, `ExprType`, `ExprValue`,
`FormatString`, `HostContext`, `ParsedExpression`, `PathMappingRule`,
`RangeExpr`, `SymbolTable`, `ExprRevision`, `PathFormat`, `TypeCode`,
`RangeExprError`, `FormatStringValidationError` — and the public
functions (`escape_format_string`, `evaluate_expression`,
`evaluate_let_bindings`, `parse_expression`). No drift detected in
the audit.

## 7. Exploratory Findings

Six concrete gaps surfaced via exploratory smoke-testing against the
binding. All six now have failing-test demonstrations in
`test/openjd/expr/test_known_gaps.py` (xfail-marked); when each is
resolved, the corresponding test moves to its proper home in the
companion test file (e.g. `test_pickle.py` for hash-related cases,
`test_expression_value.py` for unresolved `.item()` / `str()` cases,
`test_types.py` for the `ExprType` arity case).

1. **`PathFormat` is not hashable.**
   `hash(PathFormat.POSIX)` raises `TypeError: unhashable type:
   'openjd.expr.PathFormat'`. `TypeCode` and `ExprRevision`, both
   declared via `#[pyclass]`-enum in the same directory, are
   hashable. Cause: the `#[pyclass(...)]` config in
   `rust-bindings/src/expr/path_format.rs` declares `eq, eq_int`
   but not `hash`. Cross-cut: this also means `PathFormat` cannot
   be a dict key, set member, or appear inside any
   hash-equality-implying structure. Pinned by
   `test_known_gaps.py::test_path_format_is_hashable`.
2. **`ExprValue.unresolved(T).item()` returns `None`.**
   The pure-Python reference raises `ExpressionTypeError("Cannot
   extract value from unresolved[T]: value is not known")`. Cause:
   the `ExprValue::Unresolved(_) => py.None()` arm in
   `expr_value_to_py` (`rust-bindings/src/expr/expr_value.rs`)
   silently collapses unresolved to None. Pinned by
   `test_known_gaps.py::test_unresolved_item_raises`.
3. **`str(ExprValue.unresolved(T))` returns `'<unresolved[T]>'`.**
   The reference raises `ExpressionTypeError("Cannot convert
   unresolved[T] to string: value is not known")`. Cause: the
   binding's `__str__` delegates to
   `ExprValue::to_display_string` which has a printable-debug
   branch for `Unresolved`. Same surface as #2. Pinned by
   `test_known_gaps.py::test_unresolved_str_raises`.
4. **List-construction errors raise `ValueError` instead of `TypeError`.**
   `ExprValue([1, "hello"])` and `ExprValue([unresolved, 42])`
   both raise `ValueError` on the binding (`"make_list expected
   int element, got string"` and `"Cannot create list from
   unresolved elements"`); the reference raises `TypeError`
   (`"incompatible types"` and `"Cannot construct a list
   containing unresolved values"`). Cause:
   `ExprValue::make_list` errors are mapped through
   `pyo3::exceptions::PyValueError::new_err(...)` in
   `expr_value.rs::py_to_expr_value`. The error class change is a
   small, low-risk fix. Pinned by
   `test_known_gaps.py::test_mixed_type_list_raises_type_error`
   and `…::test_list_with_unresolved_raises_type_error`.
5. **`ExprType(TypeCode.UNRESOLVED)` accepts a 0/2-arity construction.**
   The reference raises `ValueError("exactly one type
   parameter")`. The binding's `PyExprType::new` builds an
   `ExprType` from a `TypeCode` and an empty params vec without
   arity validation, deferring to `ExprType::new` upstream which
   in turn allows non-canonical shapes. The shape returned has
   `to_string() == "unresolved"` (no parameter), which is unusable
   in evaluation. Pinned by
   `test_known_gaps.py::test_unresolved_type_requires_exactly_one_param`.
6. **`PathMappingRule.__repr__` shows the Rust debug name for `PathFormat`.**
   `repr()` on a rule prints
   `source_path_format=Posix` (Rust enum variant debug name)
   instead of `source_path_format=POSIX` or
   `source_path_format=PathFormat.POSIX` (Python convention).
   Cause: the format string in
   `rust-bindings/src/expr/path_mapping.rs::__repr__` uses `{:?}`
   on the inner `PathFormat`. Cosmetic; not pinned by an xfail
   test (no behaviour assertion to make).

Other exploratory findings that ARE working correctly (no gaps):

* Full pickle round-trip for `ExpressionError` preserves the
  `expr`, `lineno`, `col_offset`, and `node` attributes;
  `__module__` is `'openjd.expr'`. Pickled bytes contain
  `b'openjd.expr'`.
* `FormatStringValidationError` pickles correctly under
  `openjd.expr.FormatStringValidationError`.
* Concurrent evaluation from 10 Python threads through
  `evaluate_expression` succeeds with consistent results.
* i64 boundary integers (`2**63 - 1`, `-2**63`) round-trip cleanly;
  out-of-range values raise `ExpressionError("Integer overflow:
  …")` (matches reference contract).
* NaN/Inf floats are rejected at construction time with
  `ValueError("Float operation produced NaN/infinity")` — this is
  the upstream Rust crate's behaviour and matches reference
  semantics (no silent NaN propagation).
* `ExprRevision` and `TypeCode` enums hash and pickle correctly,
  and the pickled bytes carry the `openjd.expr` module path so
  cross-process round-trips work.
* `evaluate_let_bindings` (registered in the model module,
  re-exported through `openjd.expr.__init__`) accepts `profile=`
  as a keyword-only kwarg per spec.
* `FormatString.validate_expressions(symtab, *, profile=None)`
  raises `FormatStringValidationError` (a `ValueError` subclass)
  with a caret-anchored, byte-offset-bearing diagnostic on the
  first failing segment.
* Equality and hash on `PathMappingRule`, `FormatString`,
  `HostContext`, `ExprProfile`, `RangeExpr` are consistent with
  Python's hash/eq contract — equal objects hash equal, and the
  types are usable as dict keys / set members.
* `SymbolTable.__eq__` walks subtables recursively; insertion
  order on the underlying `HashMap` does not affect equality.

## 8. Recommendations

Listed in priority order. Each item references either a specific
file path or a specific failing xfail test so the report-driven
workflow in `~/openjd-rs/AGENTS.md` can resolve it precisely.

### P1 — Reference parity / behaviour bugs

1. ~~**Make `PathFormat` hashable.** Add `hash` to the
   `#[pyclass(module = "openjd.expr", name = "PathFormat", eq, eq_int,
   from_py_object)]` line in `rust-bindings/src/expr/path_format.rs`
   so it matches `PyTypeCode` / `PyExprRevision`. When the change
   lands, move
   `test_known_gaps.py::test_path_format_is_hashable` to
   `test_pickle.py` (or a new `test_enum_hash.py`) alongside the
   existing pickle round-trip tests for `PathFormat`.~~ **Resolved.**
   Added `hash, frozen` to the `#[pyclass(...)]` config and the
   matching `Eq, Hash` to the `#[derive(...)]`. The xfail moved to
   `test_paths.py::TestPathFormatHashability` (4 tests covering
   self-hash, distinct-variant distinct-hash, set membership, and
   dict-key usage).
2. ~~**Raise `ExpressionTypeError` from `ExprValue.unresolved(T).item()`.**
   The `ExprValue::Unresolved(_) => py.None()` arm in
   `rust-bindings/src/expr/expr_value.rs::expr_value_to_py` should
   raise `ExpressionTypeError("Cannot extract value from
   unresolved[T]: value is not known")` to match the reference
   contract. When resolved, move
   `test_known_gaps.py::test_unresolved_item_raises` to
   `test_expression_value.py`.~~ **Resolved.** `expr_value_to_py`
   converted from infallible `Py<PyAny>` → fallible
   `PyResult<Py<PyAny>>`; the `Unresolved(t)` arm now raises
   `ExpressionTypeError` with the spec'd message. The pickle path
   (`__reduce__`) special-cases unresolved before calling the
   helper, so pickle round-trips still work. The xfail moved to
   `test_expression_value.py::TestUnresolvedExtraction`.
3. ~~**Raise `ExpressionTypeError` from `str(ExprValue.unresolved(T))`.**
   Same surface as #2 — `__str__` should consult the `is_unresolved`
   path and raise instead of returning the debug-style display
   string. When resolved, move
   `test_known_gaps.py::test_unresolved_str_raises` alongside #2 in
   `test_expression_value.py`.~~ **Resolved.** `__str__` now
   special-cases `Unresolved` and raises the spec'd
   `ExpressionTypeError("Cannot convert unresolved[T] to string:
   value is not known")`. `__repr__` deliberately does *not* raise
   (Python convention: `repr` is for debugging and should never
   raise) — pinned by
   `test_expression_value.py::TestUnresolvedExtraction::test_repr_does_not_raise_on_unresolved`.
4. ~~**Raise `TypeError` (not `ValueError`) on incompatible list-element types.**
   …~~ **Resolved.** Both `ExprValue::make_list` call sites in
   `expr_value.rs` now route through a new `make_list_err_to_py`
   helper that wraps the upstream "make_list expected X element,
   got Y" message into the reference's "List contains incompatible
   types: X, Y" form, and the special unresolved-element case into
   "Cannot construct a list containing unresolved values…". Both
   raise `TypeError`, matching the reference contract. The two
   xfails moved to
   `test_lists.py::TestExprValueListConstructionErrors`. (Note:
   `[1, 2.0]` is intentionally still allowed — that's int→float
   numeric promotion, not a heterogeneous-type rejection.)
5. ~~**Validate arity for non-zero-parameter `TypeCode` variants in `ExprType.__init__`.**
   …~~ **Resolved.** New `validate_typecode_arity` helper in
   `expr_type.rs` enforces:
   - `Unresolved` and `List` must have exactly one type parameter
   - Primitives (`Int`, `String`, `Bool`, `Float`, `Path`,
     `NullType`) must have zero
   - `Union` is intentionally exempt — the upstream
     `normalize_union` deliberately accepts any number of
     parameters and unwraps single-element unions to the element /
     turns zero-element unions into `NoReturn`. The new test class
     `test_types.py::TestExprTypeArityValidation` pins this
     normalisation as well as the rejection cases. The xfail
     moved there.

### P2 — Polish / housekeeping

6. ~~**Render `PathMappingRule.source_path_format` using its Python name in `__repr__`.**
   `rust-bindings/src/expr/path_mapping.rs::__repr__` uses `{:?}` on
   the inner `PathFormat`, producing `Posix` / `Windows` / `Uri`.
   Either format the corresponding `PyPathFormat` (which yields
   `POSIX` / `WINDOWS` / `URI` via its `name` getter) or hand-write
   the variant string. Cosmetic only; no failing test today, but
   reproduces in IDE tooltips and traceback inspection.~~
   **Resolved.** `__repr__` now formats as
   `source_path_format=PathFormat.POSIX` (matching how Python's
   own enums repr themselves and how the rest of the binding's
   pyclass enums render). A pub-crate `PyPathFormat::variant_name`
   method exposes the variant string outside `#[pymethods]` for use
   from the path-mapping module. Pinned by 3 new tests in
   `test_path_mapping.py::TestPathMappingRuleRepr`.
7. **Consider exposing `ExprValue.null()` as a classmethod.**
   The reference exposes `ExprValue.null()` as a convenience
   classmethod that returns `ExprValue(None)`. The binding requires
   `ExprValue(None)`, which works — but adding the explicit
   classmethod removes a small porting friction for code coming
   from `openjd.expr` v0. If adopted, document in the spec under
   `ExprValue` as a "Special constructors" entry.
8. ~~**Document the binding's behaviour for unresolved value `.item()` / `str()` once #2/#3 are resolved.**
   The spec's ExprValue section currently shows `.item()` returning
   the native Python value but doesn't explicitly cover the
   unresolved case. Once the behaviour is unified with the
   reference (raises `ExpressionTypeError`), add a one-line note in
   the `ExprValue` section calling out the contract: "`.item()` and
   `str()` on an unresolved value raise `ExpressionTypeError`."~~
   **Resolved.** Added an "Unresolved values" subsection to the
   `ExprValue` section in `specs/python-expr-interface.md` covering
   the three contracts: `.item()` raises, `str(...)` raises, and
   `repr(...)` returns a debug-friendly string without raising
   (Python convention).
