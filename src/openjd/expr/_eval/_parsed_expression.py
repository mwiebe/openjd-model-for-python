# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""ParsedExpression class."""

from __future__ import annotations

import ast
from typing import Any, Optional, TYPE_CHECKING

from .._types import ExprType, TypeCode
from .._value import ExprValue
from .._symbol_table import SymbolTable
from .._errors import ExpressionTypeError

if TYPE_CHECKING:
    from .._functions import FunctionLibrary
    from .._path_mapping import PathFormat


class ParsedExpression:
    """A parsed expression that can be evaluated and inspected for symbol references."""

    def __init__(
        self,
        expr: str,
        ast_node: ast.AST,
        accessed_symbols: set[str],
        called_functions: set[str],
        local_bindings: Optional[set[str]] = None,
    ):
        self.expr = expr
        self._ast_node = ast_node
        self.accessed_symbols = accessed_symbols
        self.called_functions = called_functions
        self.local_bindings = local_bindings or set()
        self.peak_memory_usage: int = 0
        self.operation_count: int = 0

    def evaluate(
        self,
        *,
        values: Optional[SymbolTable | dict[str, Any]] = None,
        library: Optional["FunctionLibrary"] = None,
        target_type: Optional[ExprType] = None,
        path_format: Optional["PathFormat"] = None,
        operation_limit: Optional[int] = None,
    ) -> ExprValue:
        """Evaluate the parsed expression.

        Args:
            values: Symbol table or dict with variable bindings.
            library: Function library (uses default if not provided).
            target_type: Optional expected result type for coercion.
            path_format: Controls `path` type behavior:
                - PathFormat.POSIX: Behave like Python's PurePosixPath
                - PathFormat.WINDOWS: Behave like Python's PureWindowsPath
                - None: Behave like Python's PurePath (system native)
            operation_limit: Maximum number of operations during evaluation.

        After evaluation, peak_memory_usage and operation_count contain the
        peak memory used and total operations performed.
        """
        from ._evaluator import Evaluator
        from .._functions import get_default_library

        if values is not None:
            if isinstance(values, dict):
                symtab = SymbolTable(values)
            else:
                symtab = values
            symtabs = [symtab]
        else:
            symtabs = []
        lib = library or get_default_library()
        evaluator = Evaluator(
            symtabs, lib, expr=self.expr, path_format=path_format, operation_limit=operation_limit
        )
        result = evaluator.evaluate(self._ast_node, target_type)
        self.peak_memory_usage = evaluator.peak_memory
        self.operation_count = evaluator.operation_count

        # Validate and coerce result against target type if specified
        if target_type:
            # Check if result type already matches target
            if target_type.match(result.type) is not None:
                return result

            # Try non-destructive coercion for scalar targets
            if target_type.type_code not in (TypeCode.NULLTYPE, TypeCode.LIST, TypeCode.UNION):
                coerced = evaluator.try_coerce_nondestructive(result, target_type)
                if coerced is not None:
                    return coerced
            elif target_type.type_code == TypeCode.LIST:
                # Try list element coercion (e.g., list[string] -> list[path])
                coerced = evaluator.try_coerce_list(result, target_type)
                if coerced is not None:
                    return coerced
            elif target_type.type_code == TypeCode.UNION:
                # Try coercion to each union member
                for member in target_type.type_params:
                    if member.type_code not in (TypeCode.NULLTYPE, TypeCode.LIST):
                        coerced = evaluator.try_coerce_nondestructive(result, member)
                        if coerced is not None:
                            return coerced

            # No match and no coercion possible
            raise ExpressionTypeError(
                f"Expression result type {result.type} cannot be used where {target_type} is expected"
            )

        return result
