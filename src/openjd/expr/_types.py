# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Expression type system (RFC 0005)."""

from __future__ import annotations

from enum import IntEnum
from typing import Optional


class TypeCode(IntEnum):
    """Type codes for expression values."""

    # Primitive types
    NULLTYPE = 0
    BOOL = 1
    INT = 2
    FLOAT = 3
    STRING = 4
    PATH = 5

    # Compound types
    LIST = 6
    RANGE_EXPR = 7

    # Abstract types (not concrete)
    ANY = 8
    UNION = 9

    # Bottom type (for functions that never return)
    NORETURN = 10

    # Unresolved type (value unresolved, but satisfies constraint T)
    UNRESOLVED = 11

    # Type variables for generic signatures
    TYPEVAR_T = 100
    TYPEVAR_T1 = 101
    TYPEVAR_T2 = 102
    TYPEVAR_T3 = 103


class ExprType:
    """Represents a type in the expression language.

    Can be constructed from a string:
        ExprType("int")
        ExprType("string")
        ExprType("list[int]")
        ExprType("list[list[int]]")
        ExprType("int?")

    Or from TypeCode:
        ExprType(TypeCode.INT)
        ExprType(TypeCode.LIST, [ExprType.INT])
    """

    __slots__ = ("type_code", "type_params")

    type_code: "TypeCode"
    type_params: list["ExprType"]

    # Type constants (initialized after class definition)
    BOOL: "ExprType"
    INT: "ExprType"
    FLOAT: "ExprType"
    STRING: "ExprType"
    PATH: "ExprType"
    RANGE_EXPR: "ExprType"
    NULLTYPE: "ExprType"
    NORETURN: "ExprType"
    LIST_INT: "ExprType"
    LIST_FLOAT: "ExprType"
    LIST_STRING: "ExprType"
    LIST_PATH: "ExprType"
    LIST_BOOL: "ExprType"
    LIST_LIST_INT: "ExprType"
    EMPTY_LIST: "ExprType"

    # Map type names to TypeCode
    _NAME_TO_CODE: dict[str, "TypeCode"] = {}

    def __new__(
        cls, type_code_or_str: "TypeCode | str", type_params: Optional[list["ExprType"]] = None
    ):
        if isinstance(type_code_or_str, str):
            return cls._parse(type_code_or_str)
        # Normalize unions (may hoist unresolved)
        if type_code_or_str == TypeCode.UNION and type_params:
            return cls._normalize_union(type_params)
        # Normalize: list[unresolved[T]] -> unresolved[list[T]]
        if (
            type_code_or_str == TypeCode.LIST
            and type_params
            and len(type_params) == 1
            and type_params[0].type_code == TypeCode.UNRESOLVED
        ):
            inner_list = cls._make(TypeCode.LIST, [type_params[0].type_params[0]])
            return cls._make(TypeCode.UNRESOLVED, [inner_list])
        # Normalize: unresolved[unresolved[T]] -> unresolved[T]
        if (
            type_code_or_str == TypeCode.UNRESOLVED
            and type_params
            and len(type_params) == 1
            and type_params[0].type_code == TypeCode.UNRESOLVED
        ):
            return cls._make(TypeCode.UNRESOLVED, type_params[0].type_params)
        instance = object.__new__(cls)
        return instance

    def __init__(
        self, type_code_or_str: "TypeCode | str", type_params: Optional[list["ExprType"]] = None
    ):
        # When __new__ returns an already-initialized object (from _parse, _normalize_union,
        # or _make), Python still calls __init__ with the original arguments. Detect this by
        # checking whether type_code was already set and skip re-initialization.
        if hasattr(self, "type_code"):
            return
        self.type_code = type_code_or_str  # type: ignore[assignment]  # str case handled by __new__
        self.type_params = type_params or []
        if self.type_code == TypeCode.UNRESOLVED and len(self.type_params) != 1:
            raise ValueError("UNRESOLVED type requires exactly one type parameter (the constraint)")

    @classmethod
    def _normalize_union(cls, types: list["ExprType"]) -> "ExprType":
        """Normalize a union: flatten, deduplicate, handle ANY absorption, collapse noreturn, hoist unresolved, unwrap singletons."""
        members: set[ExprType] = set()
        for t in types:
            if t.type_code == TypeCode.ANY:
                # ANY absorbs everything
                return cls._make(TypeCode.ANY, [])
            if t.type_code == TypeCode.NORETURN:
                # noreturn collapses to nothing in unions (T | noreturn -> T)
                continue
            if t.type_code == TypeCode.UNION:
                # Flatten nested unions
                members.update(t.type_params)
            else:
                members.add(t)

        # Hoist unresolved: T | unresolved[S] -> unresolved[T | S]
        unresolved_constraints: list[ExprType] = []
        non_unresolved: set[ExprType] = set()
        for m in members:
            if m.type_code == TypeCode.UNRESOLVED:
                unresolved_constraints.append(m.type_params[0])
            else:
                non_unresolved.add(m)
        if unresolved_constraints:
            # Merge all constraints and non-unresolved members into one union constraint
            all_parts = list(non_unresolved) + unresolved_constraints
            inner = cls(TypeCode.UNION, all_parts)
            return cls(TypeCode.UNRESOLVED, [inner])

        # Single element: unwrap
        if len(members) == 1:
            return next(iter(members))
        # Empty union (all were noreturn): return noreturn
        if not members:
            return cls._make(TypeCode.NORETURN, [])
        # Create union with sorted params for consistent equality/hashing
        return cls._make(TypeCode.UNION, sorted(members, key=lambda t: str(t)))

    @classmethod
    def _make(cls, type_code: "TypeCode", type_params: list["ExprType"]) -> "ExprType":
        """Create an ExprType without normalization (internal use)."""
        instance = object.__new__(cls)
        instance.type_code = type_code  # type: ignore[assignment]
        instance.type_params = type_params
        return instance

    @classmethod
    def _split_union(cls, s: str) -> list[str]:
        """Split on ' | ' only when not inside brackets."""
        parts = []
        current = []
        depth = 0
        i = 0
        while i < len(s):
            if s[i] == "[":
                depth += 1
                current.append(s[i])
            elif s[i] == "]":
                depth -= 1
                current.append(s[i])
            elif depth == 0 and s[i : i + 3] == " | ":
                parts.append("".join(current))
                current = []
                i += 3
                continue
            else:
                current.append(s[i])
            i += 1
        parts.append("".join(current))
        return parts

    @classmethod
    def _parse(cls, s: str) -> "ExprType":
        """Parse a type string like 'int', 'list[string]', 'int?', 'int | string'."""
        # Union type: A | B | C (only split on | outside brackets)
        parts = cls._split_union(s)
        if len(parts) > 1:
            return cls(TypeCode.UNION, [cls._parse(p) for p in parts])

        # Base type - return constant if available (check before optional to handle 'nulltype')
        code = cls._NAME_TO_CODE.get(s)
        if code is not None:
            return getattr(cls, code.name, None) or cls(code)

        # Optional type: T? -> T | null (union)
        if s.endswith("?"):
            inner = cls._parse(s[:-1])
            return cls(TypeCode.UNION, [inner, ExprType(TypeCode.NULLTYPE)])

        # List type: list[T]
        if s.startswith("list[") and s.endswith("]"):
            inner = cls._parse(s[5:-1])
            return cls(TypeCode.LIST, [inner])

        # Unresolved type: unresolved or unresolved[T]
        if s == "unresolved":
            return cls(TypeCode.UNRESOLVED, [ExprType(TypeCode.ANY)])
        if s.startswith("unresolved[") and s.endswith("]"):
            inner = cls._parse(s[11:-1])
            return cls(TypeCode.UNRESOLVED, [inner])

        raise ValueError(f"Unknown type string: {s}")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExprType):
            return NotImplemented
        return self.type_code == other.type_code and self.type_params == other.type_params

    def __hash__(self) -> int:
        return hash((self.type_code, tuple(self.type_params)))

    def __str__(self) -> str:
        if self.type_code == TypeCode.NULLTYPE:
            return "nulltype"
        if self.type_code == TypeCode.NORETURN:
            return "noreturn"
        if self.type_code == TypeCode.LIST:
            elem = self.type_params[0] if self.type_params else "nulltype"
            return f"list[{elem}]"
        if self.type_code == TypeCode.UNRESOLVED:
            constraint = self.type_params[0]
            if constraint.type_code == TypeCode.ANY:
                return "unresolved"
            return f"unresolved[{constraint}]"
        if self.type_code == TypeCode.ANY:
            return "any"
        if self.type_code == TypeCode.UNION:
            # Special case: T | ? displays as T?
            non_null = [t for t in self.type_params if t.type_code != TypeCode.NULLTYPE]
            has_null = len(non_null) < len(self.type_params)
            if has_null and len(non_null) == 1:
                return f"{non_null[0]}?"
            # General case: sorted alphabetically, null at end as ?
            parts = [str(t) for t in non_null]
            if has_null:
                parts.append("nulltype")
            return " | ".join(parts)
        if self.type_code == TypeCode.TYPEVAR_T:
            return "T"
        if self.type_code == TypeCode.TYPEVAR_T1:
            return "T1"
        if self.type_code == TypeCode.TYPEVAR_T2:
            return "T2"
        if self.type_code == TypeCode.TYPEVAR_T3:
            return "T3"
        return self.type_code.name.lower()

    def __repr__(self) -> str:
        return f'ExprType("{self}")'

    def is_symbolic(self) -> bool:
        """Check if this type contains any type variables."""
        if self.type_code in (
            TypeCode.TYPEVAR_T,
            TypeCode.TYPEVAR_T1,
            TypeCode.TYPEVAR_T2,
            TypeCode.TYPEVAR_T3,
        ):
            return True
        return any(p.is_symbolic() for p in self.type_params)

    def is_concrete(self) -> bool:
        """Check if this is a single specific type (not symbolic, not ANY, not UNION, not UNKNOWN)."""
        if self.type_code in (TypeCode.ANY, TypeCode.UNION, TypeCode.UNRESOLVED):
            return False
        if self.type_code in (
            TypeCode.TYPEVAR_T,
            TypeCode.TYPEVAR_T1,
            TypeCode.TYPEVAR_T2,
            TypeCode.TYPEVAR_T3,
        ):
            return False
        return all(p.is_concrete() for p in self.type_params)

    def substitute(self, bindings: dict[TypeCode, ExprType]) -> ExprType:
        """Substitute type variables with concrete types."""
        if self.type_code in bindings:
            return bindings[self.type_code]
        if not self.type_params:
            return self
        new_params = [p.substitute(bindings) for p in self.type_params]
        return ExprType(self.type_code, new_params)

    def match(self, concrete: ExprType) -> Optional[dict[TypeCode, ExprType]]:
        """Try to match this (possibly symbolic) type against a concrete type.

        Returns a dict of type variable bindings if successful, None if no match.
        """
        if self.type_code in (
            TypeCode.TYPEVAR_T,
            TypeCode.TYPEVAR_T1,
            TypeCode.TYPEVAR_T2,
            TypeCode.TYPEVAR_T3,
        ):
            return {self.type_code: concrete}
        if concrete.type_code in (
            TypeCode.TYPEVAR_T,
            TypeCode.TYPEVAR_T1,
            TypeCode.TYPEVAR_T2,
            TypeCode.TYPEVAR_T3,
        ):
            return {concrete.type_code: self}

        # ANY matches anything
        if self.type_code == TypeCode.ANY:
            return {}
        if concrete.type_code == TypeCode.ANY:
            return {}

        # UNKNOWN[T] matches anything that T matches
        if self.type_code == TypeCode.UNRESOLVED:
            return self.type_params[0].match(concrete)
        if concrete.type_code == TypeCode.UNRESOLVED:
            return self.match(concrete.type_params[0])

        # UNION: matches if any member matches
        if self.type_code == TypeCode.UNION and concrete.type_code == TypeCode.UNION:
            # Fast path: set intersection for non-symbolic types
            if not self.is_symbolic() and not concrete.is_symbolic():
                self_set = set(self.type_params)
                concrete_set = set(concrete.type_params)
                if self_set & concrete_set:
                    return {}
                return None
            # Pairwise matching for symbolic types
            for s in self.type_params:
                for c in concrete.type_params:
                    result = s.match(c)
                    if result is not None:
                        return result
            return None
        if self.type_code == TypeCode.UNION:
            for member in self.type_params:
                result = member.match(concrete)
                if result is not None:
                    return result
            return None
        if concrete.type_code == TypeCode.UNION:
            for member in concrete.type_params:
                result = self.match(member)
                if result is not None:
                    return result
            return None

        if self.type_code != concrete.type_code:
            return None
        if len(self.type_params) != len(concrete.type_params):
            return None
        bindings: dict[TypeCode, ExprType] = {}
        for sp, cp in zip(self.type_params, concrete.type_params):
            sub_bindings = sp.match(cp)
            if sub_bindings is None:
                return None
            # Check for conflicting bindings
            for k, v in sub_bindings.items():
                if k in bindings and bindings[k] != v:
                    return None
                bindings[k] = v
        return bindings


