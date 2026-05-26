# openjd-expr Bindings Quality Evaluation Report

**Date:** 2026-05-26
**Component:** `openjd.expr`
**Reference branch:** `mwiebe/openjd-model-for-python` `expr` (local: `fork/expr`)
**Working branch:** `bindings-rs` @ `ee7d1b0`

## Executive Summary

The `openjd.expr` binding is in solid shape. Every public symbol the
spec advertises is reachable through `openjd.expr`, every binding-side
symbol (including the recently added `EvalResult`) is documented in
the spec, and the four artifacts (spec, PyO3 source, wrapper, tests)
are aligned. The build, the full Python test suite, `cargo test`,
`cargo clippy --all-targets -- -D warnings`, `hatch run lint`, and the
stub generator all run clean; `test_known_gaps.py` is empty (zero
xfail tests).

The previous evaluation closed all 13 numbered recommendations across
recent commits, and a fresh reading confirms those resolutions are
genuine — the `FunctionLibrary` → `ExprProfile` consolidation, the
`evaluate_with_metrics` / `EvalResult` split, the `from_float` Decimal
auto-capture, the `PathMappingRule` URI validation, the unresolved
`ExprValue` `repr` / `item` / `str` contract, the `TypeCode`-not-
IntEnum note, and the `ExprValue(None)` canonical-null guidance are
all in place and exercised by tests.

A small set of new findings remain, all in the
documentation-quality / minor-divergence band — none block adoption.
The most consequential is that `PathFormat` lost its `str, Enum`
mixin behaviour without a spec note (companion to the existing
`TypeCode`-not-IntEnum note). Nothing in this report is a P1, and
nothing is a regression of a previously-resolved item.

## 1. Python Interface Spec Review

`specs/python-expr-interface.md` is comprehensive and accurate.
Every symbol in `src/openjd/expr/__init__.py`'s `__all__` is
documented in detail with code examples, and the spec also covers:

* The `FunctionLibrary` → `ExprProfile` migration (§ "Migration
  from the pure-Python reference") with the explicit removed-API
  table.
* The intentional divergences from the v0 reference:
  `ExprValue(None)` as the canonical null, `match_type` instead of
  `match`, `from_float` Decimal auto-capture, `PathMappingRule.source_path`
  always `str`, `TypeCode` not an `IntEnum` subclass, `ParsedExpression.peak_memory_usage`
  and `operation_count` removal (replaced by `EvalResult`).
* Equality / hashability semantics for every value type that
  participates in dict keys or sets (`PathMappingRule`,
  `RangeExpr`, `IntRange`, `FormatString`, `HostContext`,
  `ExprProfile`, `ExprValue` is documented as deliberately
  *un*hashable).
* Pickle round-trip semantics for every pickleable type, in a
  dedicated table.

**Spec gaps**:

1. `RangeExpr.from_str` is exposed but not documented in the spec.
   It mirrors the reference's `from_str` classmethod and behaves
   identically to the constructor when given a string.
2. `HostContext.is_enabled()` and `HostContext.is_unresolved()` are
   exposed but not mentioned in the `HostContext` section of the
   spec.
3. The `TypeCode` "not an `IntEnum`" note covers the
   `isinstance(..., int)` mismatch but doesn't mention that
   standard `Enum` protocol operations (`list(TypeCode)`,
   `TypeCode["INT"]`, `TypeCode(2)` value-lookup, iteration) are
   **not** supported on the binding (the v0 reference supports
   them via `IntEnum`). Code that ports `for tc in TypeCode: ...`
   will break.
4. `PathFormat` has no spec note about the loss of `str, Enum`
   mixin behaviour. `PathFormat.POSIX == "POSIX"` is `True` in
   v0, `False` in the binding; `isinstance(PathFormat.POSIX, str)`
   is `True` in v0, `False` in the binding. This is the exact
   parallel of the documented `TypeCode` divergence and merits the
   same kind of note.
5. `ExprRevision.CURRENT` is implicitly mentioned ("Tracks
   `ExprRevision::CURRENT` in the underlying Rust crate") but not
   surfaced as a callable example like `TypeCode.INT`.

## 2. PyO3 Binding Source Review

The 13 files under `rust-bindings/src/expr/` are clean,
idiomatic, and follow the conventions documented in
`AGENTS.md` § "PyO3 Conventions".

* **Exception registration**: every `create_exception!`-built
  exception (`PyExpressionError`, `PyExpressionTypeError`,
  `PyRangeExprError`, `PyFormatStringValidationError`) is
  registered with `register_renamed_exception` in
  `rust-bindings/src/lib.rs`. Tracebacks, pickle, and IDE
  tooltips show `openjd.expr.ExpressionError`, etc., not
  `_openjd_rs.PyExpressionError`.
* **Type conversions**: `IntoPyObject` / `FromPyObject` impls are
  consistent. The i64 boundary is handled explicitly:
  `PyInt → i64` overflow is rewritten to `ExpressionError`
  ("Integer overflow: value does not fit in i64 (...)") rather
  than the default `OverflowError`. Float NaN / Inf is rejected
  at the binding boundary via `Float64::new`'s validation.
  Decimal is detected via real `isinstance` against
  `decimal.Decimal` (not duck-typed by class-name string), and
  the lexical form is captured in both `ExprValue(Decimal(...))`
  and `ExprValue.from_float(Decimal(...))`.
* **GIL handling**: the expr binding has no blocking I/O — every
  operation is in-memory parsing/evaluation that finishes
  promptly. There is no `Python::allow_threads` call, which is
  appropriate for this surface.
* **Constructor signatures**: `#[pyo3(signature = ...)]` is
  present on every `#[new]` and the keyword-only / positional
  split matches what the spec describes (e.g.
  `evaluate_expression` is keyword-only after `expr`,
  `PathMappingRule` is fully keyword-only).
* **ABI3**: no Python C-API beyond ABI3-py39 is used.

`expr/errors.rs` deserves a specific call-out for elegance:
`ExpressionError`'s keyword constructor and `with_context` /
`message_with_expr_prefix` decoration methods are compiled from
a single `&'static str` source at module init and installed
onto the type via `setattr`. That gives bound-method semantics
on instances, lets `ExpressionTypeError` inherit them through
normal Python class inheritance, and keeps the exception class
behaviour as a single source of truth in the Rust source. The
in-line comment explaining why `#[pyclass(extends = PyValueError)]`
isn't an option (abi3-py39 vs subclassing built-in exceptions
on 3.9–3.11) is the right level of detail to leave for the next
maintainer.

`expr/expr_type.rs` `validate_typecode_arity` is also
note-worthy — it constrains the binding-side `ExprType`
constructor to canonical arities (e.g. `LIST` requires exactly
one type parameter, `Unresolved` requires exactly one, simple
primitives accept zero) without requiring upstream changes to
`openjd-expr::ExprType::new`. The doc comment correctly carves
out `Union` (which the upstream `normalize_union` already
handles permissively).

The only non-blocking code-style concern is that
`expr_value.rs::expr_value_to_py` has a `_ => Ok(py.None())`
catch-all at the bottom that would silently turn any new
`ExprValue` variant introduced upstream into Python `None`.
Today no other variants exist, but the `expr_type.rs::From<TypeCode>`
match (which has been hardened to `unreachable!` on unknown
variants) is the better template — see Recommendation 1.

## 3. Python Wrapper Module Review

`src/openjd/expr/__init__.py` is a single-block re-export from
`openjd._openjd_rs` followed by an `__all__` declaration. Every
spec symbol is reachable through the documented import path,
no internal-only `_*` names leak, and the explanatory comment
above `__all__` correctly notes that the exception class
metadata fix-up (`__module__`, `__name__`, `__qualname__`) and
the `ExpressionError` keyword constructor / decoration methods
are installed Rust-side.

Verified: `set(openjd.expr.__all__) == set(<spec public
symbols>)` exactly — no drift in either direction.

## 4. Test Review

`test/openjd/expr/` contains 32 test files that mirror the
reference's test organization plus binding-specific additions:

| Reference file | Binding analog | Notes |
|---|---|---|
| `test_arithmetic.py` | ✓ | |
| `test_comparison.py` | ✓ | |
| `test_error_formatting.py` | ✓ | |
| `test_expression_value.py` | ✓ | |
| `test_function_context.py` | ✓ | |
| `test_fuzz.py` | ✓ | |
| `test_int64_bounds.py` | ✓ | |
| `test_lists.py` | ✓ | |
| `test_memory.py` | ✓ | |
| `test_method_coercion.py` | ✓ | |
| `test_operation_limit.py` | ✓ | |
| `test_parse_expression.py` | ✓ | |
| `test_parsing.py` | ✓ | |
| `test_path_format_mismatch.py` | ✓ | |
| `test_path_mapping.py` | ✓ | |
| `test_paths.py` | ✓ | |
| `test_range_expr.py` | ✓ | |
| `test_rfc_examples.py` | ✓ | |
| `test_slicing.py` | ✓ | |
| `test_string_operation_counting.py` | ✓ | |
| `test_strings.py` | ✓ | |
| `test_symbol_table.py` | ✓ | |
| `test_target_type_propagation.py` | ✓ | |
| `test_types.py` | ✓ | |
| `test_types_evaluate.py` | ✓ | |
| `test_unresolved_eval.py` | ✓ | |
| `test_uri_paths.py` | ✓ | |

Binding-only test files (covering surface that doesn't exist in
the reference, or behaviour that warrants its own organisation):

| File | Surface |
|---|---|
| `test_copy_used_symtab.py` | `FormatString.copy_used_symtab_values` |
| `test_equality.py` | `__eq__` / `__hash__` for every value type |
| `test_eval_result.py` | `EvalResult` and `evaluate_with_metrics` |
| `test_format_string_validate.py` | `FormatString.validate_expressions` |
| `test_known_gaps.py` | currently empty (zero xfail tests) |
| `test_pickle.py` | round-trip pickle for every spec'd pickleable type |

All 1855 expr tests pass (24 skipped, zero xfail, zero failures).
Coverage on the expr surface is high; the project-wide 94 %
coverage gate is enforced only by the full-suite `hatch run
test`, not by the expr-only subset.

## 5. Parity with Pure-Python Reference

The v0 reference (`fork/expr`) is the primary parity baseline.
Every public symbol it exposed has a binding counterpart, and
the documented divergences (`FunctionLibrary` → `ExprProfile`,
`ExprValue.null()` → `ExprValue(None)`, `match` → `match_type`,
etc.) are all spec'd and tested.

| Symbol | Reference (`fork/expr`) | Binding (`bindings-rs`) | Status |
|---|---|---|---|
| `evaluate_expression(expr, *, values, library, target_type, …)` | yes | yes — `library=` replaced by `profile=`, documented | ✓ |
| `parse_expression(expr)` | yes | yes | ✓ |
| `escape_format_string(s)` | implicitly via `_format_strings` | yes — top-level | ✓ |
| `ExprType("...")` / `ExprType(TypeCode, [params])` | yes | yes | ✓ |
| `ExprType.list(t)` / `ExprType.union([t…])` | yes | yes | ✓ |
| `ExprType.match(other)` | yes | renamed to `match_type` (documented) | ✓ |
| `ExprType.substitute(bindings)` | yes | yes | ✓ |
| `ExprType.is_concrete` / `is_symbolic` / `is_nullable` / `nullable` | yes | yes | ✓ |
| `TypeCode.<MEMBER>` constants | yes | yes | ✓ |
| `TypeCode(IntEnum)` mixin (`isinstance(t, int)`, `list(TypeCode)`, `TypeCode["INT"]`, `TypeCode(2)`) | yes (IntEnum) | partially (only `==` and `int(t)` work; iteration / class lookup do not) | ⚠ — documented for `isinstance(int)`; iteration / lookup not yet documented |
| `ExprValue(...)` constructor | yes | yes | ✓ |
| `ExprValue.null()` | yes | dropped — use `ExprValue(None)` (documented) | ✓ |
| `ExprValue.unresolved(t)` | yes | yes | ✓ |
| `ExprValue.from_float(v, original_str=None)` | yes | yes (with auto-Decimal capture, documented) | ✓ |
| `ExprValue.item()` / `str()` / `bool()` / iteration | yes | yes | ✓ |
| `ExprValue.memory_size()` | no (binding-only) | yes — documented | ✓ |
| `ExprValue` unhashable | yes | yes — documented | ✓ |
| `SymbolTable(source=)` | yes | yes (also accepts positional `init=`) | ✓ |
| `SymbolTable.union(*others)` | yes | yes | ✓ |
| `SymbolTable.keys` / `.symbols` | yes | yes | ✓ |
| `SymbolTable.__eq__` (recursive) | yes | yes | ✓ |
| `SymbolTable` unhashable | yes | yes | ✓ |
| `FunctionLibrary` / `FunctionSignature` / `get_default_library` | yes | dropped — replaced by `ExprProfile` (documented) | ✓ |
| `ExprProfile` / `ExprRevision` / `ExprExtension` / `HostContext` | partial (host-context only) | full builder API — documented | ✓ |
| `ParsedExpression.evaluate(...)` returns `ExprValue` | yes | yes | ✓ |
| `ParsedExpression.evaluate_with_metrics(...)` returns `EvalResult` | no (had `peak_memory_usage` / `operation_count` attrs) | yes — documented as replacement | ✓ |
| `ParsedExpression.peak_memory_usage` / `operation_count` attrs | yes | dropped — documented | ✓ |
| `EvalResult(value, peak_memory, operation_count)` | n/a | yes — frozen, unhashable, pickleable, deferred eq | ✓ |
| `PathFormat.POSIX/WINDOWS/URI` | yes (`str, Enum`) | yes (plain pyo3 enum) | ⚠ — `str, Enum` mixin lost without a spec note |
| `PathMappingRule(source_path_format=, source_path=, destination_path=)` | yes — `source_path` is `PurePath` for POSIX/WINDOWS | yes — `source_path` always `str` (documented) | ✓ |
| `PathMappingRule.apply(path=, output_format=None)` | yes | yes | ✓ |
| `PathMappingRule.to_dict()` / `from_dict(d)` | yes | yes — incl. URI-source validation | ✓ |
| `PathMappingRule` `__eq__` / `__hash__` | yes (frozen dataclass) | yes — value equality on three fields | ✓ |
| `RangeExpr("...")`, `from_str`, `from_list` | yes | yes (`from_str` undocumented) | ⚠ minor |
| `RangeExpr.start` / `.end` / `__len__` / `__iter__` / `__contains__` / `__getitem__` | yes | yes | ✓ |
| `RangeExpr.ranges()` returning `list[IntRange]` | yes (`list[_IntRange]`) | yes (binding-side `IntRange` instead of internal `_IntRange`) | ✓ |
| `RangeExpr` `__eq__` / `__hash__` | yes | yes | ✓ |
| `IntRange(start, end, step=1)` | yes (internal `_IntRange`) | yes (`openjd.expr.IntRange`) | ✓ |
| `IntRange.__eq__` / `__hash__` / pickle | reference's `_IntRange` is a private namedtuple | yes — full public type | ✓ |
| `RangeExprError`, `ExpressionError`, `ExpressionTypeError` | yes | yes — registered, full inheritance | ✓ |
| `FormatString` (whole class) | not in reference's `openjd.expr` (lived in `openjd.model._format_strings`) | yes — promoted to `openjd.expr` (documented) | ✓ |
| `FormatStringValidationError` | not exposed publicly in reference | yes | ✓ |
| `DEFAULT_MEMORY_LIMIT` / `DEFAULT_OPERATION_LIMIT` | yes | yes | ✓ |
| `ExpressionError(message, *, expr=, node=, lineno=, col_offset=)` keyword constructor | yes | yes — installed via `attach_expression_error_methods` | ✓ |
| `ExpressionError.with_context(expr, node=None)` | yes | yes | ✓ |
| `ExpressionError.message_with_expr_prefix(prefix)` | yes | yes | ✓ |

Behavioural / message-level parity:

* Undefined-variable error message format: matches
  (`Undefined variable: 'X'.\n  X\n  ~~~~~~^`).
* Operation-limit error message format: matches
  (`Expression operation count (N) exceeded limit (M)\n  expr\n  ^~~`).
* Format-string validation error embeds `[start, end]` byte
  offsets per the spec.
* `ExpressionError`'s `__module__` is `openjd.expr` end-to-end
  (verified by pickling and inspecting `type(loaded).__module__`).
* `ExprValue` int-vs-float equality (`ExprValue(1) ==
  ExprValue(1.0)`) holds, and `EvalResult.__eq__` defers to it
  (so `EvalResult(value=ExprValue(1), …) == EvalResult(value=ExprValue(1.0), …)` when other fields match).

## 6. Build and Test Results

```
$ python scripts/maturin_build.py develop --manifest-path rust-bindings/Cargo.toml
🍹 Building a mixed python/rust project
🐍 Found CPython 3.13 at .../openjd-model/bin/python
🔗 Found pyo3 bindings with abi3 support
   Compiling openjd-python v0.9.0
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.47s
🛠 Installed openjd-model-0.9.1.post55+gee7d1b011.d20260526

$ cargo build --manifest-path rust-bindings/Cargo.toml --all-targets
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.63s
(no warnings or errors)

$ cargo clippy --manifest-path rust-bindings/Cargo.toml --all-targets -- -D warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.98s
(clean — zero lints)

$ cargo test --manifest-path rust-bindings/Cargo.toml
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
   Doc-tests _openjd_rs
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

$ hatch run test-subset test/openjd/expr
1855 passed, 24 skipped in 5.33s

$ hatch run lint
ruff check src test          → All checks passed!
black --check --diff src test → All done! ✨ 🍰 ✨ 156 files would be left unchanged.
mypy src test                 → Success: no issues found in 105 source files

$ scripts/generate_stubs.sh                  # (with --features stub-gen)
Generated src/openjd/_openjd_rs.pyi
$ git diff src/openjd/_openjd_rs.pyi          → no changes
```

The Rust tree currently emits **one compiler warning** (unused
`PyType` import in `rust-bindings/src/model/task_parameter.rs`),
which is in the `model` component, not `expr`. Mentioning it here
because the warning surfaces during the stub-gen build that the
expr evaluation also runs. See Recommendation 2.

## 7. Exploratory Findings

* **Pickle round-trip** is verified for every spec'd pickleable
  type: `PathFormat`, `TypeCode`, `ExprRevision`, `ExprType`,
  `ExprValue` (including `unresolved`), `RangeExpr`, `IntRange`,
  `FormatString`, `SymbolTable`, `PathMappingRule`,
  `HostContext` (all three variants), `ExprProfile`,
  `EvalResult`. `ParsedExpression` correctly raises on pickle
  attempt (per spec).
* **Exception class round-trip** through pickle preserves
  `__module__` / `__name__` (`openjd.expr.ExpressionError`,
  etc.) thanks to `register_renamed_exception`.
* **i64 overflow**: integers outside `[i64::MIN, i64::MAX]`
  raise `ExpressionError` (not `OverflowError`), matching the
  reference contract. Verified for both top-level
  `evaluate_expression` ("Integer overflow: result is outside
  the 64-bit signed range") and `ExprValue(2**100)` ("Integer
  overflow: value does not fit in i64 (OverflowError: …)").
* **Float NaN / Inf** are rejected by `ExprValue(...)` at the
  binding boundary (`ValueError: Float operation produced NaN`
  / `... produced infinity`). Matches spec (the binding does
  not surface NaN/Inf to user code).
* **Equality semantics**: `ExprValue(1) == ExprValue(1.0)` is
  `True` (consistent across both directions); `ExprValue(1) ==
  ExprValue(True)` is `False`; `EvalResult.__eq__` defers to
  `ExprValue.equals` for the value field.
* **Concurrent evaluation**: 10 threads calling
  `parsed.evaluate_with_metrics(values={"N": 100})`
  concurrently produced 10 results with identical
  `operation_count` — i.e. metrics are local per call (no
  last-writer-wins shared state). This is the regression
  scenario that motivated the `EvalResult` redesign and it is
  closed.
* **Hashability matrix** matches the spec exactly:
  hashable: `ExprType`, `RangeExpr`, `IntRange`, `FormatString`,
  `PathMappingRule`, `HostContext`, `ExprProfile`, `TypeCode`,
  `PathFormat`, `ExprRevision`. Unhashable: `ExprValue`,
  `SymbolTable`, `EvalResult`.
* **Unicode** survives `ExprValue("héllo 🚀")` round-trip
  through `item()` / `str()`.
* **`ExprValue.unresolved(t).repr()`** is debug-friendly and
  never raises (`'ExprValue.unresolved(ExprType("int"))'`);
  `str()` and `item()` raise `ExpressionTypeError` per spec.
* **`escape_format_string` round-trip**: passing the result
  back through `FormatString(...).resolve_string(SymbolTable())`
  recovers the original input verbatim.
* **`PathFormat` mixin loss** (new finding): in v0,
  `PathFormat(str, Enum)` makes `PathFormat.POSIX == "POSIX"`
  return `True` and lets `isinstance(PathFormat.POSIX, str)`
  succeed. In the binding both are `False`. Code that branched
  on `if rule.source_path_format == "POSIX": ...` (treating
  the enum as a string) would silently fail to match. No
  binding test exercises this, and the spec has no migration
  note.
* **`TypeCode` enum-protocol loss** (new finding): the spec
  documents the `isinstance(..., int)` divergence but doesn't
  mention `list(TypeCode)`, `TypeCode["INT"]`, `TypeCode(2)`,
  and `for tc in TypeCode: ...` all *also* fail
  (`TypeError: 'type' object is not iterable` /
  `'openjd.expr.TypeCode' is not subscriptable` /
  `cannot create 'openjd.expr.TypeCode' instances`).
* **`expr_value.rs::expr_value_to_py` catch-all** (new
  finding): the function ends with `_ => Ok(py.None())`, so a
  hypothetical future `ExprValue` variant would be silently
  collapsed to Python `None`. The companion
  `expr_type.rs::From<TypeCode>` impl was hardened to
  `unreachable!` for exactly this reason; the same hardening
  hasn't been applied here.

No new failing tests were added. `test_known_gaps.py` is left
empty: the file's docstring already states there are no known
gaps, and the four findings above are documentation /
hardening matters that don't warrant xfails of broken
behaviour.

## 8. Recommendations

The previous report's Recommendations 1 – 13 are all closed —
verified by re-reading the spec, the binding source, and the
test suite, not just by trusting `**Resolved**` markers. The
following are *new* findings from this evaluation; all are
documentation / minor-hardening level (P2 / P3). No P1.

1. ~~**Replace the `_ => Ok(py.None())` catch-all in
   `rust-bindings/src/expr/expr_value.rs::expr_value_to_py`
   with an `unreachable!` arm**, mirroring the hardening
   already applied to `expr/expr_type.rs::From<TypeCode>`. As
   `openjd_expr::ExprValue` is `#[non_exhaustive]`, a new
   variant introduced upstream would today be silently
   converted to Python `None`. `unreachable!` surfaces the
   missing handler at the binding boundary instead of
   masking it. *(P2)*~~ **Resolved.** Replaced the catch-all
   with `v => unreachable!(...)` matching the existing
   `expr_type.rs::From<TypeCode>` pattern. The panic message
   names the file path (`rust-bindings/src/expr/expr_value.rs::
   expr_value_to_py`) so a future maintainer adding an
   `ExprValue` variant has a clear pointer to the right place.

2. ~~**Document the `PathFormat` `str, Enum` mixin loss in
   `specs/python-expr-interface.md`**, mirroring the existing
   `TypeCode`-not-IntEnum note. The new note should call out
   that `PathFormat.POSIX == "POSIX"` is `False` and
   `isinstance(PathFormat.POSIX, str)` is `False`, with a
   suggested rewrite for callers (`fmt == PathFormat.POSIX` /
   `fmt is PathFormat.POSIX`). Code-review for downstream
   consumers may also be worthwhile (`deadline-cloud`,
   `openjd-sessions-for-python` wrapper). *(P2)*~~ **Resolved
   (spec note added).** Added a "Not a `str` mixin Enum"
   callout to the `PathFormat` section paralleling the
   existing `TypeCode` callout. Covers (a) the comparison /
   isinstance divergence with the recommended migrations
   (`fmt is PathFormat.POSIX` / `fmt == PathFormat.POSIX` /
   `fmt.name`), and (b) the iteration / value-lookup losses
   (`list(PathFormat)`, `for fmt in PathFormat`,
   `PathFormat["POSIX"]` all raise `TypeError`). The
   downstream-consumer code review is out of scope for this
   commit; it's tracked separately by the consumer
   repositories.

3. ~~**Extend the `TypeCode` "not an `IntEnum`" note in the spec
   to also flag the enum-protocol surface that doesn't carry
   over** — `list(TypeCode)`, `TypeCode["INT"]`, `TypeCode(2)`,
   and `for tc in TypeCode: ...` all fail. Recommended phrasing
   parallels the existing isinstance note: "Iteration and
   value-lookup operations from `IntEnum` are not supported.
   Use direct attribute access (`TypeCode.INT`) and an explicit
   tuple of members where iteration is needed." *(P3)*~~
   **Resolved.** Added a second paragraph to the existing
   "Not an `IntEnum` subclass" callout in the `TypeCode`
   section. Lists each operation that raises `TypeError`
   (`list(TypeCode)`, `for tc in TypeCode`,
   `TypeCode["INT"]`, `TypeCode(2)`) and recommends direct
   attribute access plus an explicit member tuple where
   iteration is needed.

4. ~~**Document `RangeExpr.from_str` in
   `specs/python-expr-interface.md`** under the `RangeExpr`
   section. It mirrors the v0 reference's classmethod and is
   called by some test code; readers shouldn't have to read
   the source to discover it. *(P3)*~~ **Resolved.** Added an
   inline `RangeExpr.from_str(...)` example block to the
   `RangeExpr` section, between the existing constructor and
   `from_list` examples, with the explicit note that it is a
   `@staticmethod` equivalent to the constructor and mirrors
   the v0 reference's `from_str` classmethod. Extended the
   trailing error-summary paragraph to cover `RangeExprError`
   on malformed input from both the constructor and
   `from_str`.

5. ~~**Document `HostContext.is_enabled()` and
   `HostContext.is_unresolved()` in the `HostContext` section
   of the spec.** They're useful predicates (e.g. for
   conditional path-mapping setup) and are exposed but
   undocumented. *(P3)*~~ **Resolved.** Added a "Predicates on
   a `HostContext`" example block to the combined
   `ExprRevision` / `ExprExtension` / `HostContext` /
   `ExprProfile` section, right after the three-states list.
   Covers all four shapes (`none()`, `unresolved()`,
   `with_rules([])`, `with_rules([rule, ...])`) showing the
   `is_enabled` / `is_unresolved` mapping, with an explicit
   inline note that `with_rules([])` is enabled (passing
   zero rules is **not** the same as passing no host context
   at all).

6. ~~**Surface `ExprRevision.CURRENT` as an example in the
   `ExprRevision` section.** The spec currently says
   "[`ExprProfile.current()`] selects the current revision"
   but doesn't show the `ExprRevision.CURRENT` constant
   directly. *(P3)*~~ **Resolved.** Added an
   `ExprRevision.CURRENT` example block to the end of the
   profile section's example. Shows that the constant equals
   `ExprRevision.V2026_02` today, that `str(...)` returns
   `"2026-02"` and `.name` returns `"V2026_02"`, with the
   explicit note that it tracks the upstream
   `openjd_expr::ExprRevision::CURRENT` constant and rolls
   forward as new revisions ship.

Cross-reference for the report-driven workflow: when an item
is resolved, replace the line with `~~ ... ~~ **Resolved.**`
in the same commit per `AGENTS.md` § "Report-driven
development".
