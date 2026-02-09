# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Function library for expression evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .._types import (
    ExprType,
    TypeCode,
    _INT_OR_NULL,
    T1,
    T2,
    T3,
    _apply_implicit_coercions,
)
from .._value import ExprValue

# Import implementations from submodules
from ._comparison import (
    _eq_generic,
    _ne_generic,
    _lt_generic,
    _le_generic,
    _gt_generic,
    _ge_generic,
    _not_bool,
)
from ._arithmetic import (
    _add_int,
    _add_float,
    _add_string,
    _add_path_string,
    _add_string_range_expr,
    _add_range_expr_string,
    _sub_int,
    _sub_float,
    _mul_int,
    _mul_float,
    _mul_string,
    _mul_list,
    _truediv_int,
    _truediv_float,
    _path_join,
    _floordiv_int,
    _floordiv_float,
    _mod_int,
    _mod_float,
    _neg_int,
    _neg_float,
    _pos_int,
    _pos_float,
)
from ._math import (
    _abs_int,
    _abs_float,
    _min_int,
    _min_float,
    _max_int,
    _max_float,
    _floor_int,
    _floor_float,
    _ceil_int,
    _ceil_float,
    _round,
    _pow_int,
    _pow_float,
    _min_int3,
    _min_float3,
    _max_int3,
    _max_float3,
    _round_ndigits,
    _round_int_ndigits,
)
from ._string import (
    _len_string,
    _len_path,
    _getitem_string,
    _slice_string,
    _upper,
    _lower,
    _strip,
    _strip_chars,
    _startswith,
    _endswith,
    _replace,
    _split,
    _split_whitespace,
    _split_maxsplit,
    _rsplit,
    _rsplit_whitespace,
    _rsplit_maxsplit,
    _zfill_string,
    _zfill_int,
    _zfill_float,
    _repr_sh,
    _capitalize,
    _title,
    _lstrip,
    _lstrip_chars,
    _rstrip,
    _rstrip_chars,
    _isdigit,
    _isalpha,
    _isalnum,
    _isspace,
    _isupper,
    _islower,
    _isascii,
    _removeprefix,
    _removesuffix,
    _count,
    _find,
    _rfind,
    _index,
    _rindex,
    _join,
    _join_empty,
    _ljust,
    _rjust,
    _center,
    _re_match,
    _re_search,
    _re_findall,
    _re_replace,
    _re_escape,
    _re_split,
    _re_split_maxsplit,
    _contains_string,
    _not_contains_string,
)
from ._path import (
    _path_name,
    _path_stem,
    _path_suffix,
    _path_parent,
    _path_from_string,
    _path_from_list,
    _with_suffix,
    _path_join_path,
    _path_suffixes,
    _path_parts,
    _with_name,
    _with_stem,
    _as_posix,
    _is_absolute,
    _is_relative_to,
    _relative_to,
    _with_number_path,
    _with_number_string,
    _apply_path_mapping,
)
from ._list import (
    _any,
    _any_empty,
    _all,
    _all_empty,
    _contains,
    _not_contains,
    _len_list,
    _min_list_int,
    _min_list_float,
    _min_list_empty,
    _max_list_int,
    _max_list_float,
    _max_list_empty,
    _sum_list_int,
    _sum_list_float,
    _sum_list_empty,
    _join_paths,
    _flatten,
    _flatten_identity,
    _getitem_list,
    _slice_list,
    _range_stop,
    _range_start_stop,
    _range_start_stop_step,
    _add_list,
    _add_range_expr_list,
    _add_list_range_expr,
    _add_range_expr_range_expr,
    _sorted,
    _reversed,
    _unique,
)
from ._conversion import (
    _string_from_int,
    _string_from_float,
    _string_from_bool,
    _string_from_path,
    _string_from_null,
    _string_from_list,
    _string_identity,
    _int_identity,
    _int_from_string,
    _int_from_float,
    _float_identity,
    _float_from_string,
    _float_from_int,
    _bool_identity,
    _bool_from_null,
    _bool_from_int,
    _bool_from_float,
    _bool_from_string,
    _bool_from_path,
    _bool_from_list,
    _fail,
)
from ._range_expr import (
    _getitem_range_expr,
    _slice_range_expr,
    _len_range_expr,
    _min_range_expr,
    _max_range_expr,
    _sum_range_expr,
    _string_from_range_expr,
    _list_from_range_expr,
    _range_expr_from_string,
    _range_expr_from_list,
    _contains_range_expr,
    _not_contains_range_expr,
)
from ._repr import (
    _repr_sh_path,
    _repr_sh_list,
    _repr_cmd_string,
    _repr_cmd_list,
    _repr_py_string,
    _repr_py_int,
    _repr_py_float,
    _repr_py_bool,
    _repr_py_path,
    _repr_json_string,
    _repr_json_int,
    _repr_json_float,
    _repr_json_bool,
    _repr_json_null,
    _repr_json_path,
    _repr_py_null,
    _repr_py_list,
    _repr_json_list,
    _repr_pwsh_string,
    _repr_pwsh_int,
    _repr_pwsh_float,
    _repr_pwsh_bool,
    _repr_pwsh_path,
    _repr_pwsh_range_expr,
    _repr_pwsh_list,
    _repr_py_range_expr,
    _repr_json_range_expr,
)


