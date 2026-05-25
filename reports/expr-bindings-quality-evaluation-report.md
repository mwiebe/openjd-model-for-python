# openjd-expr Bindings Quality Evaluation Report

**Date:** 2026-05-22
**Component:** `openjd.expr`
**Reference branch:** `mwiebe/openjd-model-for-python` `fork/expr`

## Executive Summary

The `openjd.expr` Rust→Python bindings are in a strong state. The
public surface advertised by `specs/python-expr-interface.md` is fully
backed by live PyO3 classes and functions, the wrapper module
`src/openjd/expr/__init__.py` re-exports everything cleanly under the
canonical names, and the test suite passes 1707 / 1707 (25 platform
skips). Clippy reports zero warnings under `rust-bindings/src/expr/`,
the test_known_gaps.py landing pad is currently empty (no known
behavioural xfails), and the previously-tracked correctness bugs
around per-call path-mapping rules and target-type propagation no
longer exist — `apply_path_mapping` now flows through a `HostContext`
that is part of `ExprProfile`, and target types are forwarded
end-to-end.

The remaining work is housekeeping rather than correctness. The
five value/profile pyclasses that originally lacked
`__eq__`/`__hash__` (`PathMappingRule`, `FormatString`,
`HostContext`, `ExprProfile`, `SymbolTable`) all now compose
value-shaped equality from their visible fields — see
Recommendations 1-5. The `FormatStringValidationError` exception
class is registered but is not reachable from any public binding
entry point today. The test-suite lint debt called out in the
original draft of this report (16 ruff
errors under `test/openjd/expr/` plus 2 stragglers in a model_v1
test file, totalling 18 workspace-wide) has been fully resolved
(see Recommendation #10); `hatch run lint` is now clean.
None of the remaining items block users of the bindings.

## 1. Python Interface Spec Review

`specs/python-expr-interface.md` documents the full surface of
`openjd.expr` as advertised through the wrapper module, organised by
functions / types / exceptions / constants / pickle support. Every
section in the spec maps to a real binding symbol, and every symbol
reachable as `openjd.expr.X` corresponds to a documented surface.

Verified at runtime (`python -c "import openjd.expr; dir(openjd.expr)"`)
the public symbol set matches the spec exactly:

```
DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT,
ExprExtension, ExprProfile, ExprRevision, ExprType, ExprValue,
ExpressionError, ExpressionTypeError,
FormatString, FormatStringValidationError, FunctionLibrary,
HostContext, ParsedExpression, PathFormat, PathMappingRule,
RangeExpr, RangeExprError, SymbolTable, TypeCode,
escape_format_string, evaluate_expression, evaluate_let_bindings,
get_default_library, parse_expression
```

**Spec gaps (binding has more than spec advertises):**

- `FormatString.copy_used_symtab_values(source, dest)` is a public
  method on the binding class but is not documented in the spec's
  `FormatString` section. It is exercised by `test_copy_used_symtab.py`,
  so the surface is covered by tests, but the spec does not
  describe its semantics or when callers should use it.
- The spec lists `FormatStringValidationError` as one of the four
  exception types but does not say which entry point raises it.
  After auditing the binding, no public method currently raises it
  (see §2 and §7 below).

**Spec accuracy notes:**

- The spec's "Inspecting a profile" example following the
  `with_host_context(HostContext.unresolved())` line shows
  `profile.host_context  # HostContext.unresolved()`. This is the
  state after the `with_host_context` call, not the default state of
  `ExprProfile()` — which is `HostContext.none()`. The example reads
  cleanly in context but a one-line clarifying comment would prevent
  the reader from misinterpreting the default.
- `evaluate_let_bindings`'s spec example shows `library` as the only
  optional kwarg. The actual binding signature also takes only
  `library=`. Unlike `evaluate_expression`, `parse_expression` and
  `FormatString.resolve*`, it does NOT accept `profile=`. That is
  consistent with the spec but inconsistent with the rest of the
  expr API; consider extending the binding to accept `profile=`
  (with the documented `library` > `profile` > default precedence)
  to match its sibling entry points.

## 2. PyO3 Binding Source Review

Files under `rust-bindings/src/expr/`:

| File | Public type / function | Notes |
|------|------------------------|-------|
| `mod.rs` | (re-exports) | Clean module layout; all types pulled into `lib.rs` via `pub(crate) use ...::*`. |
| `errors.rs` | `PyExpressionError`, `PyExpressionTypeError`, `PyRangeExprError`, `PyFormatStringValidationError`, `attach_expression_error_methods` | All four are `create_exception!`-built `ValueError` subclasses. `attach_expression_error_methods` compiles a small chunk of Python source at module init to install `__init__(message, *, expr=None, node=None, lineno=None, col_offset=None)`, `with_context(expr, node=None)`, and `message_with_expr_prefix(prefix)` on `ExpressionError` — necessary because `abi3-py39` blocks `#[pyclass(extends = PyValueError)]`. The implementation is well-commented and behaves as advertised. |
| `path_format.rs` | `PyPathFormat` | Plain Rust enum with three variants (POSIX, WINDOWS, URI), `eq, eq_int`, `__reduce__` for pickle. From/Into for the underlying `openjd_expr::PathFormat`. |
| `expr_type.rs` | `PyExprType`, `PyTypeCode` | TypeCode covers all 16 known variants; the `From<TypeCode>` mapping uses `unreachable!` as the catch-all (correctly preferring a panic at the binding boundary over silent collapse to `ANY`). `match_type` (renamed from reference `match` because Rust reserves the name) returns `Option[dict[TypeCode, ExprType]]`; `substitute` accepts the same dict shape. Pickle via spec-form string. |
| `expr_value.rs` | `PyExprValue`, `PyExprValueIter`, `_reconstruct_expr_value` | Construction handles `None`/bool/int/float/str/Decimal/list/ExprValue/RangeExpr/ExprType passthroughs. NaN and Inf are rejected; integer overflow → `ExpressionError`. Pickle via a module-level `_reconstruct_expr_value` helper so older pickled bytes still load. |
| `symbol_table.rs` | `PySymbolTable` | Hierarchical dotted-path access, sets+gets via the underlying `SymbolTable`. `keys` returns top-level namespaces, `symbols` returns full dotted leaf paths. `union(*others)` mirrors the reference. Pickle via flat `dict[str, ExprValue]`. `__repr__` walks top-level keys in sorted order so output is deterministic. |
| `profile.rs` | `PyExprRevision`, `PyExprExtension`, `PyHostContext`, `PyExprProfile` | Mirrors `openjd_expr::profile::*` one-to-one. `ExprExtension` is a zero-variant placeholder today (the upstream Rust enum is empty-but-`#[non_exhaustive]`); `unreachable!` on the From impls explicitly documents the situation. `HostContext.with_rules(rules)` accepts an empty list — distinct from `HostContext.none()`, matching the Rust crate. |
| `function_library.rs` | `PyFunctionLibrary`, `get_default_library` | Two constructors: `FunctionLibrary()` (default profile) and `FunctionLibrary.for_profile(profile)` (cached). `host_context_enabled` getter exposes whether `apply_path_mapping` is registered. |
| `parsed_expression.rs` | `PyParsedExpression`, `parse_expression` | Holds last-evaluation peak memory and operation count in `AtomicUsize`. `evaluate(*, values, library, profile, target_type, path_format, memory_limit, operation_limit)` mirrors the spec. Uses `library_for_call(library, profile)` from `evaluate.rs` for consistent precedence. |
| `evaluate.rs` | `library_for_call`, `evaluate_expression` | `library_for_call` documents the `library` > `profile` > default precedence used everywhere. `evaluate_expression` strips leading/trailing whitespace before parsing (matches reference). |
| `path_mapping.rs` | `PyPathMappingRule` | `__init__(*, source_path_format, source_path, destination_path)`, `apply(*, path, output_format=None)`, `to_dict`, `from_dict`. `from_dict` accepts case-insensitive `source_path_format` strings, rejects unknown keys, and produces a Python-set-style error message for the deterministic-set repr. Pickle via `to_dict`/`from_dict`. |
| `range_expr.rs` | `PyRangeExpr`, `PyRangeExprIter` | Constructors `RangeExpr(str)` and `from_str` and `from_list` (rejecting empty input). `__hash__` wraps the underlying Rust hash; `__eq__` compares via `inner == inner`. Pickle via spec-form string. |
| `format_string.rs` | `PyFormatString`, `escape_format_string` | `new(input)` returns `PyExpressionError` on parse failure (the underlying `FormatString::new` returns `ExpressionError` in Rust). `resolve_string` and `resolve` take `(symtab, *, library, profile)`. The `validate_expressions` Rust method (which produces `FormatStringValidationError`) is **not** exposed (see §7). |

### PyO3-specific concerns

| Concern | Status |
|---------|--------|
| Exception class registration | ✅ All four expr exceptions (`ExpressionError`, `ExpressionTypeError`, `RangeExprError`, `FormatStringValidationError`) are wired through `register_renamed_exception` with public module `openjd.expr` and the canonical class name. Verified `repr(e.ExpressionError)` and pickle preserve `openjd.expr.ExpressionError` rather than the `Py`-prefixed internal name. |
| Type conversions | ✅ `int` → `i64` boundary maps `OverflowError` to `ExpressionError("Integer overflow: …")`. NaN/Inf rejected with `ValueError`. `Decimal` accepted via real `isinstance(decimal_cls)` check (not a `__class__.__name__ == "Decimal"` heuristic). `pathlib.Path` types accepted on `PathMappingRule.source_path` matching the declared format. |
| GIL handling | ✅ Expression evaluation is CPU-bound, not blocking I/O — so the binding does not need `Python::allow_threads` here. The expr code paths are short-lived and entirely synchronous; releasing the GIL would cost more in re-acquisition than it saves. |
| `#[pyclass]` constructor signatures | ✅ Every `#[new]` carries `#[pyo3(signature = ...)]` and the .pyi stub matches; spot-checked `ExprValue.__init__(value, type=None, path_format=None)` and `ExprProfile.__init__(revision=None, *, extensions=None, host_context=None)` against the spec. |
| `Py<T>` lifetime correctness | ✅ `FormatString.copy_used_symtab_values` borrows the source `PySymbolTable` immutably and the dest mutably via `borrow_mut()` — no double-borrow patterns observed elsewhere. |
| ABI3 compatibility | ✅ `Cargo.toml` declares `abi3-py39`; the reason `ExpressionError` uses `create_exception!` + `attach_expression_error_methods` rather than `#[pyclass(extends = PyValueError)]` is documented in `errors.rs` as an explicit ABI3 constraint. No leaks of `pyo3-abi3-py312` or other relaxations. |
| Stub generation | ✅ `src/openjd/_openjd_rs.pyi` is in sync with the bindings; spot-checked `FormatString`, `ExprProfile`, `evaluate_let_bindings` signatures. |

## 3. Python Wrapper Module Review

`src/openjd/expr/__init__.py` is a flat re-export from
`openjd._openjd_rs` and exposes the full public surface in `__all__`.
There are no private leaks (no `_RsX` aliases like the model wrapper
needs), no double-imports, and the docstring correctly notes that
exception class metadata is patched up Rust-side (no Python-side
fix-up required).

The `__all__` list contains 24 names and matches both the spec headings
and the live `dir(openjd.expr)` output.

## 4. Test Review

| Subarea | File | Purpose |
|---------|------|---------|
| Arithmetic | `test_arithmetic.py` (17 KB) | Operators, mixed-type arithmetic, overflow, division-by-zero. |
| Comparison | `test_comparison.py` (8 KB) | `==`, `!=`, `<`, `>`, `in` across all value types. |
| Copy used symtab | `test_copy_used_symtab.py` (3 KB) | Binding-only feature: `FormatString.copy_used_symtab_values`. |
| Error formatting | `test_error_formatting.py` (26 KB) | Caret-pointer formatting, line/column reporting, `ExpressionError` decoration. |
| Expression value | `test_expression_value.py` (11 KB) | `ExprValue` construction from each Python type, coercion. |
| Function context | `test_function_context.py` (9 KB) | `apply_path_mapping`, host-context wiring. |
| Fuzz | `test_fuzz.py` (1 KB) | Parser doesn't crash on random byte sequences. |
| Int64 bounds | `test_int64_bounds.py` (6 KB) | i64 boundary handling and overflow → `ExpressionError`. |
| Known gaps | `test_known_gaps.py` (799 B) | xfail landing pad. **Currently empty.** |
| Lists | `test_lists.py` (32 KB) | List construction, comprehension, indexing, slicing. |
| Memory | `test_memory.py` (7 KB) | Memory-limit enforcement. |
| Method coercion | `test_method_coercion.py` (4 KB) | `.upper()`, `.lower()`, etc. on coerced types. |
| Operation limit | `test_operation_limit.py` (13 KB) | Operation counter and `operation_limit` enforcement. |
| Parse expression | `test_parse_expression.py` (9 KB) | `parse_expression` API surface. |
| Parsing | `test_parsing.py` (24 KB) | Tokenizer / parser correctness. |
| Path format mismatch | `test_path_format_mismatch.py` (4 KB) | Cross-format path operations. |
| Path mapping | `test_path_mapping.py` (18 KB) | `PathMappingRule.apply`, profile-driven evaluation. |
| Paths | `test_paths.py` (22 KB) | `path` type construction and methods. |
| Pickle | `test_pickle.py` (7 KB) | Binding-only pickle round-trip suite for all listed types. |
| Range expr | `test_range_expr.py` (10 KB) | `RangeExpr` parsing, indexing, hashing. |
| RFC examples | `test_rfc_examples.py` (6 KB) | Examples from the EXPR extension spec. |
| Slicing | `test_slicing.py` (4 KB) | List slicing semantics. |
| String operation counting | `test_string_operation_counting.py` (12 KB) | Operation-count parity for string operations. |
| Strings | `test_strings.py` (55 KB) | String operations, formatting. |
| Symbol table | `test_symbol_table.py` (8 KB) | Dotted-path get/set, `union`, repr. |
| Target type propagation | `test_target_type_propagation.py` (7 KB) | `target_type` flows through `evaluate` correctly. |
| Types | `test_types.py` (29 KB) | `ExprType` parsing, equality, dispatch. |
| Types evaluate | `test_types_evaluate.py` (6 KB) | Type system during evaluation. |
| Unresolved eval | `test_unresolved_eval.py` (33 KB) | Type-checking-time evaluation with unresolved values. |
| URI paths | `test_uri_paths.py` (9 KB) | URI-format path handling. |

Coverage of the binding-specific surface (Python types, exception
classes, pickle, profile types) is good. Reference-test parity is
strong — every reference test file has an analog here, and three
binding-only test files (`test_copy_used_symtab.py`, `test_known_gaps.py`,
`test_pickle.py`) cover features that don't exist in the reference.

**Test debt:**

- `test/openjd/expr/test_rfc_examples.py` lines 64-75 contain a
  `pytest.skip(...)` block that imports `ast_parse_keyword_context`
  and `Evaluator` from `openjd.expr` — symbols that exist in the
  reference but were intentionally not exposed by the bindings. The
  skip guard prevents test failure, but ruff flags two `F821 Undefined
  name` errors. The skipped block could be deleted (it's testing an
  internal API that no longer exists) or rewritten to use
  `evaluate_expression(target_type=...)` to exercise the same
  behaviour through the public surface.

- Several test files import symbols they no longer use (16 ruff
  errors total under `test/openjd/expr/` — see §6).

## 5. Parity with Pure-Python Reference

The reference (`fork/expr` branch) exposes the following symbols from
`openjd.expr`:

```python
ExprType, TypeCode, ExprValue, RangeExpr, RangeExprError,
SymbolTable, FunctionLibrary, FunctionSignature, get_default_library,
evaluate_expression, parse_expression, ParsedExpression,
ExpressionError, ExpressionTypeError, PathMappingRule, PathFormat,
DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT
```

It does NOT export `evaluate_let_bindings`, `escape_format_string`,
`FormatString`, `FormatStringValidationError`, or any of the profile
types — those are model-side or new in the bindings. Below is the
symbol-by-symbol parity table.

| Symbol | Reference | Binding | Status |
|--------|-----------|---------|--------|
| `evaluate_expression(expr, *, values, library, target_type, memory_limit, operation_limit, path_format)` | function | function (extra `profile=` kwarg) | ✓ binding adds `profile=` |
| `parse_expression(expr) -> ParsedExpression` | function | function | ✓ |
| `evaluate_let_bindings` | not exported | function (extra) | ⚠ extra in binding; takes `library=` only |
| `get_default_library() -> FunctionLibrary` | function | function | ✓ |
| `escape_format_string(value) -> str` | not exported | function (extra) | ⚠ extra in binding; reference exposes via model package |
| `ExprType(spec_str_or_typecode, params=None)` | class | class | ✓ |
| `ExprType.match(concrete)` → `match_type(concrete)` | method | renamed | ⚠ documented divergence (Rust reserves `match`) |
| `TypeCode` enum | enum | enum | ✓ |
| `ExprValue(value, *, type=None, path_format=None)` | class | class | ✓ |
| `ExprValue.from_float(value, original_str)` | static | static | ✓ |
| `ExprValue.unresolved(type)` | static | static | ✓ |
| `SymbolTable(source=None)` | class | class (also accepts positional `init`) | ✓ |
| `SymbolTable.union(*others)` | method | method | ✓ |
| `SymbolTable.keys` / `symbols` | properties | properties | ✓ |
| `FunctionLibrary` | class | class | ✓ |
| `FunctionLibrary.for_profile(profile)` | not in reference | classmethod (new) | ⚠ extra in binding |
| `FunctionSignature` | class | not exported | ⚠ binding omits — `FunctionSignature` is reference-internal type machinery; spec does not advertise it |
| `ParsedExpression` | class | class | ✓ |
| `ParsedExpression.evaluate(*, values, library, target_type, …)` | method | method (adds `profile=`) | ✓ |
| `PathFormat` | str enum | int enum (PyO3 `eq_int`) | ⚠ binding stores values as int; spec documents the difference indirectly |
| `PathMappingRule(*, source_path_format, source_path, destination_path)` | frozen dataclass (gets `__eq__`/`__hash__` free) | pyclass with composed `__eq__`/`__hash__` (Rec #1) | ✓ |
| `PathMappingRule.apply(*, path, output_format=None) -> (bool, str)` | method | method | ✓ |
| `PathMappingRule.to_dict / from_dict` | methods | methods | ✓ |
| `RangeExpr(str)` | class | class | ✓ |
| `RangeExpr.from_str / from_list` | static / static | static / static | ✓ |
| `RangeExpr.__eq__ / __hash__` | yes / yes | yes / yes | ✓ |
| `RangeExprError` | exception | exception | ✓ |
| `ExpressionError(message, *, expr, node, lineno, col_offset)` | class | class | ✓ |
| `ExpressionError.with_context(expr, node=None)` | method | method | ✓ |
| `ExpressionError.message_with_expr_prefix(prefix)` | method | method | ✓ |
| `ExpressionTypeError` | subclass of `ExpressionError` | subclass | ✓ |
| `DEFAULT_MEMORY_LIMIT / DEFAULT_OPERATION_LIMIT` | constants | constants | ✓ |
| `FormatString` | reference: in `openjd.model._format_strings`, str-subclass with `__eq__`/`__hash__` | binding: in `openjd.expr`, composed `__eq__`/`__hash__` on `raw()` (Rec #2) | ✓ (location moved into `openjd.expr`) |
| `FormatStringValidationError` | reference: `FormatStringError` in model | binding: registered, never raised from public API | ⚠ exception is unreachable (see §7) |
| `FormatString.copy_used_symtab_values(source, dest)` | not in reference | method (new) | ⚠ binding-only; not in spec |
| `ExprProfile`, `ExprRevision`, `ExprExtension`, `HostContext` | not in reference | classes (new) | ⚠ binding-only; the path-mapping API moved from per-call kwarg to profile-based |

### Summary of meaningful divergences

1. **No `__eq__` / `__hash__` on five pyclasses.** `FormatString`,
   `SymbolTable`, `PathMappingRule`, `HostContext`, and `ExprProfile`
   all fall back to Python's default object identity. The reference's
   `PathMappingRule` is a `@dataclass(frozen=True)` and `FormatString`
   is a `str` subclass, so both compare by value in v0. Pickle round-trips
   complete but `pickle.loads(pickle.dumps(x)) == x` is `False` for these
   types — `test_pickle.py` works around the gap by comparing
   `to_dict()` results or `is_enabled()` flags.
2. **`FormatStringValidationError` is registered but unreachable** from
   any public binding entry point (see §7).
3. **`evaluate_let_bindings` does not accept `profile=`** even though
   every other entry point that accepts a `library=` also accepts a
   `profile=`. The reference does not export this function at all,
   so this is not a regression — but it is an inconsistency in the
   bindings' own API.
4. **`FunctionSignature` is intentionally not exposed** by the binding
   (spec's design choice) — the reference's `FunctionSignature` was
   internal type machinery that no documented user code constructs.
5. **The path-mapping API has moved.** Reference: `PathMappingRule` is
   a per-call kwarg via `apply_path_mapping`. Binding: rules live in
   `HostContext` which is part of `ExprProfile`. The new shape is
   strictly more expressive (it can also represent the unresolved /
   template-validation state) and the spec documents the move.

## 6. Build and Test Results

```
$ hatch run test-subset test/openjd/expr
================= 1707 passed, 25 skipped, 8 warnings in 5.16s =================
```

```
$ cargo build --manifest-path rust-bindings/Cargo.toml --all-targets
warning: `openjd-python` (lib) generated 17 warnings (3 duplicates)
warning: `openjd-python` (lib test) generated 17 warnings (14 duplicates)
    Finished `dev` profile [unoptimized + debuginfo] target(s)
```

```
$ cargo clippy --manifest-path rust-bindings/Cargo.toml -- -D warnings 2>&1 | grep -B1 'src/expr/'
(no output — zero expr-side clippy warnings)
```

The 17 cargo warnings under the workspace are all in
`rust-bindings/src/sessions/types.rs` (`UPPER_CASE_ACRONYMS`,
`type_complexity`, `too_many_arguments`) — outside this report's
scope but noted for context.

```
$ cargo test --manifest-path rust-bindings/Cargo.toml --lib
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured
```

(There are no Rust-side unit tests in the bindings crate; that's
expected — the underlying behaviour is covered by `openjd-rs` Cargo
tests in the sibling repo, and the binding-specific behaviour is
covered by the pytest suite.)

```
$ hatch run lint
Found 0 errors.
```

The 18 errors that were live on **2026-05-22** when this report
was first drafted have all been resolved (see Recommendation #10).
For historical reference, **16 of those 18** lived under
`test/openjd/expr/`, contrary to the assumption that the lint
baseline was dominated by model/sessions:

| File | Errors |
|------|--------|
| `test/openjd/expr/test_path_mapping.py` | 5 |
| `test/openjd/expr/test_lists.py` | 3 |
| `test/openjd/expr/test_rfc_examples.py` | 2 |
| `test/openjd/expr/test_path_format_mismatch.py` | 2 |
| `test/openjd/expr/test_parse_expression.py` | 2 |
| `test/openjd/expr/test_slicing.py` | 1 |
| `test/openjd/expr/test_memory.py` | 1 |
| `test/openjd/model_v1/test_rust_model_bindings.py` | 2 |

Breakdown by ruff rule:

- 11 × `F401` unused imports
- 5 × `F811` redefinition of unused (mostly duplicate imports of
  `ExpressionError` or pathlib types on the same line)
- 2 × `F821` undefined name (in the pytest-skipped block in
  `test_rfc_examples.py`)
- 1 × `E702` multiple statements on one line (semicolon, in
  `test_memory.py:110`)

15 of these are autofixable with `ruff --fix`; the two `F821` and the
`E702` need manual attention.

Stub generation drift: not run as part of this evaluation; .pyi
spot-checks against `FormatString`, `ExprProfile`, and
`evaluate_let_bindings` showed no drift.

## 7. Exploratory Findings

### Equality and pickle round-trip gap on five types

(Resolved — see Recommendations 1-5.) The pickle round-trip suite
originally exercised every type listed in the spec's "Pickle
Support" table but only verified that the round-tripped object was
well-formed, not that it compared equal to the original. The five
gaps are now closed:

* `PathMappingRule` — composed `__eq__`/`__hash__` on the three
  fields.
* `FormatString` — composed on `raw()`.
* `HostContext` — composed on the variant tag plus (for
  `with_rules`) the rule list, walked by value so distinct `Arc`
  allocations of the same rule list compare equal.
* `ExprProfile` — composed on revision, extension set
  (canonicalised), and host context.
* `SymbolTable` — composed via recursive walk of the underlying
  `openjd_expr::SymbolTable` tree. Intentionally not hashable.

Tests live in `test/openjd/expr/test_equality.py` (43 tests).
The pickle round-trip suite has been tightened to assert
`loaded == original` end-to-end.

### `FormatStringValidationError` is unreachable

```
$ rg 'PyFormatStringValidationError' rust-bindings/src
rust-bindings/src/expr/errors.rs       (declaration)
rust-bindings/src/expr/mod.rs          (re-export)
rust-bindings/src/lib.rs               (register_renamed_exception)
```

No `PyFormatStringValidationError::new_err(...)` call exists anywhere
in the binding. The underlying Rust `FormatStringValidationError` is
produced by `openjd_expr::format_string::FormatString::validate_expressions`
— a method that is **not** exposed in the binding. `FormatString::new`,
which is exposed, returns `ExpressionError` on parse failure, so any
malformed input raises `ExpressionError`, not
`FormatStringValidationError`:

```
>>> e.FormatString('{{ unclosed')
Traceback ...
openjd.expr.ExpressionError: Failed to parse interpolation expression
at [0, 11]. Reason: Braces mismatch.
```

The exception class is therefore registered, pickleable, and
documented, but a user has no way to actually catch it from the
public expr API.

### Lint debt under `test/openjd/expr/`

(Historical, fully resolved — see Recommendation #10.) `hatch run
lint` originally reported 16 errors under expr test files, falling
into three categories:

1. **Autofixable unused / duplicate imports** (13 errors): cleared
   by `ruff check --fix test/openjd/expr` in commit `3728c78`.
2. **`E702` semicolon-joined statement** in `test_memory.py:110`:
   manually rewritten in commit `3728c78` (hoisted the local
   `TypeCode` import to the top of the file).
3. **`F821` references to reference-only Python helpers**
   (`ast_parse_keyword_context`, `Evaluator`) inside a
   `pytest.skip(...)` block in `test_rfc_examples.py:64-75`:
   replaced in commit `d3bc98a` with two new tests that exercise
   the same RFC-0005 args use-case through the public
   `evaluate_expression(target_type=...)` surface.

### Spec gaps: `copy_used_symtab_values` and the `FormatStringValidationError` raise site

The binding exposes `FormatString.copy_used_symtab_values(source, dest)`
on the public class, exercised by `test_copy_used_symtab.py`, but the
spec does not document it. Adding a short paragraph to the
`FormatString` section would close the gap.

Separately, the spec's exception table lists
`FormatStringValidationError` without saying which entry point raises
it. Either the spec needs to mark the type as "reserved for future
use", or the binding should expose `FormatString.validate_expressions`
(or another path that raises it) so the exception is reachable.

### Probes that came up clean

- **Boundary integers:** `i64::MAX` accepted, `i64::MAX + 1` raises
  `ExpressionError("Integer overflow: …")`. Matches reference.
- **Float edges:** NaN and Inf rejected on `ExprValue` construction
  with `ValueError`. Matches reference's `ExpressionTypeError` /
  `ValueError` rejection model.
- **`Decimal` round-trip:** `Decimal("3.140")` preserved in float
  string ("3.140" not "3.14") via `Float64::with_str`. Matches spec.
- **Cross-type equality:** `ExprValue(1) == ExprValue(1.0)` → `True`
  (matches reference `_value.py:__eq__`); both unhashable in both
  implementations.
- **`RangeExpr` hash equality:** Two equal `RangeExpr` instances
  hash equal. Suitable as `set` / `dict` keys. Matches reference.
- **Pickle exception class names:** `pickle.loads(pickle.dumps(
  e.ExpressionError("x")))` deserialises under the canonical
  `openjd.expr.ExpressionError` name (not the `Py`-prefixed internal
  name).
- **`HostContext.with_rules([])`:** distinct from `HostContext.none()`
  — `is_enabled()` returns `True` for the former and `False` for the
  latter, matching `openjd_expr::HostContext`.

## 8. Recommendations

Priority groupings: P0 = correctness or user-visible defect; P1 =
parity gap with the reference; P2 = housekeeping / spec hygiene.

### P0 — none

No correctness defects found in the current bindings.

### P1 — parity gaps

All five P1 items have been resolved binding-side without any
upstream change to the `openjd-rs` crates. The bindings compose
each `__eq__`/`__hash__` from the visible field values rather
than forwarding to `inner == inner` (which would require
`PartialEq + Eq + Hash` on the underlying Rust types — additions
that were prepared on a separate `expr-eq-hash` branch but
deliberately not landed here, to keep this work
independent of upstream review). Tests live in
`test/openjd/expr/test_equality.py` (43 tests).

1. ~~**Implement `__eq__` and `__hash__` on `PathMappingRule`.** The
   reference's `@dataclass(frozen=True)` provides both for free.
   Suggested location: `rust-bindings/src/expr/path_mapping.rs`,
   adding `#[pyclass(... eq, hash, frozen)]` and a `Hash` impl on
   `PyPathMappingRule` (the underlying `PathMappingRule` already
   derives `PartialEq, Eq, Hash`). Replace the `to_dict()`-based
   assertion in `test_pickle.py::test_path_mapping_rule_round_trip`
   with a direct `loaded == rule` once the change lands.~~
   **Resolved.** `PyPathMappingRule` now has `__eq__` and
   `__hash__` methods that compose on `source_path_format`,
   `source_path`, and `destination_path`. `PathFormat` is hashed
   by debug repr (it's a stable enum). The report claim that the
   underlying `PathMappingRule` already derives `PartialEq, Eq,
   Hash` was not actually true — composing on the visible fields
   side-steps the need to land that derive upstream.

2. ~~**Implement `__eq__` and `__hash__` on `FormatString`.** Compare
   on `raw()`. The reference's `FormatString` (as a `str` subclass)
   compares via `str.__eq__`. Suggested location:
   `rust-bindings/src/expr/format_string.rs`, adding `__eq__(self,
   other) -> bool { self.inner.raw() == other.inner.raw() }` and a
   matching `__hash__`.~~ **Resolved.** `PyFormatString.__eq__`
   and `__hash__` compose on `inner.raw()`. Lexically distinct
   inputs that would resolve to the same value (e.g.
   `"{{ Param.X }}"` vs `"{{Param.X}}"`) compare unequal — this
   preserves source identity rather than canonicalising
   whitespace.

3. ~~**Implement `__eq__` on `HostContext`.**
   `HostContext.none() == HostContext.none()` should be `True`;
   `HostContext.with_rules(rules) == HostContext.with_rules(rules)`
   should compare the rules. The underlying `openjd_expr::HostContext`
   derives `PartialEq, Eq` so the implementation is a one-liner:
   `rust-bindings/src/expr/profile.rs`, `__eq__(self, other) -> bool
   { self.inner == other.inner }`.~~ **Resolved.**
   `PyHostContext.__eq__` and `__hash__` compose on the variant
   tag plus (for `with_rules`) the rule list, walked by value —
   distinct `Arc` allocations of the same rule list compare
   equal. Helper functions `host_context_eq` / `host_context_hash`
   in `profile.rs` are also reused by `ExprProfile.__eq__`. The
   report claim about an upstream `PartialEq, Eq` derive on
   `openjd_expr::HostContext` was likewise not true; composing
   from the visible variant data avoids it.

4. ~~**Implement `__eq__` on `ExprProfile`.** Compare on the underlying
   `inner == inner`. Same file as recommendation 3.~~
   **Resolved.** `PyExprProfile.__eq__` composes on revision,
   extension set (canonicalised order), and host context (via
   `host_context_eq`). `__hash__` canonicalises the extension
   set as a sorted-by-debug-repr tuple so profiles with the same
   set hash equal regardless of `HashSet` insertion order.

5. ~~**Implement `__eq__` on `SymbolTable`.** Compare on the entries
   exposed via `all_paths`. The reference doesn't have explicit
   `__eq__` either, but documenting the intent (and matching the
   pickle round-trip expectation in `test_pickle.py`) is valuable.
   Suggested location: `rust-bindings/src/expr/symbol_table.rs`.~~
   **Resolved.** `PySymbolTable.__eq__` walks the underlying
   `openjd_expr::SymbolTable` recursively via the
   `symbol_table_eq` helper, comparing keys at every level and
   `ExprValue`s at the leaves. Insertion order in the underlying
   `HashMap` does not affect equality. `SymbolTable` is
   intentionally **not** hashable: `__setitem__` is supported, so
   the type is mutable and Python's hash/eq contract requires
   hashable types to be effectively immutable.

### P2 — housekeeping

6. **Make `FormatStringValidationError` reachable, or mark it reserved.**
   Either expose `FormatString.validate_expressions(symtab, library)`
   on the binding (mirroring the Rust crate's method) and document
   the raise site in the spec, or remove `FormatStringValidationError`
   from the spec and from `openjd.expr.__all__`. Suggested location:
   spec edit + (optional) `rust-bindings/src/expr/format_string.rs`
   adding the missing method.

7. **Document `FormatString.copy_used_symtab_values` in the spec.**
   The method is public, exercised by `test_copy_used_symtab.py`, and
   referenced by the model bindings — the spec is the only place it
   isn't mentioned. Suggested location:
   `specs/python-expr-interface.md`, in the `FormatString` section.

8. **Decide whether `evaluate_let_bindings` should accept `profile=`.**
   Every other entry point that takes `library=` also takes
   `profile=`. Adding it would be a non-breaking change and would
   close the only signature-shape inconsistency in the expr API.
   Suggested location:
   `rust-bindings/src/model/create_job_fns.rs::py_evaluate_let_bindings`
   (the function lives on the model side but is exposed in
   `openjd.expr`). Update the spec example accordingly.

9. **Clarify the default `host_context` in the "Inspecting a profile"
   spec example.** The example just before the `Inspecting a profile`
   block sets `with_host_context(HostContext.unresolved())` — and the
   reader has to keep that line in mind to interpret
   `profile.host_context  # HostContext.unresolved()` correctly. A
   one-line clarifying comment ("after the `with_host_context` call
   above") in `specs/python-expr-interface.md` would prevent
   misreadings about the default state of `ExprProfile()`.

10. ~~**Resolve lint debt under `test/openjd/expr/`.** Run
    `ruff --fix test/openjd/expr` to auto-resolve the 13 unused- or
    duplicate-import errors. Manually fix the `E702` semicolon-joined
    statement at `test_memory.py:110`. Remove or rewrite the
    `pytest.skip(...)` block at `test_rfc_examples.py:64-75` so that
    `ast_parse_keyword_context` and `Evaluator` no longer appear as
    `F821` undefined names. After all three groups, the expr test
    suite should contribute zero errors to `hatch run lint`.~~
    **Resolved.** Three commits cleared all 16 expr-test lint
    errors:

    - `d3bc98a` rewrote the skipped `test_quality_list_with_value`
      block in `test_rfc_examples.py` against the public
      `evaluate_expression(target_type=...)` API (using the built-in
      `string()` function to satisfy RFC 0005's unconstrained-operand
      rule), eliminating the two `F821`s and an unused `pytest`
      import. A companion `test_quality_list_branch_null` test was
      added for the conditional's `else` branch.
    - `3728c78` ran `ruff check --fix test/openjd/expr` to clear
      eleven `F401`/`F811` unused- or duplicate-import errors across
      `test_lists.py`, `test_parse_expression.py`,
      `test_path_format_mismatch.py`, `test_path_mapping.py`,
      `test_slicing.py`, plus a manual rewrite of the `E702`
      semicolon-joined statement in `test_memory.py:110` (hoisted the
      local `from openjd.expr import TypeCode` to the top of the
      file).
    - This commit also cleared the two stragglers in
      `test/openjd/model_v1/test_rust_model_bindings.py` (an unused
      `UnsupportedSchema` import and a dead local
      `StepParameterSpaceIterator` import inside a fixture body),
      bringing `hatch run lint` to **0 errors workspace-wide**.

11. **Drop the unreachable arm in `From<PyTypeCode> for TypeCode`.**
    `expr_type.rs::From<TypeCode>` correctly panics on a future
    upstream variant via `unreachable!`. The reverse direction
    (`From<PyTypeCode> for TypeCode`) is exhaustive on Python-side
    variants, so the `_ =>` arm in `From<ExprRevision>` and similar
    spots is `#[allow(unreachable_patterns)]`-guarded. As more
    revisions land in the Rust crate, audit those spots and add
    explicit arms. (No action needed today; tracking item only.)
