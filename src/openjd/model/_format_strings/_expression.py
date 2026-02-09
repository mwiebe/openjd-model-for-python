# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import numbers
from typing import Union, Optional

from .._errors import ExpressionError
from ._nodes import Node
from ._parser import parse_format_string_expr, ExprNode
from .._types import ModelParsingContextInterface, ResolutionScope

from ...expr import ExprType, ExprValue, FunctionLibrary
from ...expr._symbol_table import SymbolTable
from ...expr._path_mapping import PathFormat


class InterpolationExpression:
    expr: str
    _expression_tree: ExprNode | Node
    context: ModelParsingContextInterface

    def __init__(self, expr: str, *, context: ModelParsingContextInterface) -> None:
        """Constructor.

        Raises:
            ExpressionError: The provided expression cannot be parsed.
            TokenError: The provided expression contains nonvalid or unexpected tokens.

        Args:
            expr (str): The expression
        """
        self.expr = expr
        self.context = context

        # Raises: ExpressionError, TokenError
        self._expression_tree = parse_format_string_expr(expr, context=context)

    def validate_symbol_refs(
        self,
        *,
        symbols: set[str],
        types: dict[str, ExprType] | None = None,
        scope: ResolutionScope | None = None,
    ) -> None:
        """Check whether this expression can be evaluated correctly given a set of symbol names.

        Args:
            symbols (set[str]): The names of symbols visible to this expression.
            types (dict[str, ExprType] | None): Optional mapping of symbol names to types.
            scope (ResolutionScope | None): The resolution scope for library selection.

        Raises:
            ValueError: If the expression cannot be evaluated with the given symbol names
        """
        self._expression_tree.validate_symbol_refs(symbols=symbols, types=types, scope=scope)

    def evaluate(
        self,
        *,
        symtab: SymbolTable,
        library: Optional[FunctionLibrary] = None,
        path_format: Optional[PathFormat] = None,
    ) -> Union[numbers.Real, str]:
        """Evaluate the expression given a SymbolTable.

        Args:
            symtab (SymbolTable): A symbol table containing values to use in the evaluation.
            library: Optional function library for expression evaluation.
            path_format: Optional path format for path type behavior.

        Raises:
            ExpressionError: If the expression could not be evaluated.

        Returns:
            Union[numbers.Real, str]: Resulting value.
        """
        try:
            result = self._expression_tree.evaluate(
                symtab=symtab, library=library, path_format=path_format
            )
        except ValueError as exc:
            raise ExpressionError(f"Expression failed validation: {str(exc)}")

        if isinstance(result, ExprValue):
            return result.to_string()

        if isinstance(result, (numbers.Real, str)):
            return result

        raise ExpressionError(f"Nonvalid result type: {result} of type {type(result)}")

    def evaluate_typed(
        self,
        *,
        symtab: SymbolTable,
        library: FunctionLibrary,
        target_type: Optional["ExprType"] = None,
        path_format: Optional[PathFormat] = None,
    ) -> "ExprValue":
        """Evaluate the expression and return the raw ExprValue.

        Args:
            symtab (SymbolTable): A symbol table containing values to use in the evaluation.
            library: Function library for expression evaluation.
            target_type: Optional target ExprType for type coercion (can be union).
            path_format: Optional path format for path type behavior.

        Raises:
            ExpressionError: If the expression could not be evaluated.

        Returns:
            ExprValue: The raw expression value preserving type information.
        """
        if isinstance(self._expression_tree, ExprNode):
            return self._expression_tree.evaluate_typed(
                symtab=symtab,
                library=library,
                target_type=target_type,
                path_format=path_format,
            )
        raise ExpressionError("evaluate_typed requires EXPR extension")
