# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from dataclasses import dataclass
from numbers import Real
from typing import Optional, Union

from .._errors import ExpressionError, TokenError
from ._dyn_constrained_str import DynamicConstrainedStr
from ._expression import InterpolationExpression
from .._types import ModelParsingContextInterface
from ...expr import ExprType, ExprValue, FunctionLibrary, get_default_library
from ...expr._symbol_table import SymbolTable
from ...expr._errors import ExpressionError as ExprExpressionError
from ...expr._path_mapping import PathFormat


@dataclass
class ExpressionInfo:
    start_pos: int
    end_pos: int
    expression: Optional[InterpolationExpression] = None
    resolved_value: Optional[Union[Real, str]] = None


class FormatStringError(ValueError):
    def __init__(self, *, string: str, start: int, end: int, expr: str = "", details: str = ""):
        self.input = string
        expression = f"Expression: {expr}. " if expr else ""
        reason = f"Reason: {details}." if details else ""
        msg = (
            f"Failed to parse interpolation expression at [{start}, {end}]. "
            f"{expression}"
            f"{reason}"
        )
        super().__init__(msg)


class FormatString(DynamicConstrainedStr):
    _processed_list: list[Union[str, ExpressionInfo]]

    def __new__(cls, value: str, *, context: ModelParsingContextInterface):
        """
        Instantiate a FormatString from a given string.

        Verifies that each pair of opening curly braces {{ has a corresponding pair
        of closing curly braces }}, and vice versa.

        Also, verifies that each interpolation expression inside of {{ }} has a valid format.

        Parameters
        ----------
        original_string: str
            A string that contains 0 or more interpolation expressions.
            For example, 'text', '{{expr}}', '{{ expr }}', 'text {{expr}}text{{expr}} text',
            are all valid inputs.

        Raises
        ------
        FormatStringError: if the original string is nonvalid.
        """
        self = super().__new__(cls, value, context=context)
        self._processed_list = self._preprocess(context=context)
        return self

    @property
    def original_value(self) -> str:
        """
        Returns
        -------
        original_string: str
            An original string passed during the construction of this object.
        """
        return self

    @property
    def expressions(self) -> list[ExpressionInfo]:
        """
        Returns
        -------
        expressions: list[ExpressionInfo]
            A list of all interpolation expressions in this interpolated string.
        """
        return [expr for expr in self._processed_list if isinstance(expr, ExpressionInfo)]

    def resolve(
        self,
        *,
        symtab: SymbolTable,
        library: Optional[FunctionLibrary] = None,
        target_type: Optional["ExprType"] = None,
        path_format: Optional[PathFormat] = None,
    ) -> "ExprValue":
        """
        Resolve the format string and return an ExprValue.

        If the format string is purely a single expression (e.g., "{{ expr }}"),
        returns the raw ExprValue which may be a list, null, or scalar.

        If the format string contains literal text or multiple expressions,
        returns a string ExprValue.

        Parameters
        ----------
        symtab: SymbolTable
            A symbol table with values for resolving expressions.
        library: Optional[FunctionLibrary]
            Function library for expression evaluation.
        target_type: Optional[ExprType]
            Optional target ExprType for type coercion (can be union).
        path_format: Optional[PathFormat]
            Controls path type behavior during evaluation.

        Returns
        -------
        ExprValue:
            The resolved value, preserving type information.

        Raises
        ------
        FormatStringError: if it is impossible to resolve
        all interpolation expressions with a given symbol table.
        """
        # Pure single EXPR expression — return typed result (may be list, null, etc.)
        non_empty_parts = [p for p in self._processed_list if p != ""]
        if (
            len(non_empty_parts) == 1
            and isinstance(non_empty_parts[0], ExpressionInfo)
            and non_empty_parts[0].expression is not None
            and "EXPR" in non_empty_parts[0].expression.context.extensions
        ):
            expr_info = non_empty_parts[0]
            assert expr_info.expression is not None
            lib = library or get_default_library()
            try:
                return expr_info.expression.evaluate_typed(
                    symtab=symtab,
                    library=lib,
                    target_type=target_type,
                    path_format=path_format,
                )
            except ExpressionError as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=expr_info.start_pos,
                    end=expr_info.end_pos,
                    expr=expr_info.expression.expr,
                    details=str(exc),
                )
        resolved_list: list[str] = []
        for element in self._processed_list:
            assert isinstance(element, (ExpressionInfo, str))
            if isinstance(element, str):
                resolved_list.append(element)
                continue

            assert element.expression is not None
            try:
                element.resolved_value = element.expression.evaluate(
                    symtab=symtab,
                    library=library,
                    path_format=path_format,
                )
            except ExpressionError as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=element.start_pos,
                    end=element.end_pos,
                    expr=element.expression.expr,
                    details=str(exc),
                )

            resolved_list.append(str(element.resolved_value))

        return ExprValue("".join(resolved_list))

    def _preprocess(
        self, *, context: ModelParsingContextInterface
    ) -> list[Union[str, ExpressionInfo]]:
        """
        Scans through the original string to find all interpolation expressions inside of {{ }}.
        Also, validates the content of each interpolation expression inside of {{ }}.

        The output format is designed to be used later by `resolve()` function.
        It allows us to replace each ExpressionInfo with a resolved value
        and then efficiently combine simple strings and resolved values into the final string.

        Raises
        ------
        FormatStringError
            - if the string contains opening pair {{ without a matching closing pair,
              and vice versa.
            - if any expression inside of {{ }} is nonvalid.

        Returns
        -------
        preprocessed_list: list[Union[str, ExpressionInfo]]
            A list, where each element is either
                - a string that doesn't contain interpolation expression {{ }}, or
                - an instance of ExpressionInfo
            For example, for original string 'a {{ B.C }} d {{ E.f }}' the list will be
            ['a ', ExpressionInfo({{ B.C }}), ' d ', ExpressionInfo({{ E.f }})]
        """
        result_list: list[Union[str, ExpressionInfo]] = []

        opening = "{{"
        closing = "}}"

        braces_end = 0
        while braces_end < len(self):
            braces_start = self.find(opening, braces_end)
            expression_end = self.find(closing, braces_end)

            if braces_start == -1 and expression_end == -1:
                result_list.append(self[braces_end:])
                break

            if expression_end < braces_start:
                raise FormatStringError(
                    string=self.original_value,
                    start=braces_end,
                    end=len(self.original_value),
                    details="Braces mismatch",
                )

            if braces_start == -1 and expression_end != -1:
                raise FormatStringError(
                    string=self.original_value,
                    start=braces_end,
                    end=(expression_end + len(closing)),
                    details="Missing opening braces",
                )

            result_list.append(self[braces_end:braces_start])

            expression_start = braces_start + len(opening)
            braces_end = expression_end + len(closing)

            expression_info = ExpressionInfo(braces_start, braces_end)
            try:
                expr = InterpolationExpression(
                    self[expression_start:expression_end], context=context
                )
            except (ExpressionError, ExprExpressionError, TokenError) as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=expression_info.start_pos,
                    end=expression_info.end_pos,
                    details=str(exc),
                )

            expression_info.expression = expr
            result_list.append(expression_info)

        return result_list