@dataclass
class FunctionSignature:
    """A function signature with parameter types and return type."""

    param_types: list[ExprType]
    return_type: ExprType
    impl: Callable[..., ExprValue]

    def is_generic(self) -> bool:
        """Check if this signature uses type variables."""
        if self.return_type.is_symbolic():
            return True
        return any(pt.is_symbolic() for pt in self.param_types)


class FunctionLibrary:
    """Registry of functions available in expressions."""

    def __init__(self) -> None:
        self._functions: dict[str, list[FunctionSignature]] = {}
        self._path_mapping_rules: Optional[list] = None
        self._host_context_enabled = False
        self._register_builtins()

    @property
    def path_mapping_rules(self) -> Optional[list]:
        return self._path_mapping_rules

    @path_mapping_rules.setter
    def path_mapping_rules(self, rules: Optional[list]) -> None:
        self._path_mapping_rules = rules

    def with_host_context(
        self,
        *,
        path_mapping_rules: Optional[list] = None,
    ) -> "FunctionLibrary":
        """Enable host context functions (evaluated at runtime on worker).

        This enables functions like `apply_path_mapping` that are only
        available in `@fmtstring[host]` contexts.

        Args:
            path_mapping_rules: Path mapping rules to use for apply_path_mapping.
                Uses PathMappingRule from openjd.sessions.

        Returns:
            A new FunctionLibrary with host context enabled.
        """
        # Create a copy to avoid mutating the shared default library
        import copy

        new_lib = copy.copy(self)
        new_lib._functions = copy.copy(self._functions)
        new_lib._host_context_enabled = True
        new_lib._path_mapping_rules = path_mapping_rules
        # Register host-context-only functions
        new_lib.register(
            "apply_path_mapping", [ExprType.STRING], ExprType.PATH, _apply_path_mapping
        )
        return new_lib

    @property
    def host_context_enabled(self) -> bool:
        return self._host_context_enabled

    def register(
        self,
        name: str,
        param_types: list[ExprType],
        return_type: ExprType,
        impl: Callable[..., ExprValue],
    ) -> None:
        """Register a function signature."""
        sig = FunctionSignature(param_types, return_type, impl)
        if name not in self._functions:
            self._functions[name] = []
        self._functions[name].append(sig)

    def get_signatures(self, name: str) -> list[FunctionSignature]:
        """Get all signatures for a function name."""
        return self._functions.get(name, [])

    def get_property_type(self, value_type: ExprType, property_name: str) -> Optional[ExprType]:
        """Get the return type of a property access on a type.

        Looks up __property_{name}__ functions that accept value_type.

        Args:
            value_type: The type of the value being accessed
            property_name: The property name (e.g., "stem", "parent")

        Returns:
            The return type if the property is valid, None otherwise
        """
        func_name = f"__property_{property_name}__"
        for sig in self.get_signatures(func_name):
            if len(sig.param_types) == 1:
                bindings = sig.param_types[0].match(value_type)
                if bindings is not None:
                    return sig.return_type.substitute(bindings)
        return None

    def derive_return_types(self, name: str, arg_types: list[set[ExprType]]) -> set[ExprType]:
        """Get possible return types of a function call given argument type sets.

        Args:
            name: The function name
            arg_types: Set of possible types for each argument

        Returns:
            Set of possible return types (empty if no matching signatures)
        """
        # Step 1: If all arg sets are singletons, try exact match first
        if all(len(ts) == 1 for ts in arg_types):
            exact_types = [next(iter(ts)) for ts in arg_types]
            for sig in self.get_signatures(name):
                if len(sig.param_types) != len(exact_types):
                    continue
                bindings: dict[TypeCode, ExprType] = {}
                match = True
                for param_type, arg_type in zip(sig.param_types, exact_types):
                    result = param_type.match(arg_type)
                    if result is None:
                        match = False
                        break
                    bindings.update(result)
                if match:
                    return {sig.return_type.substitute(bindings)}

        # Step 2: Apply coercions and find all possible return types
        coerced_arg_types = [_apply_implicit_coercions(ts) for ts in arg_types]
        result_types: set[ExprType] = set()
        for sig in self.get_signatures(name):
            if len(sig.param_types) != len(coerced_arg_types):
                continue
            self._match_signature(sig, coerced_arg_types, 0, {}, result_types)
        return result_types

    def _match_signature(
        self,
        sig: FunctionSignature,
        arg_type_sets: list[set[ExprType]],
        idx: int,
        bindings: dict[TypeCode, ExprType],
        result_types: set[ExprType],
    ) -> None:
        """Recursively match signature against argument type combinations."""
        if idx == len(arg_type_sets):
            # All arguments matched
            result_types.add(sig.return_type.substitute(bindings))
            return

        param_type = sig.param_types[idx]
        for arg_type in arg_type_sets[idx]:
            match_result = param_type.match(arg_type)
            if match_result is None:
                continue
            # Check for conflicting bindings
            new_bindings = dict(bindings)
            conflict = False
            for k, v in match_result.items():
                if k in new_bindings and new_bindings[k] != v:
                    conflict = True
                    break
                new_bindings[k] = v
            if not conflict:
                self._match_signature(sig, arg_type_sets, idx + 1, new_bindings, result_types)

    def _register_builtins(self) -> None:
        """Register all built-in functions."""
        # Arithmetic operators
        self.register("__add__", [ExprType.INT, ExprType.INT], ExprType.INT, _add_int)
        self.register("__add__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _add_float)
        self.register("__add__", [ExprType.STRING, ExprType.STRING], ExprType.STRING, _add_string)
        self.register(
            "__add__",
            [ExprType.STRING, ExprType.RANGE_EXPR],
            ExprType.STRING,
            _add_string_range_expr,
        )
        self.register(
            "__add__",
            [ExprType.RANGE_EXPR, ExprType.STRING],
            ExprType.STRING,
            _add_range_expr_string,
        )
        self.register("__add__", [ExprType.PATH, ExprType.STRING], ExprType.PATH, _add_path_string)
        self.register(
            "__add__",
            [ExprType(TypeCode.LIST, [T1]), ExprType(TypeCode.LIST, [T2])],
            ExprType(TypeCode.LIST, [T3]),
            _add_list,
        )
        self.register(
            "__add__",
            [ExprType.RANGE_EXPR, ExprType(TypeCode.LIST, [T1])],
            ExprType(TypeCode.LIST, [T2]),
            _add_range_expr_list,
        )
        self.register(
            "__add__",
            [ExprType(TypeCode.LIST, [T1]), ExprType.RANGE_EXPR],
            ExprType(TypeCode.LIST, [T2]),
            _add_list_range_expr,
        )
        self.register(
            "__add__",
            [ExprType.RANGE_EXPR, ExprType.RANGE_EXPR],
            ExprType.LIST_INT,
            _add_range_expr_range_expr,
        )

        self.register("__sub__", [ExprType.INT, ExprType.INT], ExprType.INT, _sub_int)
        self.register("__sub__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _sub_float)

        self.register("__mul__", [ExprType.INT, ExprType.INT], ExprType.INT, _mul_int)
        self.register("__mul__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _mul_float)
        self.register("__mul__", [ExprType.STRING, ExprType.INT], ExprType.STRING, _mul_string)
        self.register(
            "__mul__",
            [ExprType(TypeCode.LIST, [T1]), ExprType.INT],
            ExprType(TypeCode.LIST, [T1]),
            _mul_list,
        )

        self.register("__truediv__", [ExprType.INT, ExprType.INT], ExprType.FLOAT, _truediv_int)
        self.register(
            "__truediv__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _truediv_float
        )
        self.register("__truediv__", [ExprType.PATH, ExprType.STRING], ExprType.PATH, _path_join)
        self.register("__truediv__", [ExprType.PATH, ExprType.PATH], ExprType.PATH, _path_join_path)

        self.register("__floordiv__", [ExprType.INT, ExprType.INT], ExprType.INT, _floordiv_int)
        self.register(
            "__floordiv__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.INT, _floordiv_float
        )

        self.register("__mod__", [ExprType.INT, ExprType.INT], ExprType.INT, _mod_int)
        self.register("__mod__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _mod_float)

        self.register("__neg__", [ExprType.INT], ExprType.INT, _neg_int)
        self.register("__neg__", [ExprType.FLOAT], ExprType.FLOAT, _neg_float)

        self.register("__pos__", [ExprType.INT], ExprType.INT, _pos_int)
        self.register("__pos__", [ExprType.FLOAT], ExprType.FLOAT, _pos_float)

        # Comparison operators
        self.register("__eq__", [T1, T2], ExprType.BOOL, _eq_generic)
        self.register("__ne__", [T1, T2], ExprType.BOOL, _ne_generic)
        self.register("__lt__", [T1, T2], ExprType.BOOL, _lt_generic)
        self.register("__le__", [T1, T2], ExprType.BOOL, _le_generic)
        self.register("__gt__", [T1, T2], ExprType.BOOL, _gt_generic)
        self.register("__ge__", [T1, T2], ExprType.BOOL, _ge_generic)

        # Logical operators
        self.register("__not__", [ExprType.BOOL], ExprType.BOOL, _not_bool)

        # Subscript (single index) for range_expr, lists, and strings
        self.register(
            "__getitem__", [ExprType.RANGE_EXPR, ExprType.INT], ExprType.INT, _getitem_range_expr
        )
        self.register(
            "__getitem__", [ExprType(TypeCode.LIST, [T1]), ExprType.INT], T1, _getitem_list
        )
        self.register(
            "__getitem__", [ExprType.STRING, ExprType.INT], ExprType.STRING, _getitem_string
        )

        # Slice (start:stop:step) for lists, range_expr, and strings
        self.register(
            "__getitem__",
            [ExprType(TypeCode.LIST, [T1]), _INT_OR_NULL, _INT_OR_NULL, _INT_OR_NULL],
            ExprType(TypeCode.LIST, [T1]),
            _slice_list,
        )
        self.register(
            "__getitem__",
            [ExprType.RANGE_EXPR, _INT_OR_NULL, _INT_OR_NULL, _INT_OR_NULL],
            ExprType.LIST_INT,
            _slice_range_expr,
        )
        self.register(
            "__getitem__",
            [ExprType.STRING, _INT_OR_NULL, _INT_OR_NULL, _INT_OR_NULL],
            ExprType.STRING,
            _slice_string,
        )

        # Membership test (in / not in)
        self.register("__contains__", [ExprType(TypeCode.LIST, [T1]), T1], ExprType.BOOL, _contains)
        self.register(
            "__not_contains__", [ExprType(TypeCode.LIST, [T1]), T1], ExprType.BOOL, _not_contains
        )
        self.register(
            "__contains__", [ExprType.RANGE_EXPR, ExprType.INT], ExprType.BOOL, _contains_range_expr
        )
        self.register(
            "__not_contains__",
            [ExprType.RANGE_EXPR, ExprType.INT],
            ExprType.BOOL,
            _not_contains_range_expr,
        )
        self.register(
            "__contains__", [ExprType.STRING, ExprType.STRING], ExprType.BOOL, _contains_string
        )
        self.register(
            "__not_contains__",
            [ExprType.STRING, ExprType.STRING],
            ExprType.BOOL,
            _not_contains_string,
        )

        # Length
        self.register("len", [ExprType.STRING], ExprType.INT, _len_string)
        self.register("len", [ExprType.PATH], ExprType.INT, _len_path)
        self.register("len", [ExprType.RANGE_EXPR], ExprType.INT, _len_range_expr)
        self.register("len", [ExprType(TypeCode.LIST, [T1])], ExprType.INT, _len_list)

        # Type conversions
        self.register("bool", [ExprType.BOOL], ExprType.BOOL, _bool_identity)
        self.register("bool", [ExprType.NULLTYPE], ExprType.BOOL, _bool_from_null)
        self.register("bool", [ExprType.INT], ExprType.BOOL, _bool_from_int)
        self.register("bool", [ExprType.FLOAT], ExprType.BOOL, _bool_from_float)
        self.register("bool", [ExprType.STRING], ExprType.BOOL, _bool_from_string)
        self.register("bool", [ExprType.PATH], ExprType.BOOL, _bool_from_path)
        self.register("bool", [ExprType(TypeCode.LIST, [T1])], ExprType.BOOL, _bool_from_list)

        # Validation function
        self.register("fail", [ExprType.STRING], ExprType.NORETURN, _fail)

        self.register("string", [ExprType.INT], ExprType.STRING, _string_from_int)
        self.register("string", [ExprType.FLOAT], ExprType.STRING, _string_from_float)
        self.register("string", [ExprType.BOOL], ExprType.STRING, _string_from_bool)
        self.register("string", [ExprType.STRING], ExprType.STRING, _string_identity)
        self.register("string", [ExprType.PATH], ExprType.STRING, _string_from_path)
        self.register("string", [ExprType.NULLTYPE], ExprType.STRING, _string_from_null)
        self.register("string", [ExprType.RANGE_EXPR], ExprType.STRING, _string_from_range_expr)
        self.register("string", [ExprType(TypeCode.LIST, [T1])], ExprType.STRING, _string_from_list)

        self.register("list", [ExprType.RANGE_EXPR], ExprType.LIST_INT, _list_from_range_expr)

        self.register("int", [ExprType.INT], ExprType.INT, _int_identity)
        self.register("int", [ExprType.STRING], ExprType.INT, _int_from_string)
        self.register("int", [ExprType.FLOAT], ExprType.INT, _int_from_float)

        self.register("float", [ExprType.FLOAT], ExprType.FLOAT, _float_identity)
        self.register("float", [ExprType.STRING], ExprType.FLOAT, _float_from_string)
        self.register("float", [ExprType.INT], ExprType.FLOAT, _float_from_int)

        # Min/max (2 args)
        self.register("min", [ExprType.INT, ExprType.INT], ExprType.INT, _min_int)
        self.register("min", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _min_float)
        self.register("min", [ExprType.LIST_INT], ExprType.INT, _min_list_int)
        self.register("min", [ExprType.LIST_FLOAT], ExprType.FLOAT, _min_list_float)
        self.register("min", [ExprType.EMPTY_LIST], ExprType.NORETURN, _min_list_empty)
        self.register("min", [ExprType.RANGE_EXPR], ExprType.INT, _min_range_expr)

        self.register("max", [ExprType.INT, ExprType.INT], ExprType.INT, _max_int)
        self.register("max", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _max_float)
        self.register("max", [ExprType.LIST_INT], ExprType.INT, _max_list_int)
        self.register("max", [ExprType.LIST_FLOAT], ExprType.FLOAT, _max_list_float)
        self.register("max", [ExprType.EMPTY_LIST], ExprType.NORETURN, _max_list_empty)
        self.register("max", [ExprType.RANGE_EXPR], ExprType.INT, _max_range_expr)

        # Min/max (3 args)
        self.register("min", [ExprType.INT, ExprType.INT, ExprType.INT], ExprType.INT, _min_int3)
        self.register(
            "min", [ExprType.FLOAT, ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _min_float3
        )
        self.register("max", [ExprType.INT, ExprType.INT, ExprType.INT], ExprType.INT, _max_int3)
        self.register(
            "max", [ExprType.FLOAT, ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _max_float3
        )

        # Sum
        self.register("sum", [ExprType.LIST_INT], ExprType.INT, _sum_list_int)
        self.register("sum", [ExprType.LIST_FLOAT], ExprType.FLOAT, _sum_list_float)
        self.register("sum", [ExprType.EMPTY_LIST], ExprType.INT, _sum_list_empty)
        self.register("sum", [ExprType.RANGE_EXPR], ExprType.INT, _sum_range_expr)

        # Flatten
        self.register(
            "flatten",
            [ExprType(TypeCode.LIST, [ExprType(TypeCode.LIST, [T1])])],
            ExprType(TypeCode.LIST, [T1]),
            _flatten,
        )
        self.register(
            "flatten",
            [ExprType(TypeCode.LIST, [T1])],
            ExprType(TypeCode.LIST, [T1]),
            _flatten_identity,
        )

        # Sorted and reversed
        self.register(
            "sorted",
            [ExprType(TypeCode.LIST, [T1])],
            ExprType(TypeCode.LIST, [T1]),
            _sorted,
        )
        self.register(
            "reversed",
            [ExprType(TypeCode.LIST, [T1])],
            ExprType(TypeCode.LIST, [T1]),
            _reversed,
        )
        self.register(
            "unique",
            [ExprType(TypeCode.LIST, [T1])],
            ExprType(TypeCode.LIST, [T1]),
            _unique,
        )

        # Range
        self.register("range", [ExprType.INT], ExprType.LIST_INT, _range_stop)
        self.register("range", [ExprType.INT, ExprType.INT], ExprType.LIST_INT, _range_start_stop)
        self.register(
            "range",
            [ExprType.INT, ExprType.INT, ExprType.INT],
            ExprType.LIST_INT,
            _range_start_stop_step,
        )

        # Abs
        self.register("abs", [ExprType.INT], ExprType.INT, _abs_int)
        self.register("abs", [ExprType.FLOAT], ExprType.FLOAT, _abs_float)

        # Rounding
        self.register("floor", [ExprType.INT], ExprType.INT, _floor_int)
        self.register("floor", [ExprType.FLOAT], ExprType.INT, _floor_float)
        self.register("ceil", [ExprType.INT], ExprType.INT, _ceil_int)
        self.register("ceil", [ExprType.FLOAT], ExprType.INT, _ceil_float)
        self.register("round", [ExprType.FLOAT], ExprType.INT, _round)
        self.register(
            "round",
            [ExprType.FLOAT, ExprType.INT],
            ExprType(TypeCode.UNION, [ExprType.FLOAT, ExprType.INT]),
            _round_ndigits,
        )
        self.register("round", [ExprType.INT, ExprType.INT], ExprType.INT, _round_int_ndigits)

        # Power operator (int**int returns int for non-negative exponent, float for negative)
        self.register("__pow__", [ExprType.INT, ExprType.INT], ExprType("float | int"), _pow_int)
        self.register("__pow__", [ExprType.FLOAT, ExprType.FLOAT], ExprType.FLOAT, _pow_float)

        # String functions
        self.register("upper", [ExprType.STRING], ExprType.STRING, _upper)
        self.register("lower", [ExprType.STRING], ExprType.STRING, _lower)
        self.register("strip", [ExprType.STRING], ExprType.STRING, _strip)
        self.register("strip", [ExprType.STRING, ExprType.STRING], ExprType.STRING, _strip_chars)
        self.register("lstrip", [ExprType.STRING], ExprType.STRING, _lstrip)
        self.register("lstrip", [ExprType.STRING, ExprType.STRING], ExprType.STRING, _lstrip_chars)
        self.register("rstrip", [ExprType.STRING], ExprType.STRING, _rstrip)
        self.register("rstrip", [ExprType.STRING, ExprType.STRING], ExprType.STRING, _rstrip_chars)
        self.register("isdigit", [ExprType.STRING], ExprType.BOOL, _isdigit)
        self.register("isalpha", [ExprType.STRING], ExprType.BOOL, _isalpha)
        self.register("isalnum", [ExprType.STRING], ExprType.BOOL, _isalnum)
        self.register("isspace", [ExprType.STRING], ExprType.BOOL, _isspace)
        self.register("isupper", [ExprType.STRING], ExprType.BOOL, _isupper)
        self.register("islower", [ExprType.STRING], ExprType.BOOL, _islower)
        self.register("isascii", [ExprType.STRING], ExprType.BOOL, _isascii)
        self.register(
            "removeprefix", [ExprType.STRING, ExprType.STRING], ExprType.STRING, _removeprefix
        )
        self.register(
            "removesuffix", [ExprType.STRING, ExprType.STRING], ExprType.STRING, _removesuffix
        )
        self.register("capitalize", [ExprType.STRING], ExprType.STRING, _capitalize)
        self.register("title", [ExprType.STRING], ExprType.STRING, _title)
        self.register("startswith", [ExprType.STRING, ExprType.STRING], ExprType.BOOL, _startswith)
        self.register("endswith", [ExprType.STRING, ExprType.STRING], ExprType.BOOL, _endswith)
        self.register(
            "replace",
            [ExprType.STRING, ExprType.STRING, ExprType.STRING],
            ExprType.STRING,
            _replace,
        )
        self.register("split", [ExprType.STRING], ExprType.LIST_STRING, _split_whitespace)
        self.register("split", [ExprType.STRING, ExprType.STRING], ExprType.LIST_STRING, _split)
        self.register(
            "split",
            [ExprType.STRING, ExprType.STRING, ExprType.INT],
            ExprType.LIST_STRING,
            _split_maxsplit,
        )
        self.register("rsplit", [ExprType.STRING], ExprType.LIST_STRING, _rsplit_whitespace)
        self.register("rsplit", [ExprType.STRING, ExprType.STRING], ExprType.LIST_STRING, _rsplit)
        self.register(
            "rsplit",
            [ExprType.STRING, ExprType.STRING, ExprType.INT],
            ExprType.LIST_STRING,
            _rsplit_maxsplit,
        )
        self.register("zfill", [ExprType.STRING, ExprType.INT], ExprType.STRING, _zfill_string)
        self.register("zfill", [ExprType.INT, ExprType.INT], ExprType.STRING, _zfill_int)
        self.register("zfill", [ExprType.FLOAT, ExprType.INT], ExprType.STRING, _zfill_float)
        self.register("count", [ExprType.STRING, ExprType.STRING], ExprType.INT, _count)
        self.register("find", [ExprType.STRING, ExprType.STRING], ExprType.INT, _find)
        self.register("rfind", [ExprType.STRING, ExprType.STRING], ExprType.INT, _rfind)
        self.register("index", [ExprType.STRING, ExprType.STRING], ExprType.INT, _index)
        self.register("rindex", [ExprType.STRING, ExprType.STRING], ExprType.INT, _rindex)
        self.register("join", [ExprType.EMPTY_LIST, ExprType.STRING], ExprType.STRING, _join_empty)
        self.register("join", [ExprType.LIST_STRING, ExprType.STRING], ExprType.STRING, _join)
        self.register("join", [ExprType.LIST_PATH, ExprType.STRING], ExprType.STRING, _join_paths)
        self.register("ljust", [ExprType.STRING, ExprType.INT], ExprType.STRING, _ljust)
        self.register("rjust", [ExprType.STRING, ExprType.INT], ExprType.STRING, _rjust)
        self.register("center", [ExprType.STRING, ExprType.INT], ExprType.STRING, _center)

        # Regular expression functions
        self.register(
            "re_match", [ExprType.STRING, ExprType.STRING], ExprType("list[string]?"), _re_match
        )
        self.register(
            "re_search", [ExprType.STRING, ExprType.STRING], ExprType("list[string]?"), _re_search
        )
        self.register(
            "re_findall",
            [ExprType.STRING, ExprType.STRING],
            ExprType("list[string] | list[list[string]]"),
            _re_findall,
        )
        self.register(
            "re_replace",
            [ExprType.STRING, ExprType.STRING, ExprType.STRING],
            ExprType.STRING,
            _re_replace,
        )
        self.register("re_escape", [ExprType.STRING], ExprType.STRING, _re_escape)
        self.register(
            "re_split", [ExprType.STRING, ExprType.STRING], ExprType.LIST_STRING, _re_split
        )
        self.register(
            "re_split",
            [ExprType.STRING, ExprType.STRING, ExprType.INT],
            ExprType.LIST_STRING,
            _re_split_maxsplit,
        )

        # Path functions
        self.register("path", [ExprType.STRING], ExprType.PATH, _path_from_string)
        self.register("path", [ExprType.LIST_STRING], ExprType.PATH, _path_from_list)

        # Path property access (P.name, P.stem, etc.)
        self.register("__property_name__", [ExprType.PATH], ExprType.STRING, _path_name)
        self.register("__property_stem__", [ExprType.PATH], ExprType.STRING, _path_stem)
        self.register("__property_suffix__", [ExprType.PATH], ExprType.STRING, _path_suffix)
        self.register(
            "__property_suffixes__", [ExprType.PATH], ExprType.LIST_STRING, _path_suffixes
        )
        self.register("__property_parent__", [ExprType.PATH], ExprType.PATH, _path_parent)
        self.register("__property_parts__", [ExprType.PATH], ExprType.LIST_STRING, _path_parts)
        self.register("with_suffix", [ExprType.PATH, ExprType.STRING], ExprType.PATH, _with_suffix)
        self.register("with_name", [ExprType.PATH, ExprType.STRING], ExprType.PATH, _with_name)
        self.register("with_stem", [ExprType.PATH, ExprType.STRING], ExprType.PATH, _with_stem)
        self.register(
            "with_number", [ExprType.PATH, ExprType.INT], ExprType.PATH, _with_number_path
        )
        self.register(
            "with_number", [ExprType.STRING, ExprType.INT], ExprType.STRING, _with_number_string
        )
        self.register("as_posix", [ExprType.PATH], ExprType.STRING, _as_posix)
        self.register("is_absolute", [ExprType.PATH], ExprType.BOOL, _is_absolute)
        self.register(
            "is_relative_to", [ExprType.PATH, ExprType.PATH], ExprType.BOOL, _is_relative_to
        )
        self.register("relative_to", [ExprType.PATH, ExprType.PATH], ExprType.PATH, _relative_to)

        # Rangeexpr
        self.register("range_expr", [ExprType.STRING], ExprType.RANGE_EXPR, _range_expr_from_string)
        self.register("range_expr", [ExprType.LIST_INT], ExprType.RANGE_EXPR, _range_expr_from_list)

        # Boolean aggregation
        # Empty list overloads (list[?]) - any([]) is False, all([]) is True
        self.register("any", [ExprType.EMPTY_LIST], ExprType.BOOL, _any_empty)
        self.register("all", [ExprType.EMPTY_LIST], ExprType.BOOL, _all_empty)
        self.register("any", [ExprType.LIST_BOOL], ExprType.BOOL, _any)
        self.register("all", [ExprType.LIST_BOOL], ExprType.BOOL, _all)

        # Repr functions
        self.register("repr_sh", [ExprType.STRING], ExprType.STRING, _repr_sh)
        self.register("repr_sh", [ExprType.PATH], ExprType.STRING, _repr_sh_path)
        self.register("repr_sh", [ExprType.LIST_STRING], ExprType.STRING, _repr_sh_list)
        self.register("repr_sh", [ExprType.LIST_PATH], ExprType.STRING, _repr_sh_list)
        self.register("repr_cmd", [ExprType.STRING], ExprType.STRING, _repr_cmd_string)
        self.register("repr_cmd", [ExprType.LIST_STRING], ExprType.STRING, _repr_cmd_list)
        self.register("repr_pwsh", [ExprType.STRING], ExprType.STRING, _repr_pwsh_string)
        self.register("repr_pwsh", [ExprType.INT], ExprType.STRING, _repr_pwsh_int)
        self.register("repr_pwsh", [ExprType.FLOAT], ExprType.STRING, _repr_pwsh_float)
        self.register("repr_pwsh", [ExprType.BOOL], ExprType.STRING, _repr_pwsh_bool)
        self.register("repr_pwsh", [ExprType.PATH], ExprType.STRING, _repr_pwsh_path)
        self.register("repr_pwsh", [ExprType.RANGE_EXPR], ExprType.STRING, _repr_pwsh_range_expr)
        self.register(
            "repr_pwsh", [ExprType(TypeCode.LIST, [T1])], ExprType.STRING, _repr_pwsh_list
        )
        self.register("repr_py", [ExprType.STRING], ExprType.STRING, _repr_py_string)
        self.register("repr_py", [ExprType.INT], ExprType.STRING, _repr_py_int)
        self.register("repr_py", [ExprType.FLOAT], ExprType.STRING, _repr_py_float)
        self.register("repr_py", [ExprType.BOOL], ExprType.STRING, _repr_py_bool)
        self.register("repr_py", [ExprType.PATH], ExprType.STRING, _repr_py_path)
        self.register("repr_py", [ExprType.NULLTYPE], ExprType.STRING, _repr_py_null)
        self.register("repr_py", [ExprType.RANGE_EXPR], ExprType.STRING, _repr_py_range_expr)
        self.register("repr_py", [ExprType(TypeCode.LIST, [T1])], ExprType.STRING, _repr_py_list)
        self.register("repr_json", [ExprType.STRING], ExprType.STRING, _repr_json_string)
        self.register("repr_json", [ExprType.INT], ExprType.STRING, _repr_json_int)
        self.register("repr_json", [ExprType.FLOAT], ExprType.STRING, _repr_json_float)
        self.register("repr_json", [ExprType.BOOL], ExprType.STRING, _repr_json_bool)
        self.register("repr_json", [ExprType.NULLTYPE], ExprType.STRING, _repr_json_null)
        self.register("repr_json", [ExprType.PATH], ExprType.STRING, _repr_json_path)
        self.register("repr_json", [ExprType.RANGE_EXPR], ExprType.STRING, _repr_json_range_expr)
        self.register(
            "repr_json", [ExprType(TypeCode.LIST, [T1])], ExprType.STRING, _repr_json_list
        )


# Default function library instance
_default_library: Optional[FunctionLibrary] = None


def get_default_library() -> FunctionLibrary:
    """Get the default function library."""
    global _default_library
    if _default_library is None:
        _default_library = FunctionLibrary()
    return _default_library
