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

### `get_default_library`

Return the default function library with all built-in functions.

```python
from openjd.expr import get_default_library

lib = get_default_library()
lib.host_context_enabled  # False
```

### `escape_format_string`

Escape `{{` and `}}` in a string for use as a literal in a format string.

```python
from openjd.expr import escape_format_string

escape_format_string("use {{braces}}")  # "use {{ \"{\" + \"{\" }}braces{{ \"}\" + \"}\" }}"
```

## Types

### `ExprType`

Represents a type in the expression language. The type system includes
primitives (`int`, `float`, `string`, `bool`, `path`), compound types
(`list[T]`, `range_expr`), unions (`int | string`), nullable (`int?`),
and type variables (`T`, `T1`, `T2`, `T3`) for generic function signatures.

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

# Generic type matching (for function signature dispatch)
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
st.keys                                           # {"Param"}

# Mutation
st["Task.Index"] = 5
```

Auto-converts Python values: `int`, `float`, `str`, `bool`, `None`, `list`,
`Decimal`, `ExprValue`, `ExprType` (→ unresolved), `RangeExpr`.

### `FunctionLibrary`

Registry of functions available during expression evaluation. The default
library includes all built-in functions. Host-context functions like
`apply_path_mapping` require explicit opt-in.

```python
from openjd.expr import FunctionLibrary, evaluate_expression, PathMappingRule, PathFormat

# Default library (no host context)
lib = FunctionLibrary()
lib.host_context_enabled  # False

# Enable host-context functions with path mapping rules
rules = [PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path="/mnt/shared",
    destination_path="/local/cache",
)]
lib = FunctionLibrary().with_host_context()
evaluate_expression(
    "apply_path_mapping('/mnt/shared/file.exr')",
    library=lib,
    path_mapping_rules=rules,
).item()  # "/local/cache/file.exr"

# For job creation time (returns unresolved types)
lib = FunctionLibrary().with_unresolved_host_context()
```

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

r = RangeExpr("1-10:3")
list(r)         # [1, 4, 7, 10]

r = RangeExpr("1-3,10-12")
list(r)         # [1, 2, 3, 10, 11, 12]
r.ranges()      # [(1, 3, 1), (10, 12, 1)]
```

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

## Constants

```python
from openjd.expr import DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT

DEFAULT_MEMORY_LIMIT      # 100_000_000 (100 MB)
DEFAULT_OPERATION_LIMIT   # 10_000_000 (10 million)
```
