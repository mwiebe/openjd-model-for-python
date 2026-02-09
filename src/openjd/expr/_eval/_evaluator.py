# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Expression evaluator."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from os import name as os_name
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Optional

from .._types import ExprType, TypeCode
from .._value import ExprValue
from .._symbol_table import SymbolTable
from .._functions import FunctionLibrary, FunctionSignature
from .._errors import ExpressionError, ExpressionTypeError
from .._path_mapping import PathFormat
from .._uri_path import is_uri
from ._parse import normalize_json_literals

# Target type for evaluation - can be a single type or union
TargetType = Optional[ExprType]

# Default memory limit: 100 million bytes
DEFAULT_MEMORY_LIMIT = 100_000_000

# Default operation limit: 10 million
DEFAULT_OPERATION_LIMIT = 10_000_000


@dataclass
class EvaluationResult:
    """Result of expression evaluation."""

    value: ExprValue
    peak_memory: int


# Map internal operator names to user-friendly symbols
_OPERATOR_NAMES = {
    "__add__": "+",
    "__sub__": "-",
    "__mul__": "*",
    "__truediv__": "/",
    "__floordiv__": "//",
    "__mod__": "%",
    "__pow__": "**",
    "__neg__": "-",
    "__pos__": "+",
    "__not__": "not",
    "__lt__": "<",
    "__le__": "<=",
    "__gt__": ">",
    "__ge__": ">=",
    "__eq__": "==",
    "__ne__": "!=",
    "__contains__": "in",
    "__not_contains__": "not in",
}


def _friendly_name(name: str) -> str:
    """Convert internal function name to user-friendly name."""
    if name.startswith("__property_") and name.endswith("__"):
        return "." + name[11:-2]  # Extract property name
    return _OPERATOR_NAMES.get(name, name)


def _host_path_format() -> PathFormat:
    """Return the PathFormat matching the host OS."""
    return PathFormat.WINDOWS if os_name == "nt" else PathFormat.POSIX


