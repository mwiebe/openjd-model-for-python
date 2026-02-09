# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""IntRangeExpr - Pydantic-compatible range expression for OpenJD templates."""

from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

from openjd.expr import RangeExpr
from openjd.expr._range_expr import _IntRange as IntRange
from openjd.expr._range_expr import _Parser as Parser

__all__ = ["IntRangeExpr", "IntRange", "Parser"]


class IntRangeExpr(RangeExpr):
    """A range expression with Pydantic integration for use in OpenJD template models.

    This is a subclass of `openjd.expr.RangeExpr` that adds Pydantic validation
    support, allowing it to be used as a field type in Pydantic models.

    Examples:
        IntRangeExpr("1-10")        # 1, 2, 3, ..., 10
        IntRangeExpr("1-10:2")      # 1, 3, 5, 7, 9
        IntRangeExpr("1-5,10-15")   # 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15
    """

    def __repr__(self) -> str:
        return f"IntRangeExpr({str(self)!r})"

    @classmethod
    def _pydantic_validate(cls, value: Any) -> Any:
        if isinstance(value, IntRangeExpr):
            return value
        elif isinstance(value, RangeExpr):
            # Convert RangeExpr to IntRangeExpr
            return cls(value._ranges)
        elif isinstance(value, str):
            return cls.from_str(value)
        elif isinstance(value, list):
            return cls.from_list(value)
        else:
            raise ValueError("Value must be an integer range expression or a list of integers.")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(cls._pydantic_validate)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string"}
