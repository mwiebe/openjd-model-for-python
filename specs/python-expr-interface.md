# Python Expression Language Interface (`openjd.expr`)

Rust-backed implementation of the Open Job Description expression language
([EXPR extension](https://github.com/OpenJobDescription/openjd-specifications/wiki/2026-02-Expression-Language)).

## Functions

### `evaluate_expression`

Evaluate an expression string and return the result.

```python
from openjd.expr import evaluate_expression, SymbolTable, ExprType, PathFormat

# Simple arithmetic
evaluate_expression("1 + 2").item()  # 3

# With variables
st = SymbolTable({"Param.Frame": 42, "Param.Name": "render"})
evaluate_expression("Param.Frame * 2", values=st).item()  # 84
evaluate_expression("Param.Name.upper()", values=st).item()  # "RENDER"

# Conditional
evaluate_expression("'high' if Param.Frame > 100 else 'low'", values=st).item()  # "low"

# List comprehension
evaluate_expression("[x * 2 for x in range(5)]").item()  # [0, 2, 4, 6, 8]

# With target type coercion
evaluate_expression("[1, 2, 3]", target_type=ExprType("list[string]")).item()  # ["1", "2", "3"]

# With resource limits
evaluate_expression("sum(range(100))", operation_limit=50)  # raises ExpressionError

# With path format
evaluate_expression("path('/a/b').name", path_format=PathFormat.POSIX).item()  # "b"
```

### `parse_expression`

Parse an expression without evaluating it. Inspect symbol references and function calls.

```python
from openjd.expr import parse_expression

parsed = parse_expression("Param.Start + len(Param.Items)")
parsed.accessed_symbols   # {"Param.Start", "Param.Items"}
parsed.called_functions   # {"len"}
parsed.local_bindings     # set()

# Evaluate later with different values
result = parsed.evaluate(values={"Param.Start": 10, "Param.Items": [1, 2, 3]})
result.item()  # 13

# Check resource usage after evaluation
parsed.peak_memory_usage  # bytes used
parsed.operation_count    # operations performed
```

### `evaluate_let_bindings`

Evaluate let bindings against a symbol table. Used by sessions to resolve
step-level `let` bindings at runtime.

```python
from openjd.expr import evaluate_let_bindings, SymbolTable

st = SymbolTable({"Param.Start": 1, "Param.Count": 10})
result = evaluate_let_bindings(["end = Param.Start + Param.Count - 1"], st)
result["end"].item()  # 10
```

### `escape_format_string`

Escape `{{` and `}}` in a string for use as a literal in a format string.

```python
from openjd.expr import escape_format_string

escape_format_string("use {{braces}}")  # 'use {{ "{{" }}braces{{ "}" + "}" }}'
```

## Types

### `ExprType`

Represents a type in the expression language. The type system includes
primitives (`int`, `float`, `string`, `bool`, `path`), compound types
(`list[T]`, `range_expr`), unions (`int | string`), nullable (`int?`),
and type variables (`T`, `T1`, `T2`, `T3`) for generic function signatures.

`ExprType` instances are constructed from the spec-form string
(`ExprType("bool")`, `ExprType("list[int]")`, `ExprType("int | string")`)
or from a `(TypeCode, type_params)` tuple
(`ExprType(TypeCode.LIST, [ExprType("int")])`). The binding deliberately
**does not** expose class-level shortcut constants such as
`ExprType.BOOL` or `ExprType.LIST_INT`; the string form is the single
canonical way to refer to a type and round-trips through
`str(t)` / `ExprType(str(t))`.

```python
from openjd.expr import ExprType, TypeCode

# Construction from string
ExprType("int")                           # int
ExprType("list[int]")                     # list[int]
ExprType("int?")                          # int | nulltype (nullable)
ExprType("int | string")                  # union
ExprType("list[list[int]]")               # nested list

# Construction from TypeCode
ExprType(TypeCode.LIST, [ExprType("int")])  # list[int]

# Properties
t = ExprType("list[int]")
t.type_code                               # TypeCode.LIST
t.type_params                             # [ExprType("int")]
str(t)                                    # "list[int]"

# Methods
ExprType("int").nullable()                # ExprType("int | nulltype")
ExprType("int?").is_nullable()            # True
ExprType("int").is_concrete()             # True
ExprType("T").is_symbolic()               # True

# Static constructors
ExprType.list(ExprType("int"))            # list[int]
ExprType.union([ExprType("int"), ExprType("string")])  # int | string

# Generic type matching (for function signature dispatch).
# Named `match_type` rather than `match` to mirror the underlying
# Rust API (where `match` is a reserved keyword). The pure-Python
# v0 reference called this `match`; consumers porting from v0 must
# rename their call site.
generic = ExprType(TypeCode.LIST, [ExprType("T")])
concrete = ExprType("list[int]")
bindings = generic.match_type(concrete)   # {TypeCode.TYPEVAR_T: ExprType("int")}
generic.substitute(bindings)              # ExprType("list[int]")
```

### `TypeCode`

Enum identifying the kind of an `ExprType`.

```python
from openjd.expr import TypeCode

TypeCode.INT          # integer type
TypeCode.LIST         # list type (parameterized)
TypeCode.UNRESOLVED   # placeholder for unknown values during type checking
```

**Members:** `NULLTYPE`, `BOOL`, `INT`, `FLOAT`, `STRING`, `PATH`, `LIST`,
`RANGE_EXPR`, `ANY`, `UNION`, `NORETURN`, `UNRESOLVED`, `TYPEVAR_T`,
`TYPEVAR_T1`, `TYPEVAR_T2`, `TYPEVAR_T3`

### `ExprValue`

A typed value during expression evaluation. Wraps Rust `ExprValue`.

```python
from openjd.expr import ExprValue, PathFormat
from decimal import Decimal

# Construction from Python values
ExprValue(42)                             # Int
ExprValue(3.14)                           # Float
ExprValue("hello")                        # String
ExprValue(True)                           # Bool
ExprValue(None)                           # Null
ExprValue([1, 2, 3])                      # list[int]
ExprValue(Decimal("3.140"))               # Float preserving "3.140"

# Type coercion
ExprValue("42", type="int")               # Int(42)
ExprValue("/tmp", type="path", path_format=PathFormat.POSIX)  # Path
ExprValue("1-5", type="range_expr")       # RangeExpr

# Special constructors
ExprValue.from_float(3.14, "3.140")       # Float preserving original string
ExprValue.unresolved("int")              # Unresolved placeholder for type checking

# Properties
v = ExprValue(42)
v.type                                    # ExprType("int")
v.type.type_code                          # TypeCode.INT
v.is_null                                 # False
v.item()                                  # 42 (native Python value)
v.memory_size()                           # bytes used (Rust ExprValue + heap)
str(v)                                    # "42"
bool(v)                                   # True

# Sequence protocols for list and range_expr values
v = ExprValue([10, 20, 30])
len(v)                                    # 3
v[0].item()                               # 10
v[-1].item()                              # 30
[e.item() for e in v]                     # [10, 20, 30]
```

### `SymbolTable`

Hierarchical key-value store providing variable bindings for expression
evaluation. Supports dotted paths that create nested tables automatically.

```python
from openjd.expr import SymbolTable, ExprValue

# Construction
st = SymbolTable({"Param.Frame": 42, "Param.Name": "test"})
st = SymbolTable({"Param": {"Frame": 42}})       # nested dict
st = SymbolTable(source=other_symtab)             # copy

# Access
"Param.Frame" in st                               # True
st["Param.Frame"].item()                          # 42
st["Param"]                                       # SymbolTable (subtable)
st.get("Missing")                                 # None
st.keys                                           # {"Param"} — top-level keys
st.symbols                                        # {"Param.Frame", "Param.Name"} — every dotted leaf path
repr(st)                                          # SymbolTable({...})

# Mutation
st["Task.Index"] = 5

# Combine with other tables / dicts (returns a new table; later
# arguments win on key collision).
combined = st.union(other_symtab, {"Extra": 1})
```

Auto-converts Python values: `int`, `float`, `str`, `bool`, `None`, `list`,
`Decimal`, `ExprValue`, `ExprType` (→ unresolved), `RangeExpr`.

`keys` returns the top-level namespaces; `symbols` returns every
fully-qualified dotted leaf path. Both are sets and are documented
alongside the Pydantic-based v0 reference whose contract this binding
preserves.

**Equality.** Two `SymbolTable`s compare equal when they contain the
same set of dotted-path → value mappings. Insertion order in the
underlying `HashMap` does not affect equality, and equality is
recursive through nested subtables. `dict` is **not** auto-coerced
for comparison — wrap it in `SymbolTable(...)` first if you want
that.

**Hashability.** `SymbolTable` is intentionally **not** hashable.
`__setitem__` is supported, so the type is mutable; Python's hash/eq
contract requires hashable types to be effectively immutable.

`union(*others)` mirrors the v0 reference's combine-tables convenience.
The Rust crate's underlying primitive is `SymbolTable::merge_from`,
which mutates in place; `union` is the immutable equivalent built on
top of it for Python ergonomics.

### `ExprRevision` / `ExprExtension` / `HostContext` / `ExprProfile`

Profile types that select which functions, operators, and types are
available for a given evaluation. Mirror the equivalent types in the
underlying `openjd-expr` Rust crate.

```python
from openjd.expr import (
    ExprProfile, ExprRevision, ExprExtension, HostContext,
    PathMappingRule, PathFormat,
)

# Empty profile: current revision, no extensions, no host context.
ExprProfile()  # same as ExprProfile.current()
ExprProfile.current()
ExprProfile.latest()  # current revision + every known extension (intentionally
                      # unstable across crate versions; use ExprProfile.current()
                      # if you want stable parse behavior)

# Builder-style — every with_* method returns a new profile.
profile = ExprProfile().with_host_context(HostContext.unresolved())

# Three host-context states, mirroring openjd_expr::HostContext:
HostContext.none()                      # default — apply_path_mapping is not registered
HostContext.unresolved()                # template-validation time — returns unresolved[T]
HostContext.with_rules([rule, ...])     # runtime — real apply_path_mapping with rules

# Inspecting a profile
profile.revision      # ExprRevision.V2026_02
profile.extensions    # [] today
profile.host_context  # HostContext.unresolved()
profile.has_extension(ext)  # False today
```

`ExprExtension` is empty today — no expression-level extensions exist
yet — but the type is reserved for the first one. `ExprExtension.ALL`
returns `[]` today and will grow as new variants land.

### Path-mapping in evaluation

Path-mapping rules are *part of the profile*, not a per-call kwarg. To
evaluate `apply_path_mapping(...)` against a real rule set:

```python
from openjd.expr import (
    ExprProfile, HostContext, PathFormat, PathMappingRule,
    evaluate_expression,
)

rules = [PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path="/mnt/shared",
    destination_path="/local/cache",
)]

# Build the profile once; every entry point accepts profile=.
profile = ExprProfile().with_host_context(HostContext.with_rules(rules))

evaluate_expression(
    "apply_path_mapping('/mnt/shared/file.exr')",
    profile=profile,
).item()  # "/local/cache/file.exr"
```

For template-validation type-checking (where rules aren't known yet but
function signatures need to be) use `HostContext.unresolved()`:

```python
profile = ExprProfile().with_host_context(HostContext.unresolved())
evaluate_expression("apply_path_mapping('/p')", profile=profile)
# returns ExprValue.unresolved("path")
```

**Equality and hashability.** Both `HostContext` and `ExprProfile`
implement `__eq__` and `__hash__`.

* `HostContext` compares variant-by-variant; `with_rules` carries a
  list of `PathMappingRule`s and is compared by value (rule-by-rule
  in order, not as a set — order is meaningful for path-mapping
  resolution). Two distinct `with_rules` constructions with
  identical rule lists are equal and hash equal.
* `ExprProfile` compares on revision, extension set
  (insertion-order independent), and host context. Profiles built
  from the same arguments are equal and hash equal regardless of
  construction path. The extension set is canonicalised (sorted
  by debug repr) when hashing so set-equal extensions hash equal.

### `ParsedExpression`

A parsed expression that can be inspected for symbol references and
evaluated multiple times with different values.

```python
from openjd.expr import parse_expression

parsed = parse_expression("[x.upper() for x in Param.Items if len(x) > 2]")
parsed.expr                # "[x.upper() for x in Param.Items if len(x) > 2]"
parsed.accessed_symbols    # {"Param.Items"}
parsed.called_functions    # {"upper", "len"}
parsed.local_bindings      # {"x"}

result = parsed.evaluate(values={"Param.Items": ["hi", "hello", "yo"]})
result.item()              # ["HELLO"]
parsed.peak_memory_usage   # bytes
parsed.operation_count     # ops
```

### `PathFormat`

Path format enum controlling how `path` values behave.

```python
from openjd.expr import PathFormat

PathFormat.POSIX     # Unix-style paths (/)
PathFormat.WINDOWS   # Windows-style paths (\)
PathFormat.URI       # URI paths (s3://, https://)

PathFormat.POSIX.name  # "POSIX"
```

### `PathMappingRule`

A rule for mapping paths from one location to another, used by
`apply_path_mapping` and sessions for cross-platform path translation.

```python
from openjd.expr import PathMappingRule, PathFormat
from pathlib import PurePosixPath

# Construction
rule = PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path="/mnt/shared",
    destination_path="/local/cache",
)

# Apply
matched, result = rule.apply(path="/mnt/shared/project/file.exr")
# matched=True, result="/local/cache/project/file.exr"

matched, result = rule.apply(path="/other/path")
# matched=False, result="/other/path"

# Serialization
d = rule.to_dict()
# {"source_path_format": "POSIX", "source_path": "/mnt/shared", "destination_path": "/local/cache"}
rule2 = PathMappingRule.from_dict(d)
```

**Equality and hashability.** `PathMappingRule` implements `__eq__`
and `__hash__` over the three fields. Two rules compare equal when
they have identical `source_path_format`, `source_path`, and
`destination_path`; equal rules hash equal so the type is suitable
as a `set` / `dict` key.

### `RangeExpr`

Integer range expression for task parameter spaces. Parses expressions
like `"1-10"`, `"1-100:10"`, `"1,5,10-20"` into sorted, non-overlapping ranges.

```python
from openjd.expr import RangeExpr

r = RangeExpr("1-10")
len(r)          # 10
3 in r          # True
r[0]            # 1
r[-1]           # 10
list(r)         # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
r.ranges()      # [(1, 10, 1)]
r.start         # 1
r.end           # 10

r = RangeExpr("1-10:3")
list(r)         # [1, 4, 7, 10]

r = RangeExpr("1-3,10-12")
list(r)         # [1, 2, 3, 10, 11, 12]
r.ranges()      # [(1, 3, 1), (10, 12, 1)]

# Build from a list of values (ints or numeric strings, mixed allowed).
# Duplicates are removed and the result is sorted ascending.
RangeExpr.from_list([1, 3, 5, 7, 9])      # 1-9:2
RangeExpr.from_list([9, 8, 7, 6])         # 6-9
RangeExpr.from_list(["1", "2", "3"])      # 1-3
```

`RangeExpr.from_list([])` raises `ValueError`. Two `RangeExpr` values
that compare equal also hash equal (suitable as `set` / `dict` keys).

### `FormatString`

Template format string with `{{interpolation}}` syntax. Used in template
fields like command, args, job name, and embedded file data. Interpolations
contain expressions that are resolved against a symbol table at runtime.

```python
from openjd.expr import FormatString, SymbolTable

# Literal (no interpolations)
fs = FormatString("hello world")
fs.is_literal()           # True
fs.raw()                  # "hello world"

# With interpolation
fs = FormatString("render --frame {{Param.Frame}}")
fs.is_literal()           # False
fs.expression_names()     # ["Param.Frame"]
fs.has_complex_expressions()  # False (simple name reference)

# Resolve
st = SymbolTable({"Param.Frame": 42})
fs.resolve_string(st)     # "render --frame 42"

# Single-expression format string returns typed value
fs = FormatString("{{Param.Frame + 1}}")
fs.has_complex_expressions()  # True
result = fs.resolve(st)
result.item()             # 43
result.type.type_code     # TypeCode.INT
```

**Static validation.** ``validate_expressions(symtab, *, profile=None)``
walks every ``{{...}}`` segment and evaluates it
against the supplied symbol table, raising
``FormatStringValidationError`` (a ``ValueError`` subclass) on the
first failure. Returns ``None`` on success.

The intended pattern is to populate the symbol table with
``ExprValue.unresolved(T)`` placeholders for symbols whose concrete
values are not yet known — the evaluator's unresolved-propagation
rules then drive type checking through the expression tree without
requiring real values:

```python
from openjd.expr import (
    FormatString, SymbolTable, ExprType, ExprValue,
    FormatStringValidationError,
)

# At template-validation time, populate the symbol table with
# typed placeholders for parameters whose values aren't bound yet.
symtab = SymbolTable({
    "Param.Name": ExprValue.unresolved(ExprType("string")),
    "Param.Frame": ExprValue.unresolved(ExprType("int")),
})

# Valid: every interpolation resolves under the placeholder types.
FormatString("hello {{Param.Name}}").validate_expressions(symtab)

# Invalid: missing symbol — raises with a caret-anchored diagnostic.
try:
    FormatString("hello {{Param.Missing}}").validate_expressions(symtab)
except FormatStringValidationError as e:
    str(e)  # "Failed to parse interpolation expression at [6, 24].
            #  Undefined variable: 'Param.Missing'.
            #    Param.Missing
            #    ~~~~~~^~~~~~~"
```

The error message embeds the ``[start, end]`` byte offsets of the
failing ``{{...}}`` pair so callers can produce structured
diagnostics or syntax-highlight the failing segment. Mirrors the
Rust crate's ``FormatString::validate_expressions(symtab, lib)``.

**Equality and hashability.** `FormatString` implements `__eq__` and
`__hash__` on the raw source string. Two format strings compare equal
iff `a.raw() == b.raw()`; lexically distinct inputs that would
resolve to the same value (e.g. `"{{ Param.X }}"` vs `"{{Param.X}}"`)
compare unequal — this preserves source identity rather than
canonicalising whitespace. Equal format strings hash equal, so the
type is suitable as a `set` / `dict` key.

## Exceptions

```python
from openjd.expr import ExpressionError, RangeExprError, evaluate_expression

# Syntax error
try:
    evaluate_expression("1 +")
except ExpressionError as e:
    str(e)  # "Syntax error: ...\n  1 +\n  ^~~"

# Undefined variable
try:
    evaluate_expression("Param.X")
except ExpressionError as e:
    str(e)  # "Undefined variable: 'Param.X'..."

# Range expression error
try:
    RangeExpr("not-a-range")
except RangeExprError as e:
    str(e)  # "Expected integer in 'not-a-range'"
```

| Exception | Base |
|---|---|
| `ExpressionError` | `ValueError` |
| `ExpressionTypeError` | `ExpressionError` |
| `RangeExprError` | `ValueError` |
| `FormatStringValidationError` | `ValueError` |

`ExpressionError` (and its subclass `ExpressionTypeError`) accept
optional keyword arguments for attaching expression-source context:

```python
from openjd.expr import ExpressionError

# Construction with context
err = ExpressionError(
    "bad value",
    expr="Param.X + 1",  # outer expression source
    lineno=1,
    col_offset=8,
    node=ast_node,        # opaque tagalong; not used by the binding
)
err.expr           # "Param.X + 1"
err.col_offset     # 8

# Decorate an existing error caught from `evaluate_expression`.
# Returns a new error if no context is attached, or self if there
# already is one (innermost wins).
try:
    evaluate_expression("Param.X")
except ExpressionError as inner:
    raise inner.with_context("outer source", node=outer_node)

# Render the message with a custom prefix on the source line. Useful
# for let-binding errors where the expression appears as part of
# `"name = expr"`.
err.message_with_expr_prefix("x = ")
# "bad value\n  x = Param.X + 1\n          ^"
```

## Constants

```python
from openjd.expr import DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT

DEFAULT_MEMORY_LIMIT      # 100_000_000 (100 MB)
DEFAULT_OPERATION_LIMIT   # 10_000_000 (10 million)
```

## Pickle Support

The following value types are pickleable. Pickled state round-trips
through ``pickle.dumps`` / ``pickle.loads`` and compares equal to the
original.

| Type | Reduces through |
|---|---|
| ``PathFormat`` | variant name (``POSIX`` / ``WINDOWS`` / ``URI``) |
| ``TypeCode`` | variant name (``INT``, ``LIST``, ``RANGE_EXPR``, …) |
| ``ExprRevision`` | variant name (e.g. ``V2026_02``) |
| ``ExprType`` | spec-form string (``str(t)``) |
| ``ExprValue`` | constructor arguments (``item``, ``type``, ``path_format``) |
| ``RangeExpr`` | spec-form string (``str(r)``) |
| ``FormatString`` | raw input string (``fs.raw()``) |
| ``SymbolTable`` | flat ``dict[str, ExprValue]`` of all dotted leaf paths |
| ``PathMappingRule`` | ``to_dict()`` / ``from_dict()`` |
| ``HostContext`` | one of three classmethods (``none``, ``unresolved``, ``with_rules``) |
| ``ExprProfile`` | constructor arguments (``revision``, ``extensions``, ``host_context``) |
| ``ExpressionError``, ``ExpressionTypeError``, ``RangeExprError``, ``FormatStringValidationError`` | standard exception pickle, under their canonical ``openjd.expr`` module path |

The runtime type ``ParsedExpression`` is not pickleable — it holds
transient evaluation state that is not meaningful to serialize.
Re-construct it via ``parse_expression`` after loading the inputs.