class Evaluator:
    """Expression evaluator with memory-bounded execution."""

    def __init__(
        self,
        symtabs: list[SymbolTable],
        library: FunctionLibrary,
        expr: Optional[str] = None,
        memory_limit: Optional[int] = None,
        operation_limit: Optional[int] = None,
        path_format: Optional[PathFormat] = None,
        _current_memory: int = 0,
        _peak_memory: int = 0,
    ):
        self.symtabs = symtabs
        self.library = library
        self.expr = expr  # Original expression string for error messages
        self.memory_limit = memory_limit if memory_limit is not None else DEFAULT_MEMORY_LIMIT
        self.operation_limit = (
            operation_limit if operation_limit is not None else DEFAULT_OPERATION_LIMIT
        )
        self.path_format = path_format if path_format is not None else _host_path_format()
        self._current_memory = _current_memory
        self._peak_memory = _peak_memory
        self._operation_count = 0

    def pure_path(self, path_str: str) -> PurePath:
        """Create a PurePath using the evaluator's path_format.

        Note: Do NOT use for URI paths — use uri-aware functions instead.
        """
        if self.path_format == PathFormat.POSIX:
            return PurePosixPath(path_str)
        else:
            return PureWindowsPath(path_str)

    def is_uri_path(self, path_str: str) -> bool:
        """Return True if path_str is a URI (has a scheme:// prefix)."""
        return is_uri(path_str)

    def make_path_value(self, string_value: str) -> "ExprValue":
        """Create a PATH ExprValue that carries this evaluator's path_format.

        Normalizes the path through pure_path to ensure OS-native separators,
        unless the path is a URI.
        """
        if not is_uri(string_value):
            string_value = str(self.pure_path(string_value))

        return ExprValue._create(
            ExprType.PATH, string_value=string_value, path_format=self.path_format
        )

    @property
    def peak_memory(self) -> int:
        """Peak memory usage during evaluation."""
        return self._peak_memory

    @property
    def operation_count(self) -> int:
        """Total operation count during evaluation."""
        return self._operation_count

    def _count_operation(self) -> None:
        """Count a single operation (e.g., a function call)."""
        self._operation_count += 1
        if self._operation_count > self.operation_limit:
            raise ExpressionError(
                f"Expression operation count ({self._operation_count}) "
                f"exceeded limit ({self.operation_limit})"
            )

    def _count_operations(self, count: int) -> None:
        """Count multiple operations (e.g., iterating through a list)."""
        self._operation_count += count
        if self._operation_count > self.operation_limit:
            raise ExpressionError(
                f"Expression operation count ({self._operation_count}) "
                f"exceeded limit ({self.operation_limit})"
            )

    def _count_string_ops(self, length: int) -> None:
        """Count operations for processing a string or path value.

        Adds ceil(length / 256) to the operation count. This ensures that
        functions doing work proportional to string length are bounded.
        """
        if length > 0:
            self._count_operations(-(-length // 256))  # ceil division

    def _track(self, value: ExprValue) -> ExprValue:
        """Track memory for a newly created value."""
        self._current_memory += value.memory_size()
        if self._current_memory > self._peak_memory:
            self._peak_memory = self._current_memory
        if self._current_memory > self.memory_limit:
            raise ExpressionError(
                f"Expression memory usage ({self._current_memory} bytes) "
                f"exceeded limit ({self.memory_limit} bytes)"
            )
        return value

    def _release(self, *values: ExprValue) -> None:
        """Release memory for consumed values."""
        for v in values:
            self._current_memory -= v.memory_size()

    def _error(self, message: str, node: Optional[ast.AST] = None) -> ExpressionError:
        """Create an ExpressionError with location context."""
        return ExpressionError(message, expr=self.expr, node=node)

    def _type_error(self, message: str, node: Optional[ast.AST] = None) -> ExpressionTypeError:
        """Create an ExpressionTypeError with location context."""
        return ExpressionTypeError(message, expr=self.expr, node=node)

    def evaluate(self, node: ast.AST, target_type: TargetType = None) -> ExprValue:
        """Evaluate an AST node. Returns a tracked value (memory-accounted)."""
        node = normalize_json_literals(node)

        if isinstance(node, ast.Expression):
            return self.evaluate(node.body, target_type)

        if isinstance(node, ast.Constant):
            return self._track(self._eval_constant(node, target_type))

        if isinstance(node, ast.Name):
            return self._track(self._eval_name(node, target_type))

        if isinstance(node, ast.Attribute):
            return self._track(self._eval_attribute(node, target_type))

        if isinstance(node, ast.BinOp):
            return self._eval_binop(node, target_type)

        if isinstance(node, ast.UnaryOp):
            return self._eval_unaryop(node, target_type)

        if isinstance(node, ast.Compare):
            return self._eval_compare(node, target_type)

        if isinstance(node, ast.BoolOp):
            return self._eval_boolop(node, target_type)

        if isinstance(node, ast.IfExp):
            return self._eval_ifexp(node, target_type)

        if isinstance(node, ast.Call):
            return self._eval_call(node, target_type)

        if isinstance(node, ast.List):
            return self._eval_list(node, target_type)

        if isinstance(node, ast.ListComp):
            return self._eval_listcomp(node, target_type)

        if isinstance(node, ast.Subscript):
            return self._eval_subscript(node, target_type)

        raise ExpressionError(f"Unsupported expression: {type(node).__name__}")

    def _eval_constant(self, node: ast.Constant, target_type: TargetType) -> ExprValue:
        try:
            if isinstance(node.value, float) and self.expr is not None:
                original = ast.get_source_segment(self.expr, node)
                return ExprValue.from_float(node.value, original)
            return ExprValue(node.value)
        except (TypeError, ExpressionError) as e:
            raise self._error(str(e), node)

    def _eval_name(self, node: ast.Name, target_type: TargetType) -> ExprValue:
        return self._lookup_variable([node.id])

    def _eval_attribute(self, node: ast.Attribute, target_type: TargetType) -> ExprValue:
        # Try to collect as variable path first (e.g., Param.InputFile.name)
        path = self._try_collect_attribute_path(node)
        if path is not None:
            # Try full path as variable
            try:
                return self._lookup_variable(path)
            except ExpressionError:
                pass
            # Try progressively shorter prefixes as variable, rest as properties
            for i in range(len(path) - 1, 0, -1):
                try:
                    base_value = self._lookup_variable(path[:i])
                except ExpressionError:
                    continue
                # Base resolved — apply remaining path as property accesses.
                # Let property errors propagate (don't swallow them).
                for prop_name in path[i:]:
                    base_value = self._call_function(
                        f"__property_{prop_name}__", [base_value], node=node
                    )
                return base_value
            raise self._error(f"Undefined variable: {'.'.join(path)}", node)

        # Base is not a simple path (e.g., function call) - evaluate it
        base_value = self.evaluate(node.value)
        return self._call_function(f"__property_{node.attr}__", [base_value], node=node)

    def _try_collect_attribute_path(self, node: ast.AST) -> list[str] | None:
        """Try to collect attribute path, return None if not a simple path."""
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            base = self._try_collect_attribute_path(node.value)
            if base is not None:
                return base + [node.attr]
        return None

    def _lookup_variable(self, path: list[str]) -> ExprValue:
        for symtab in self.symtabs:
            result = self._lookup_path(path, symtab)
            if result is not None:
                self._check_path_format(result, path)
                return result
        raise ExpressionError(f"Undefined variable: {'.'.join(path)}")

    def _check_path_format(self, value: ExprValue, path: list[str]) -> None:
        """Raise if a PATH value's path_format doesn't match the evaluator's."""
        tc = value.type.type_code
        if tc == TypeCode.PATH:
            if value._path_format != self.path_format:
                raise ExpressionError(
                    f"Path format mismatch for '{'.'.join(path)}': "
                    f"value has {value._path_format.name} but evaluator uses {self.path_format.name}"
                )
        elif tc == TypeCode.LIST and value.type.type_params:
            if value.type.type_params[0].type_code == TypeCode.PATH:
                items = value.to_expr_value_list()
                if items and items[0]._path_format != self.path_format:
                    raise ExpressionError(
                        f"Path format mismatch for '{'.'.join(path)}': "
                        f"value has {items[0]._path_format.name} but evaluator uses {self.path_format.name}"
                    )

    def _lookup_path(self, path: list[str], symtab: SymbolTable) -> Optional[ExprValue]:
        current: SymbolTable | ExprValue = symtab
        for name in path:
            if isinstance(current, SymbolTable):
                entry = current.get(name)
                if entry is None:
                    return None
                current = entry
            else:
                return None
        if isinstance(current, ExprValue):
            return current
        return None

    def _eval_binop(self, node: ast.BinOp, target_type: TargetType) -> ExprValue:
        op_map = {
            ast.Add: "__add__",
            ast.Sub: "__sub__",
            ast.Mult: "__mul__",
            ast.Div: "__truediv__",
            ast.FloorDiv: "__floordiv__",
            ast.Mod: "__mod__",
            ast.Pow: "__pow__",
        }
        op_name = op_map.get(type(node.op))
        if op_name is None:
            raise self._error(f"Unsupported operator: {type(node.op).__name__}", node)

        left = self.evaluate(node.left)
        right = self.evaluate(node.right)

        result = self._call_function(op_name, [left, right], node=node)
        self._release(left, right)
        return self._track(result)

    def _eval_unaryop(self, node: ast.UnaryOp, target_type: TargetType) -> ExprValue:
        # Fold -<int literal> to handle INT64_MIN (-2**63) which can't be
        # represented as a positive literal followed by negation.
        if (
            isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
        ):
            try:
                return self._track(ExprValue(-node.operand.value))
            except ExpressionError as e:
                raise self._error(str(e).split("\n")[0], node)

        op_map = {
            ast.UAdd: "__pos__",
            ast.USub: "__neg__",
            ast.Not: "__not__",
        }
        op_name = op_map.get(type(node.op))
        if op_name is None:
            raise self._error(f"Unsupported operator: {type(node.op).__name__}", node)

        operand = self.evaluate(node.operand)
        result = self._call_function(op_name, [operand], node=node)
        self._release(operand)
        return self._track(result)

    def _eval_compare(self, node: ast.Compare, target_type: TargetType) -> ExprValue:
        op_map = {
            ast.Lt: "__lt__",
            ast.LtE: "__le__",
            ast.Gt: "__gt__",
            ast.GtE: "__ge__",
            ast.Eq: "__eq__",
            ast.NotEq: "__ne__",
            ast.In: "__contains__",
            ast.NotIn: "__not_contains__",
        }

        # Chained comparisons: 1 < 2 < 3 means 1 < 2 and 2 < 3
        left = self.evaluate(node.left)
        any_unknown = False
        for op, comparator in zip(node.ops, node.comparators):
            op_name = op_map.get(type(op))
            if op_name is None:
                raise self._error(f"Unsupported comparison: {type(op).__name__}", node)

            right = self.evaluate(comparator)

            # "x in list" -> __contains__(list, x)
            if isinstance(op, (ast.In, ast.NotIn)):
                result = self._call_function(op_name, [right, left], node=node)
            else:
                result = self._call_function(op_name, [left, right], node=node)

            self._release(left)

            # Unresolved result in chained comparison — can't short-circuit,
            # continue checking remaining comparisons for type errors
            if result.type.type_code == TypeCode.UNRESOLVED:
                any_unknown = True
                left = right
                continue

            if not result.item():
                self._release(right)
                return ExprValue(False)

            left = right

        self._release(left)
        if any_unknown:
            return ExprValue.unresolved(ExprType.BOOL)
        return ExprValue(True)

    def _eval_boolop(self, node: ast.BoolOp, target_type: TargetType) -> ExprValue:
        # and/or are value-returning with null-coalescing semantics.
        # Only null and false are falsy. All other values are truthy.
        def _is_falsy(v: ExprValue) -> bool:
            return v.is_null or (v.type.type_code == TypeCode.BOOL and v.item() is False)

        result: ExprValue
        any_unknown = False
        if isinstance(node.op, ast.And):
            # a and b: if a is falsy, return a; otherwise evaluate and return b
            for value_node in node.values:
                if any_unknown:
                    try:
                        result = self.evaluate(value_node, target_type)
                    except (ExpressionError, ExpressionTypeError):
                        continue
                else:
                    result = self.evaluate(value_node, target_type)
                if result.type.type_code == TypeCode.UNRESOLVED:
                    any_unknown = True
                    continue
                if _is_falsy(result):
                    return result
            if any_unknown:
                return ExprValue.unresolved(result.type if result else ExprType.BOOL)
            return result
        elif isinstance(node.op, ast.Or):
            # a or b: if a is falsy, evaluate and return b; otherwise return a
            for value_node in node.values:
                if any_unknown:
                    try:
                        result = self.evaluate(value_node, target_type)
                    except (ExpressionError, ExpressionTypeError):
                        continue
                else:
                    result = self.evaluate(value_node, target_type)
                if result.type.type_code == TypeCode.UNRESOLVED:
                    any_unknown = True
                    continue
                if not _is_falsy(result):
                    return result
            if any_unknown:
                return ExprValue.unresolved(result.type if result else ExprType.BOOL)
            return result
        raise ExpressionError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def _eval_ifexp(self, node: ast.IfExp, target_type: TargetType) -> ExprValue:
        test = self.evaluate(node.test, ExprType.BOOL)

        # Unresolved condition: must be compatible with bool
        if test.type.type_code == TypeCode.UNRESOLVED:
            if ExprType.BOOL.match(test.type.type_params[0]) is None:
                raise self._type_error(
                    f"Condition must be a boolean, got {test.type.type_params[0]}", node.test
                )

            body_err = None
            orelse_err = None
            body_val = None
            orelse_val = None
            try:
                body_val = self.evaluate(node.body, target_type)
            except (ExpressionError, ExpressionTypeError) as e:
                body_err = e
            try:
                orelse_val = self.evaluate(node.orelse, target_type)
            except (ExpressionError, ExpressionTypeError) as e:
                orelse_err = e

            if body_err and orelse_err:
                raise self._error(
                    f"Both branches will fail in the if/else:\n"
                    f"  if-branch: {body_err}\n"
                    f"  else-branch: {orelse_err}",
                    node,
                )
            if body_err:
                # Only else branch succeeded
                result = orelse_val
            elif orelse_err:
                # Only if branch succeeded
                result = body_val
            else:
                # Both succeeded — union the types
                result_type = ExprType(TypeCode.UNION, [body_val.type, orelse_val.type])  # type: ignore[union-attr]
                return ExprValue.unresolved(
                    result_type.type_params[0]
                    if result_type.type_code == TypeCode.UNRESOLVED
                    else result_type
                )

            # One branch succeeded — wrap in unresolved if not already
            if result.type.type_code != TypeCode.UNRESOLVED:  # type: ignore[union-attr]
                return ExprValue.unresolved(result.type)  # type: ignore[union-attr]
            return result  # type: ignore[return-value]

        if test.type.type_code != TypeCode.BOOL:
            raise self._type_error("Condition must be a boolean", node.test)
        if test.item():
            return self.evaluate(node.body, target_type)
        return self.evaluate(node.orelse, target_type)

    def _eval_call(self, node: ast.Call, target_type: TargetType) -> ExprValue:
        # Handle method calls: obj.method(args) -> method(obj, args)
        # Track whether this is a method call to disable receiver coercion
        is_method_call = False
        if isinstance(node.func, ast.Attribute):
            obj = self.evaluate(node.func.value)
            func_name = node.func.attr
            other_args = [self.evaluate(arg) for arg in node.args]
            args = [obj] + other_args
            is_method_call = True
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            args = [self.evaluate(arg) for arg in node.args]
        else:
            raise self._error("Invalid function call", node)

        # Reject direct calls to dunder methods (internal implementation details)
        if func_name.startswith("__") and func_name.endswith("__"):
            raise self._error(
                f"Cannot call '{func_name}' directly. Use the corresponding operator or function instead.",
                node,
            )

        # Reject calling properties as methods (e.g., path.stem() should be path.stem)
        if is_method_call and self.library.get_signatures(f"__property_{func_name}__"):
            raise self._error(
                f"'{func_name}' is a property, not a method. Use .{func_name} instead of .{func_name}()",
                node,
            )

        result = self._call_function(func_name, args, is_method_call=is_method_call, node=node)

        self._release(*args)
        return self._track(result)

    def _call_function(
        self,
        name: str,
        args: list[ExprValue],
        *,
        is_method_call: bool = False,
        node: Optional[ast.AST] = None,
    ) -> ExprValue:
        signatures = self.library.get_signatures(name)
        if not signatures:
            friendly = _friendly_name(name)
            if friendly != name:
                # It's a __property_X__ lookup that failed - check if it's a method
                prop_name = friendly[1:]  # Remove leading "."
                if self.library.get_signatures(prop_name):
                    raise self._error(
                        f"'{prop_name}' is a method, not a property. Did you mean {prop_name}()?",
                        node,
                    )
                raise self._error(f"Unknown property '{prop_name}'", node)
            raise self._error(f"Unknown function: {name}", node)

        # Count every function call as 1 operation
        try:
            self._count_operation()
        except ExpressionError as e:
            if e.expr is None and self.expr and node:
                raise e.with_context(self.expr, node)
            raise

        # Helper to call impl and wrap any errors with context
        def call_impl(sig: FunctionSignature, call_args: list[ExprValue]) -> ExprValue:
            # If any argument is unresolved, return unresolved[return_type] without calling impl
            if any(a.type.type_code == TypeCode.UNRESOLVED for a in call_args):
                return ExprValue.unresolved(sig.return_type)
            try:
                return sig.impl(self, *call_args)
            except (ExpressionError, ExpressionTypeError) as e:
                # Add location context if not already present
                if e.expr is None and self.expr and node:
                    raise e.with_context(self.expr, node)
                raise

        # Find matching signature (non-generic first)
        for sig in signatures:
            if len(sig.param_types) != len(args):
                continue
            if sig.is_generic():
                continue
            if self._types_match(args, sig.param_types):
                return call_impl(sig, args)

        # Try with coercion (non-generic)
        # For method calls, skip coercion on the first argument (receiver)
        for sig in signatures:
            if len(sig.param_types) != len(args):
                continue
            if sig.is_generic():
                continue
            coerced = self._try_coerce_args(args, sig.param_types, skip_first=is_method_call)
            if coerced is not None:
                return call_impl(sig, coerced)

        # Try generic signatures
        for sig in signatures:
            if len(sig.param_types) != len(args):
                continue
            if not sig.is_generic():
                continue
            result = self._try_generic_match(sig, args, node=node)
            if result is not None:
                return result

        # Build user-friendly error message
        arg_types = [
            str(a.type.type_params[0]) if a.type.type_code == TypeCode.UNRESOLVED else str(a.type)
            for a in args
        ]
        friendly = _friendly_name(name)
        if friendly in _OPERATOR_NAMES.values():
            # It's an operator
            if len(args) == 2:
                raise self._type_error(
                    f"Cannot use '{friendly}' operator with {arg_types[0]} and {arg_types[1]}",
                    node,
                )
            elif len(args) == 1:
                raise self._type_error(
                    f"Cannot use '{friendly}' operator with {arg_types[0]}", node
                )

        # Check if it's an argument count mismatch vs type mismatch
        available_arities = sorted({len(sig.param_types) for sig in signatures})
        if len(args) not in available_arities:
            if len(available_arities) == 1:
                expected_count = available_arities[0]
                raise self._type_error(
                    f"{friendly}() takes {expected_count} argument(s), but {len(args)} were given",
                    node,
                )
            else:
                expected_str = ", ".join(str(a) for a in available_arities)
                raise self._type_error(
                    f"{friendly}() takes {expected_str} arguments, but {len(args)} were given",
                    node,
                )

        # Type mismatch - show available types for method/property calls
        if args:
            receiver_type = args[0].type
            if receiver_type.type_code == TypeCode.UNRESOLVED:
                receiver_type = receiver_type.type_params[0]
            available_types = sorted(
                {str(sig.param_types[0]) for sig in signatures if sig.param_types}
            )
            if available_types:
                if name.startswith("__property_") and name.endswith("__"):
                    # Property access
                    prop_name = friendly[1:]  # Remove leading "."
                    raise self._type_error(
                        f"'{prop_name}' property is not available for {receiver_type}. "
                        f"Available for: {', '.join(available_types)}",
                        node,
                    )
                elif is_method_call:
                    raise self._type_error(
                        f"{friendly}() is not available for {receiver_type}. "
                        f"Available for: {', '.join(available_types)}",
                        node,
                    )

        raise self._type_error(
            f"No matching signature for {friendly}({', '.join(arg_types)})", node
        )

    def _try_generic_match(
        self,
        sig: FunctionSignature,
        args: list[ExprValue],
        node: Optional[ast.AST] = None,
    ) -> Optional[ExprValue]:
        """Try to match args against a generic signature.

        When binding type variables, unresolved[T] and T are treated as compatible
        (e.g., T=int from a list and T=unresolved[int] from an item). The concrete
        binding is preferred since it's more precise for return type substitution.
        """
        # Collect type variable bindings from all args
        bindings: dict[TypeCode, ExprType] = {}
        for param_type, arg in zip(sig.param_types, args):
            match = param_type.match(arg.type)
            if match is None:
                return None
            for k, v in match.items():
                if k in bindings and bindings[k] != v:
                    # Check if one is unresolved[T] and the other is T — compatible
                    existing = bindings[k]
                    if existing.type_code == TypeCode.UNRESOLVED and existing.type_params[0] == v:
                        # Keep the concrete binding
                        bindings[k] = v
                    elif v.type_code == TypeCode.UNRESOLVED and v.type_params[0] == existing:
                        # Keep the existing concrete binding
                        pass
                    else:
                        return None
                else:
                    bindings[k] = v

        # All args matched, call the implementation with error wrapping
        # If any argument is unresolved, return unresolved[return_type] without calling impl
        if any(a.type.type_code == TypeCode.UNRESOLVED for a in args):
            return_type = sig.return_type.substitute(bindings)
            return ExprValue.unresolved(return_type)
        try:
            return sig.impl(self, *args)
        except (ExpressionError, ExpressionTypeError) as e:
            if e.expr is None and self.expr and node:
                raise e.with_context(self.expr, node)
            raise

    def _types_match(self, args: list[ExprValue], param_types: list[ExprType]) -> bool:
        return all(p.match(a.type) is not None for a, p in zip(args, param_types))

    def _try_coerce_args(
        self,
        args: list[ExprValue],
        param_types: list[ExprType],
        *,
        skip_first: bool = False,
    ) -> Optional[list[ExprValue]]:
        result = []
        for i, (arg, param_type) in enumerate(zip(args, param_types)):
            if skip_first and i == 0:
                # For method calls, first arg (receiver) must match exactly
                if param_type.match(arg.type) is None:
                    return None
                result.append(arg)
            else:
                coerced = self._try_coerce(arg, param_type)
                if coerced is None:
                    return None
                result.append(coerced)
        return result

    def _try_coerce(self, value: ExprValue, target: ExprType) -> Optional[ExprValue]:
        if value.type == target:
            return value
        # unresolved[T] -> unresolved[target] if T can be coerced to target
        if value.type.type_code == TypeCode.UNRESOLVED:
            constraint = value.type.type_params[0]
            # Create a dummy concrete check — can the constraint type coerce?
            if constraint == target:
                return ExprValue.unresolved(target)
            if constraint.type_code == TypeCode.INT and target.type_code == TypeCode.FLOAT:
                return ExprValue.unresolved(target)
            if constraint.type_code == TypeCode.PATH and target.type_code == TypeCode.STRING:
                return ExprValue.unresolved(target)
            if constraint.type_code == TypeCode.RANGE_EXPR and target.type_code == TypeCode.STRING:
                return ExprValue.unresolved(target)
            if constraint.type_code == TypeCode.RANGE_EXPR and target.type_code == TypeCode.LIST:
                if target.type_params and target.type_params[0].type_code == TypeCode.INT:
                    return ExprValue.unresolved(target)
            return None
        # int -> float
        if value.type.type_code == TypeCode.INT and target.type_code == TypeCode.FLOAT:
            return ExprValue(float(value.item()))
        # path -> string
        if value.type.type_code == TypeCode.PATH and target.type_code == TypeCode.STRING:
            return ExprValue(value.to_string())
        # range_expr -> string
        if value.type.type_code == TypeCode.RANGE_EXPR and target.type_code == TypeCode.STRING:
            return ExprValue(value.to_string())
        # range_expr -> list[int]
        if value.type.type_code == TypeCode.RANGE_EXPR and target.type_code == TypeCode.LIST:
            if target.type_params and target.type_params[0].type_code == TypeCode.INT:
                return ExprValue._from_list([ExprValue(i) for i in value.item()], ExprType.INT)
        # list[T] -> list[U] when T can be coerced to U
        if value.type.type_code == TypeCode.LIST and target.type_code == TypeCode.LIST:
            if target.type_params and value.type.type_params:
                target_elem = target.type_params[0]
                coerced_elems = []
                for elem in value.to_expr_value_list():
                    coerced = self._try_coerce(elem, target_elem)
                    if coerced is None:
                        return None
                    coerced_elems.append(coerced)
                return ExprValue._from_list(coerced_elems, target_elem)
        return None

    def try_coerce_nondestructive(self, value: ExprValue, target: ExprType) -> Optional[ExprValue]:
        """Non-destructive coercion for list element context."""
        if value.type == target:
            return value
        tc = value.type.type_code
        # bool/int/float/path/range_expr -> string
        if target.type_code == TypeCode.STRING:
            if tc in (
                TypeCode.BOOL,
                TypeCode.INT,
                TypeCode.FLOAT,
                TypeCode.PATH,
                TypeCode.RANGE_EXPR,
            ):
                return ExprValue(value.to_string())
        # range_expr -> list[int]
        if target.type_code == TypeCode.LIST and tc == TypeCode.RANGE_EXPR:
            if target.type_params and target.type_params[0].type_code == TypeCode.INT:
                return ExprValue._from_list([ExprValue(i) for i in value.item()], ExprType.INT)
        # string -> path
        if target.type_code == TypeCode.PATH and tc == TypeCode.STRING:
            return self.make_path_value(value.item())
        # float/string -> int (must be exact)
        if target.type_code == TypeCode.INT:
            if tc == TypeCode.FLOAT:
                if value.item() == int(value.item()):
                    return ExprValue(int(value.item()))
                raise ExpressionTypeError(
                    f"Cannot coerce {value.item()} to int: not a whole number"
                )
            if tc == TypeCode.STRING:
                try:
                    return ExprValue(int(value.item()))
                except ValueError:
                    raise ExpressionTypeError(f"Cannot coerce {value.item()!r} to int")
        # int/string -> float
        if target.type_code == TypeCode.FLOAT:
            if tc == TypeCode.INT:
                return ExprValue(float(value.item()))
            if tc == TypeCode.STRING:
                try:
                    return ExprValue(float(value.item()))
                except ValueError:
                    raise ExpressionTypeError(f"Cannot coerce {value.item()!r} to float")
        return None

    def try_coerce_list(self, value: ExprValue, target: ExprType) -> Optional[ExprValue]:
        """Try to coerce a list value to a target list type by coercing elements."""
        if value.type.type_code != TypeCode.LIST or target.type_code != TypeCode.LIST:
            return None
        if not target.type_params:
            return None
        target_elem = target.type_params[0]
        items = value.to_expr_value_list()
        coerced_items = []
        for item in items:
            if item.type == target_elem:
                coerced_items.append(item)
            else:
                coerced = self.try_coerce_nondestructive(item, target_elem)
                if coerced is None:
                    return None
                coerced_items.append(coerced)
        return ExprValue._from_list(coerced_items, target_elem)

    def _eval_list(self, node: ast.List, target_type: TargetType) -> ExprValue:
        if not node.elts:
            # Empty list - use target type if available, otherwise list[?]
            if target_type:
                if target_type.type_code == TypeCode.LIST and target_type.type_params:
                    return self._track(ExprValue._from_list([], target_type.type_params[0]))
                elif target_type.type_code == TypeCode.UNION:
                    for t in target_type.type_params:
                        if t.type_code == TypeCode.LIST and t.type_params:
                            return self._track(ExprValue._from_list([], t.type_params[0]))
            # Return list[?] - implicitly convertible to list[T] for any T
            return self._track(ExprValue._from_list([], ExprType.NULLTYPE))

        # Find target element type if there's a list type in target_type
        target_elem_type = None
        if target_type:
            if target_type.type_code == TypeCode.LIST and target_type.type_params:
                if target_type.type_params[0].type_code != TypeCode.NULLTYPE:
                    target_elem_type = target_type.type_params[0]
            elif target_type.type_code == TypeCode.UNION:
                list_types = [
                    t
                    for t in target_type.type_params
                    if t.type_code == TypeCode.LIST
                    and t.type_params
                    and t.type_params[0].type_code != TypeCode.NULLTYPE
                ]
                if len(list_types) == 1:
                    target_elem_type = list_types[0].type_params[0]

        # Pass target element type to nested evaluations for recursive coercion
        elem_target_type = target_elem_type
        values = [self.evaluate(elt, elem_target_type) for elt in node.elts]

        # Check if any element is unresolved
        has_unknown = any(v.type.type_code == TypeCode.UNRESOLVED for v in values)

        # Reject null values in list literals
        for v in values:
            if v.is_null:
                raise self._type_error("null/None cannot be an element of a list literal", node)

        # If any element is unresolved, infer element type from constraints and
        # return unresolved[list[T]] — we know the type but not the values
        if has_unknown:
            # Unwrap unresolved[T] -> T for type inference
            elem_types = [
                v.type.type_params[0] if v.type.type_code == TypeCode.UNRESOLVED else v.type
                for v in values
            ]
            try:
                elem_type = self._infer_element_type_from_types(elem_types)
            except ExpressionTypeError as e:
                raise self._type_error(str(e), node)
            return self._track(ExprValue.unresolved(ExprType(TypeCode.LIST, [elem_type])))

        # If we have a target element type, coerce all elements non-destructively
        if target_elem_type:
            coerced_values = []
            for v in values:
                coerced = self.try_coerce_nondestructive(v, target_elem_type)
                if coerced is None:
                    raise ExpressionTypeError(
                        f"Cannot coerce {v.type} to {target_elem_type} in list literal"
                    )
                coerced_values.append(coerced)
            self._release(*values)
            return self._track(ExprValue._from_list(coerced_values, target_elem_type))

        # Infer element type from all elements
        try:
            elem_type = self._infer_list_element_type(values)
        except ExpressionTypeError as e:
            raise self._type_error(str(e), node)

        # Validate nesting depth (max 2 levels per RFC 0005)
        if elem_type.type_code == TypeCode.LIST and elem_type.type_params:
            inner = elem_type.type_params[0]
            if inner.type_code == TypeCode.LIST:
                raise ExpressionTypeError(
                    "Lists cannot be nested more than 2 levels deep (e.g., list[list[int]] is allowed, "
                    "but list[list[list[int]]] is not)"
                )

        # Coerce elements to the inferred type (e.g., int -> float)
        coerced_values = []
        for v in values:
            if v.type == elem_type:
                coerced_values.append(v)
            elif v.type.type_code == TypeCode.INT and elem_type.type_code == TypeCode.FLOAT:
                coerced_values.append(ExprValue(float(v.item())))
            elif v.type.type_code == TypeCode.PATH and elem_type.type_code == TypeCode.STRING:
                coerced_values.append(ExprValue(str(v.item())))
            elif v.type.type_code == TypeCode.LIST and elem_type.type_code == TypeCode.LIST:
                # Coerce inner list elements (e.g., list[int] -> list[float], list[path] -> list[string])
                target_inner = elem_type.type_params[0] if elem_type.type_params else None
                v_inner = v.type.type_params[0] if v.type.type_params else None
                if target_inner and v_inner and v_inner != target_inner:
                    if (
                        v_inner.type_code == TypeCode.INT
                        and target_inner.type_code == TypeCode.FLOAT
                    ):
                        inner_items = [ExprValue(float(e.item())) for e in v.to_expr_value_list()]
                        coerced_values.append(ExprValue._from_list(inner_items, target_inner))
                    elif (
                        v_inner.type_code == TypeCode.PATH
                        and target_inner.type_code == TypeCode.STRING
                    ):
                        inner_items = [ExprValue(str(e.item())) for e in v.to_expr_value_list()]
                        coerced_values.append(ExprValue._from_list(inner_items, target_inner))
                    else:
                        coerced_values.append(v)
                else:
                    coerced_values.append(v)
            else:
                coerced_values.append(v)
        self._release(*values)
        return self._track(ExprValue._from_list(coerced_values, elem_type))

    def _infer_list_element_type(self, values: list[ExprValue]) -> ExprType:
        """Infer the element type for a list literal from its values."""
        try:
            return ExprValue._infer_list_element_type(values)
        except TypeError as e:
            raise ExpressionTypeError(str(e).replace("List", "List literal"))

    def _infer_element_type_from_types(self, types: list[ExprType]) -> ExprType:
        """Infer the element type from a list of types (used when some elements are unresolved)."""
        first = types[0]
        if all(t == first for t in types):
            return first
        type_codes = {t.type_code for t in types}
        if type_codes == {TypeCode.INT, TypeCode.FLOAT}:
            return ExprType.FLOAT
        if type_codes == {TypeCode.PATH, TypeCode.STRING}:
            return ExprType.STRING
        unique = sorted(set(str(t) for t in types))
        raise ExpressionTypeError(f"List literal contains incompatible types: {', '.join(unique)}")

    def _eval_listcomp(self, node: ast.ListComp, target_type: TargetType) -> ExprValue:
        if len(node.generators) != 1:
            raise ExpressionError("Only single generator list comprehensions supported")
        gen = node.generators[0]
        if not isinstance(gen.target, ast.Name):
            raise ExpressionError("List comprehension target must be a simple name")

        var_name = gen.target.id
        iter_val = self.evaluate(gen.iter)

        # Unresolved iterable: loop variable becomes unresolved[elem_type], evaluate body once
        if iter_val.type.type_code == TypeCode.UNRESOLVED:
            constraint = iter_val.type.type_params[0]
            if constraint.type_code == TypeCode.LIST and constraint.type_params:
                elem_constraint = constraint.type_params[0]
            elif constraint.type_code == TypeCode.RANGE_EXPR:
                elem_constraint = ExprType.INT
            else:
                raise ExpressionTypeError("List comprehension requires list or range_expr")
            local_symtab = SymbolTable({var_name: ExprValue.unresolved(elem_constraint)})
            saved_symtabs = self.symtabs
            self.symtabs = [local_symtab] + self.symtabs
            try:
                elem_result = self.evaluate(node.elt, target_type)
                for cond in gen.ifs:
                    self.evaluate(cond, ExprType.BOOL)
            finally:
                self.symtabs = saved_symtabs
            result_elem_type = (
                elem_result.type.type_params[0]
                if elem_result.type.type_code == TypeCode.UNRESOLVED
                else elem_result.type
            )
            return self._track(ExprValue.unresolved(ExprType(TypeCode.LIST, [result_elem_type])))

        # Get iterable items from list or range_expr
        if iter_val.type.type_code == TypeCode.LIST:
            items = iter_val.to_expr_value_list()
        elif iter_val.type.type_code == TypeCode.RANGE_EXPR:
            items = [ExprValue(i) for i in iter_val.item()]
        else:
            raise ExpressionTypeError("List comprehension requires list or range_expr")

        # Count iterations as operations
        self._count_operations(len(items))

        results = []
        saved_symtabs = self.symtabs
        for item in items:
            # Create local scope with loop variable
            local_symtab = SymbolTable({var_name: item})
            self.symtabs = [local_symtab] + saved_symtabs

            # Check filter conditions
            skip = False
            for cond in gen.ifs:
                cond_val = self.evaluate(cond, ExprType.BOOL)
                if not cond_val.item():
                    skip = True
                    break
            if skip:
                continue

            # Evaluate element expression
            elem_result = self.evaluate(node.elt, target_type)
            results.append(elem_result)

        self.symtabs = saved_symtabs

        self._release(iter_val)
        if not results:
            # Return list[?] for empty comprehension result
            return self._track(ExprValue._from_list([], ExprType.NULLTYPE))
        elem_type = results[0].type

        # Validate nesting depth (max 2 levels per RFC 0005)
        if elem_type.type_code == TypeCode.LIST and elem_type.type_params:
            inner = elem_type.type_params[0]
            if inner.type_code == TypeCode.LIST:
                raise ExpressionTypeError(
                    "Lists cannot be nested more than 2 levels deep (e.g., list[list[int]] is allowed, "
                    "but list[list[list[int]]] is not)"
                )

        self._release(*results)
        return self._track(ExprValue._from_list(results, elem_type))

    def _eval_subscript(self, node: ast.Subscript, target_type: TargetType) -> ExprValue:
        value = self.evaluate(node.value)

        # Handle slice syntax: v[start:stop:step]
        if isinstance(node.slice, ast.Slice):
            start = self.evaluate(node.slice.lower) if node.slice.lower else ExprValue.null()
            stop = self.evaluate(node.slice.upper) if node.slice.upper else ExprValue.null()
            step = self.evaluate(node.slice.step) if node.slice.step else ExprValue.null()

            # Validate slice bounds are int, null, or unresolved[int]
            for bound, name in [(start, "start"), (stop, "stop"), (step, "step")]:
                if bound.is_null:
                    continue
                if bound.type.type_code == TypeCode.UNRESOLVED:
                    if ExprType.INT.match(bound.type.type_params[0]) is None:
                        raise self._type_error(f"Slice {name} must be an integer", node)
                elif bound.type.type_code != TypeCode.INT:
                    raise self._type_error(f"Slice {name} must be an integer", node)

            result = self._call_function("__getitem__", [value, start, stop, step], node=node)
            self._release(value)
            if node.slice.lower:
                self._release(start)
            if node.slice.upper:
                self._release(stop)
            if node.slice.step:
                self._release(step)
            return self._track(result)

        # Handle single index: v[i]
        index = self.evaluate(node.slice)

        if index.type.type_code == TypeCode.UNRESOLVED:
            # Unresolved index — validate constraint is int, return unresolved element type
            if ExprType.INT.match(index.type.type_params[0]) is None:
                raise self._type_error("Index must be an integer", node)
            if value.type.type_code == TypeCode.UNRESOLVED:
                constraint = value.type.type_params[0]
                if constraint.type_code == TypeCode.LIST and constraint.type_params:
                    return self._track(ExprValue.unresolved(constraint.type_params[0]))
                if constraint.type_code == TypeCode.STRING:
                    return self._track(ExprValue.unresolved(ExprType.STRING))
            elif value.type.type_code == TypeCode.LIST and value.type.type_params:
                return self._track(ExprValue.unresolved(value.type.type_params[0]))
            elif value.type.type_code == TypeCode.STRING:
                return self._track(ExprValue.unresolved(ExprType.STRING))
            # Fall through to __getitem__ which will short-circuit for unresolved args
            return self._track(self._call_function("__getitem__", [value, index], node=node))

        if index.type.type_code != TypeCode.INT:
            raise self._type_error("Index must be an integer", node)

        # Unresolved value with concrete index — return unresolved element type
        if value.type.type_code == TypeCode.UNRESOLVED:
            constraint = value.type.type_params[0]
            if constraint.type_code == TypeCode.LIST and constraint.type_params:
                return self._track(ExprValue.unresolved(constraint.type_params[0]))
            if constraint.type_code == TypeCode.STRING:
                return self._track(ExprValue.unresolved(ExprType.STRING))
            # Fall through to __getitem__ which will short-circuit for unresolved args
            return self._track(self._call_function("__getitem__", [value, index], node=node))

        if value.type.type_code == TypeCode.LIST:
            idx = index.item()
            lst = value.to_expr_value_list()
            if idx < 0:
                idx = len(lst) + idx
            if idx < 0 or idx >= len(lst):
                raise self._error(
                    f"Index {index.item()} out of bounds for list of length {len(lst)}", node
                )
            self._release(value, index)
            return self._track(lst[idx])

        if value.type.type_code == TypeCode.RANGE_EXPR:
            result = self._call_function("__getitem__", [value, index], node=node)
            self._release(value, index)
            return self._track(result)

        if value.type.type_code == TypeCode.STRING:
            result = self._call_function("__getitem__", [value, index], node=node)
            self._release(value, index)
            return self._track(result)

        raise self._type_error(f"Cannot subscript type {value.type}", node)
