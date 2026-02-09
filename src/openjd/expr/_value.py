# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Expression value representation (RFC 0005)."""

from __future__ import annotations

from decimal import Decimal
from math import isinf, isnan, copysign
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Optional

from ._types import ExprType, TypeCode
from ._errors import ExpressionTypeError
from ._path_mapping import PathFormat
from ._range_expr import RangeExpr
from ._uri_path import is_uri


class ExprValue:
    """Holds a value during expression evaluation."""

    __slots__ = (
        "type",
        "is_null",
        "_bool_value",
        "_int_value",
        "_float_value",
        "_string_value",
        "_list_value",
        "_range_expr_value",
        "_path_format",
    )

    type: "ExprType"
    is_null: bool
    _bool_value: Optional[bool]
    _int_value: Optional[int]
    _float_value: Optional[float]
    _string_value: Optional[str]
    _list_value: Optional[list["ExprValue"]]
    _range_expr_value: Any
    _path_format: Any  # Optional[PathFormat], using Any to avoid circular import

    def __new__(
        cls,
        value: Any = None,
        *,
        type: Optional["ExprType | str"] = None,
        evaluator: Any = None,
        path_format: Any = None,
    ) -> "ExprValue":
        # Construct from Python value, optionally coercing to specified type
        if isinstance(type, str):
            type = ExprType(type)
        return cls._from_python(value, type, evaluator=evaluator, path_format=path_format)

    def __init__(
        self,
        value: Any = None,
        *,
        type: Optional["ExprType | str"] = None,
        evaluator: Any = None,
        path_format: Any = None,
    ):
        pass  # All initialization done in _from_python via _create

    @classmethod
    def _create(
        cls,
        type: "ExprType",
        *,
        is_null: bool = False,
        bool_value: Optional[bool] = None,
        int_value: Optional[int] = None,
        float_value: Optional[float] = None,
        string_value: Optional[str] = None,
        list_value: Optional[list["ExprValue"]] = None,
        range_expr_value: Any = None,
        path_format: Any = None,
    ) -> "ExprValue":
        """Internal constructor for creating ExprValue with explicit type and value."""
        if not type.is_concrete() and type.type_code != TypeCode.UNRESOLVED:
            raise ExpressionTypeError(f"ExprValue must have concrete type, got: {type}")
        if type.type_code == TypeCode.PATH and path_format is None and not is_null:
            raise ExpressionTypeError("PATH ExprValue requires path_format to be set")
        instance: ExprValue = object.__new__(cls)
        instance.type = type  # type: ignore[attr-defined]
        instance.is_null = is_null  # type: ignore[attr-defined]
        instance._bool_value = bool_value  # type: ignore[attr-defined]
        instance._int_value = int_value  # type: ignore[attr-defined]
        # Validate int64 range
        if int_value is not None and (
            int_value < -9223372036854775808 or int_value > 9223372036854775807
        ):
            from ._errors import ExpressionError

            raise ExpressionError("Integer overflow: result is outside the 64-bit signed range")
        # Sanitize float: reject nan/inf, normalize -0.0 to 0.0
        if float_value is not None:
            if isnan(float_value):
                from ._errors import ExpressionError

                raise ExpressionError("Float operation produced NaN")
            if isinf(float_value):
                from ._errors import ExpressionError

                raise ExpressionError("Float operation produced infinity")
            if float_value == 0.0 and copysign(1.0, float_value) < 0:
                float_value = 0.0
                string_value = None  # Clear pass-through for normalized value
        instance._float_value = float_value  # type: ignore[attr-defined]
        instance._string_value = string_value  # type: ignore[attr-defined]
        instance._list_value = list_value  # type: ignore[attr-defined]
        instance._range_expr_value = range_expr_value  # type: ignore[attr-defined]
        instance._path_format = path_format  # type: ignore[attr-defined]
        return instance

    @classmethod
    def _from_python(
        cls,
        value: Any,
        target_type: Optional[ExprType] = None,
        *,
        evaluator: Any = None,
        path_format: Any = None,
    ) -> "ExprValue":
        """Convert a Python value to an ExprValue, optionally coercing to target_type."""
        # If target type specified, coerce to that type
        if target_type is not None:
            return cls._coerce_to_type(
                value, target_type, evaluator=evaluator, path_format=path_format
            )

        if isinstance(value, ExprValue):
            return value
        if isinstance(value, bool):
            return cls._create(ExprType.BOOL, bool_value=value)
        if isinstance(value, Decimal):
            return cls.from_float(value)  # Preserves string representation
        if isinstance(value, int):
            return cls._create(ExprType.INT, int_value=value)
        if isinstance(value, float):
            return cls._create(ExprType.FLOAT, float_value=value)
        if isinstance(value, str):
            return cls._create(ExprType.STRING, string_value=value)
        if value is None:
            return cls.null()
        # Check for IntRangeExpr (circular import prevents isinstance)
        if type(value).__name__ == "IntRangeExpr":
            return cls._create(ExprType.RANGE_EXPR, range_expr_value=value)
        if isinstance(value, list):
            items = [cls._from_python(item) for item in value]
            # Unresolved values cannot appear in list construction from Python values.
            # Use the evaluator's _eval_list for list literals with unresolved elements.
            for item in items:
                if item.type.type_code == TypeCode.UNRESOLVED:
                    raise TypeError(
                        "Cannot construct a list containing unresolved values. "
                        "Use ExprValue.unresolved() to create unresolved list types for type checking."
                    )
            if not items:
                return cls._from_list([], ExprType.NULLTYPE)
            elem_type = cls._infer_list_element_type(items)
            # Coerce int -> float if needed
            if elem_type.type_code == TypeCode.FLOAT:
                items = [
                    cls(float(v.item())) if v.type.type_code == TypeCode.INT else v for v in items
                ]
            # Coerce path -> string if needed
            elif elem_type.type_code == TypeCode.STRING:
                items = [
                    cls(v.to_string()) if v.type.type_code == TypeCode.PATH else v for v in items
                ]
            # Coerce list[int] -> list[float] if needed
            elif elem_type == ExprType.LIST_FLOAT:
                coerced = []
                for v in items:
                    if v.type == ExprType.LIST_INT:
                        inner = [cls(float(e.item())) for e in v.to_expr_value_list()]
                        coerced.append(cls._from_list(inner, ExprType.FLOAT))
                    else:
                        coerced.append(v)
                items = coerced
            # Coerce list[path] -> list[string] if needed
            elif elem_type == ExprType.LIST_STRING:
                coerced = []
                for v in items:
                    if v.type == ExprType.LIST_PATH:
                        inner = [cls(e.to_string()) for e in v.to_expr_value_list()]
                        coerced.append(cls._from_list(inner, ExprType.STRING))
                    else:
                        coerced.append(v)
                items = coerced
            return cls._from_list(items, elem_type)
        raise TypeError(f"Cannot convert {type(value).__name__} to ExprValue")

    @classmethod
    def _coerce_to_type(
        cls, value: Any, target: ExprType, *, evaluator: Any = None, path_format: Any = None
    ) -> "ExprValue":
        """Coerce a Python value to a specific ExprType."""
        if isinstance(value, ExprValue):
            if value.type == target:
                return value
            value = value.item()
        tc = target.type_code
        if tc == TypeCode.INT:
            return cls._create(ExprType.INT, int_value=int(value))
        if tc == TypeCode.FLOAT:
            return cls.from_float(float(value), str(value))
        if tc == TypeCode.STRING:
            return cls._create(ExprType.STRING, string_value=str(value))
        if tc == TypeCode.PATH:
            if evaluator is not None:
                return evaluator.make_path_value(str(value))
            if path_format is not None:
                return cls._normalize_path_value(str(value), path_format)
            raise ExpressionTypeError(
                "Constructing a PATH ExprValue requires either evaluator= or path_format="
            )
        if tc == TypeCode.BOOL:
            if isinstance(value, bool):
                return cls._create(ExprType.BOOL, bool_value=value)
            return cls._create(ExprType.BOOL, bool_value=str(value).lower() == "true")
        if tc == TypeCode.RANGE_EXPR:
            if isinstance(value, RangeExpr):
                return cls._create(ExprType.RANGE_EXPR, range_expr_value=value)
            return cls._create(ExprType.RANGE_EXPR, range_expr_value=RangeExpr(str(value)))
        if tc == TypeCode.LIST and target.type_params:
            elem_type = target.type_params[0]
            items = [
                cls._coerce_to_type(v, elem_type, evaluator=evaluator, path_format=path_format)
                for v in value
            ]
            return cls._from_list(items, elem_type)
        raise TypeError(f"Cannot coerce to type {target}")

    @classmethod
    def _normalize_path_value(cls, string_value: str, path_format: Any) -> "ExprValue":
        """Create a PATH ExprValue normalized to the given path_format.

        Handles URI paths (passed through unchanged) and filesystem paths
        (normalized via PurePosixPath or PureWindowsPath).
        """
        if not is_uri(string_value):
            if path_format == PathFormat.POSIX:
                string_value = str(PurePosixPath(string_value))
            else:
                string_value = str(PureWindowsPath(string_value))

        return cls._create(ExprType.PATH, string_value=string_value, path_format=path_format)

    @staticmethod
    def _infer_list_element_type(values: list["ExprValue"]) -> ExprType:
        """Infer the element type for a list from its values."""
        types = [v.type for v in values]
        first = types[0]
        if all(t == first for t in types):
            return first

        # Filter out list[?] (empty lists) — they're compatible with any list type
        non_empty_types = [t for t in types if t != ExprType(TypeCode.LIST, [ExprType.NULLTYPE])]
        if non_empty_types and all(t.type_code == TypeCode.LIST for t in types):
            if len(non_empty_types) == 0:
                return first  # all empty lists
            if all(t == non_empty_types[0] for t in non_empty_types):
                return non_empty_types[0]

        # int/float mix -> float
        type_codes = {t.type_code for t in types}
        if type_codes == {TypeCode.INT, TypeCode.FLOAT}:
            return ExprType.FLOAT

        # path/string mix -> string
        if type_codes == {TypeCode.PATH, TypeCode.STRING}:
            return ExprType.STRING

        # Nested list with int/float element mix -> list[float]
        if type_codes == {TypeCode.LIST}:
            inner_codes = {t.type_params[0].type_code for t in types if t.type_params}
            # Filter out NULLTYPE (empty sublists)
            inner_codes.discard(TypeCode.NULLTYPE)
            if len(inner_codes) == 1:
                return ExprType(TypeCode.LIST, [ExprType(inner_codes.pop())])
            if inner_codes == {TypeCode.INT, TypeCode.FLOAT}:
                return ExprType.LIST_FLOAT
            if inner_codes == {TypeCode.PATH, TypeCode.STRING}:
                return ExprType.LIST_STRING

        # Incompatible types
        unique = list(dict.fromkeys(str(t) for t in types))
        raise TypeError(f"List contains incompatible types: {', '.join(unique)}")

    @classmethod
    def null(cls) -> "ExprValue":
        """Create a null value."""
        return cls._create(ExprType.NULLTYPE, is_null=True)

    @classmethod
    def unresolved(cls, constraint: "ExprType | str") -> "ExprValue":
        """Create an unresolved value with the given type constraint.

        An unresolved value is a placeholder used during static type checking for
        symbols whose values are not available (e.g., task parameters checked at
        submission time). It carries type information but has no concrete value —
        calling item() or to_string() will raise an error.

        Args:
            constraint: The type that the unresolved value satisfies (e.g., ExprType.INT or "int").
        """
        if isinstance(constraint, str):
            constraint = ExprType(constraint)
        return cls._create(ExprType(TypeCode.UNRESOLVED, [constraint]))

    @classmethod
    def from_float(cls, value: float | Decimal, original_str: Optional[str] = None) -> ExprValue:
        """Create a float ExprValue, optionally preserving original string representation.

        Args:
            value: The numeric value (float, int, or Decimal)
            original_str: Optional string representation to preserve for pass-through.
                          If not provided and value is Decimal, uses str(value).
        """
        if not isinstance(value, (int, float, Decimal)):
            raise TypeError(f"Expected float or Decimal, got {type(value).__name__}")
        if original_str is not None and not isinstance(original_str, str):
            raise TypeError(f"original_str must be str, got {type(original_str).__name__}")
        str_value = (
            original_str
            if original_str is not None
            else (str(value) if isinstance(value, Decimal) else None)
        )
        return cls._create(ExprType.FLOAT, float_value=float(value), string_value=str_value)

    @classmethod
    def _from_list(cls, values: list[ExprValue], elem_type: ExprType) -> ExprValue:
        return cls._create(ExprType(TypeCode.LIST, [elem_type]), list_value=values)

    def to_expr_value_list(self) -> list["ExprValue"]:
        """Return the value as a list of ExprValue items."""
        if self._list_value is None:
            raise TypeError(f"Cannot convert {self.type} to list")
        return self._list_value

    def to_string(self) -> str:
        """Convert value to string representation."""
        import json

        if self.is_null:
            return ""
        tc = self.type.type_code
        if tc == TypeCode.BOOL:
            return "true" if self._bool_value else "false"
        if tc == TypeCode.INT:
            return str(self._int_value)
        if tc == TypeCode.FLOAT:
            # Preserve original string if available (pass-through)
            if self._string_value:
                return self._string_value
            return str(self._float_value)
        if tc in (TypeCode.STRING, TypeCode.PATH):
            return self._string_value  # type: ignore
        if tc == TypeCode.RANGE_EXPR:
            return str(self._range_expr_value)
        if tc == TypeCode.LIST:
            return json.dumps(self._to_json_value())
        if tc == TypeCode.UNRESOLVED:
            raise ExpressionTypeError(
                f"Cannot convert unresolved[{self.type.type_params[0]}] to string: value is not known"
            )
        return ""

    def _to_json_value(self):
        """Convert to JSON-serializable Python value."""
        tc = self.type.type_code
        if tc == TypeCode.BOOL:
            return self._bool_value
        if tc == TypeCode.INT:
            return self._int_value
        if tc == TypeCode.FLOAT:
            return self._float_value
        if tc in (TypeCode.STRING, TypeCode.PATH):
            return self._string_value
        if tc == TypeCode.RANGE_EXPR:
            return str(self._range_expr_value)
        if tc == TypeCode.LIST:
            return [item._to_json_value() for item in self._list_value]  # type: ignore
        if self.is_null:
            return None
        return self.to_string()

    def item(self) -> Any:
        """Extract the native Python value.

        Returns:
            - bool for BOOL
            - int for INT
            - float for FLOAT
            - str for STRING
            - str for PATH
            - IntRangeExpr for RANGE_EXPR
            - list for LIST (recursively extracts items)
            - None for null values
        """

        if self.is_null:
            return None
        tc = self.type.type_code
        if tc == TypeCode.BOOL:
            return self._bool_value
        if tc == TypeCode.INT:
            return self._int_value
        if tc == TypeCode.FLOAT:
            return self._float_value
        if tc in (TypeCode.STRING, TypeCode.PATH):
            return self._string_value
        if tc == TypeCode.RANGE_EXPR:
            return self._range_expr_value
        if tc == TypeCode.LIST:
            return [item.item() for item in self._list_value]  # type: ignore
        if tc == TypeCode.UNRESOLVED:
            raise ExpressionTypeError(
                f"Cannot extract value from unresolved[{self.type.type_params[0]}]: value is not known"
            )
        return None

    def __repr__(self) -> str:
        if self.is_null:
            return "ExprValue(None)"
        tc = self.type.type_code
        if tc == TypeCode.UNRESOLVED:
            return f"ExprValue.unresolved({self.type.type_params[0]!r})"
        if tc == TypeCode.BOOL:
            return f"ExprValue({self._bool_value})"
        if tc == TypeCode.INT:
            return f"ExprValue({self._int_value})"
        if tc == TypeCode.FLOAT:
            if self._string_value is not None:
                return f"ExprValue({self._string_value!r}, type='float')"
            return f"ExprValue({self._float_value})"
        if tc == TypeCode.STRING:
            return f"ExprValue({self._string_value!r})"
        if tc == TypeCode.PATH:
            pf = self._path_format
            pf_str = f", path_format=PathFormat.{pf.name}" if pf is not None else ""
            return f"ExprValue({self._string_value!r}, type='path'{pf_str})"
        if tc == TypeCode.LIST:
            # Check if this list (or nested list) contains path elements
            pf = self._find_path_format()
            pf_str = f", path_format=PathFormat.{pf.name}" if pf is not None else ""
            return f"ExprValue({self.item()!r}, type={str(self.type)!r}{pf_str})"
        return f"ExprValue({self.to_string()!r}, type={str(self.type)!r})"

    def _find_path_format(self) -> "Any":
        """Find the path_format from the deepest path elements in a list, or None."""
        current = self
        while current._list_value is not None and current._list_value:
            first = current._list_value[0]
            if first.type.type_code == TypeCode.PATH:
                return first._path_format
            if first.type.type_code == TypeCode.LIST:
                current = first
                continue
            break
        return None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExprValue):
            return NotImplemented
        if self.type != other.type:
            return False
        if self.is_null != other.is_null:
            return False
        if self.is_null:
            return True
        tc = self.type.type_code
        if tc == TypeCode.BOOL:
            return self._bool_value == other._bool_value
        if tc == TypeCode.INT:
            return self._int_value == other._int_value
        if tc == TypeCode.FLOAT:
            return self._float_value == other._float_value
        if tc in (TypeCode.STRING, TypeCode.PATH):
            return self._string_value == other._string_value
        if tc == TypeCode.LIST:
            return self._list_value == other._list_value
        if tc == TypeCode.RANGE_EXPR:
            return self._range_expr_value == other._range_expr_value
        if tc == TypeCode.UNRESOLVED:
            return True  # All unresolved[T] values with same type are equal
        return False

    def memory_size(self) -> int:
        """Return the memory size of this value in bytes for memory tracking.

        Size is sizeof(ExprValue) + storage for variable-sized data.
        """
        import sys

        base = sys.getsizeof(self)
        tc = self.type.type_code
        if tc in (TypeCode.STRING, TypeCode.PATH):
            return base + sys.getsizeof(self._string_value)
        if tc == TypeCode.RANGE_EXPR and self._range_expr_value is not None:
            r = self._range_expr_value
            return (
                base
                + sys.getsizeof(r)
                + sys.getsizeof(r.ranges)
                + sum(sys.getsizeof(rng) for rng in r.ranges)
            )
        if tc == TypeCode.LIST and self._list_value is not None:
            lst = self._list_value
            return base + sys.getsizeof(lst) + sum(v.memory_size() for v in lst)
        return base