# Initialize name to code mapping
ExprType._NAME_TO_CODE = {
    "bool": TypeCode.BOOL,
    "int": TypeCode.INT,
    "float": TypeCode.FLOAT,
    "string": TypeCode.STRING,
    "path": TypeCode.PATH,
    "range_expr": TypeCode.RANGE_EXPR,
    "nulltype": TypeCode.NULLTYPE,
    "noreturn": TypeCode.NORETURN,
    "any": TypeCode.ANY,
}

# Initialize type constants as class attributes
ExprType.BOOL = ExprType(TypeCode.BOOL)
ExprType.INT = ExprType(TypeCode.INT)
ExprType.FLOAT = ExprType(TypeCode.FLOAT)
ExprType.STRING = ExprType(TypeCode.STRING)
ExprType.PATH = ExprType(TypeCode.PATH)
ExprType.RANGE_EXPR = ExprType(TypeCode.RANGE_EXPR)
ExprType.NULLTYPE = ExprType(TypeCode.NULLTYPE)
ExprType.NORETURN = ExprType(TypeCode.NORETURN)
ExprType.LIST_INT = ExprType(TypeCode.LIST, [ExprType.INT])
ExprType.LIST_FLOAT = ExprType(TypeCode.LIST, [ExprType.FLOAT])
ExprType.LIST_STRING = ExprType(TypeCode.LIST, [ExprType.STRING])
ExprType.LIST_PATH = ExprType(TypeCode.LIST, [ExprType.PATH])
ExprType.LIST_BOOL = ExprType(TypeCode.LIST, [ExprType.BOOL])
ExprType.LIST_LIST_INT = ExprType(TypeCode.LIST, [ExprType.LIST_INT])
ExprType.EMPTY_LIST = ExprType(TypeCode.LIST, [ExprType.NULLTYPE])

# Internal: optional type for slice parameters (int | null)
_INT_OR_NULL = ExprType(TypeCode.UNION, [ExprType.INT, ExprType.NULLTYPE])

# Type variables (internal use for generic signatures)
T = ExprType(TypeCode.TYPEVAR_T)
T1 = ExprType(TypeCode.TYPEVAR_T1)
T2 = ExprType(TypeCode.TYPEVAR_T2)
T3 = ExprType(TypeCode.TYPEVAR_T3)

# Implicit coercion rules: type -> set of types it can coerce to
_IMPLICIT_COERCIONS: dict[TypeCode, set[TypeCode]] = {
    TypeCode.INT: {TypeCode.FLOAT},
    TypeCode.PATH: {TypeCode.STRING},
}


def _apply_implicit_coercions(types: set[ExprType]) -> set[ExprType]:
    """Expand a set of types to include all types they can implicitly coerce to.

    For example, {INT} -> {INT, FLOAT} because int can coerce to float.
    """
    result = set(types)
    for t in types:
        coercions = _IMPLICIT_COERCIONS.get(t.type_code)
        if coercions:
            for target_code in coercions:
                result.add(ExprType(target_code))
    return result
