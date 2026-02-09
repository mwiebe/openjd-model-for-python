# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from typing import Any, Type, cast, Optional

from .._errors import ExpressionError as ModelExpressionError, TokenError
from .._tokenstream import Token, TokenStream, TokenType
from ._nodes import FullNameNode, Node
from ._tokens import DotToken, NameToken
from .._types import ModelParsingContextInterface
from ...expr import (
    ParsedExpression,
    ExprType,
    FunctionLibrary,
    SymbolTable,
    evaluate_expression,
    parse_expression,
    get_default_library,
)
from ...expr._errors import ExpressionError as ExprExpressionError, ExpressionTypeError
from ...expr._path_mapping import PathFormat

from .._types import ResolutionScope

_tokens: dict[TokenType, Type[Token]] = {TokenType.NAME: NameToken, TokenType.DOT: DotToken}


def parse_format_string_expr(
    expr: str, *, context: ModelParsingContextInterface
) -> "ExprNode | Node":
    """Generate an expression tree for the given string interpolation expression.

    Args:
        expr (str): A string interpolation expression
        context: The model parsing context

    Raises:
        ExpressionError: If the given expression does not adhere to the grammar.
        TokenError: If the given expression contains nonvalid or unexpected tokens.

    Returns:
        Node: Root of the expression tree.
    """
    if "EXPR" in context.extensions:
        # EXPR extension (RFC 0005): use openjd.expr for full expression language
        return ExprNode(parse_expression(expr))
    return FormatStringExprParser_v2023_09().parse(expr)


class ExprNode(Node):
    """Expression tree node wrapping a ParsedExpression from openjd.expr.

    Type validation is performed using the types dict passed to validate_symbol_refs,
    which maps symbol names to their ExprType. This enables early type checking
    during expression parsing (EXPR extension).
    """

    def __init__(self, parsed: "ParsedExpression") -> None:  # noqa: F821
        self._parsed = parsed

    def validate_symbol_refs(
        self,
        *,
        symbols: set[str],
        types: dict[str, ExprType] | None = None,
        scope: ResolutionScope | None = None,
    ) -> None:
        if types is None:
            raise ValueError(
                "ExprNode requires types for validation (EXPR extension must provide types)"
            )
        # Add empty namespaces so undefined symbols report full path (e.g. "Param.X" not "Param")
        namespaces = ("Param", "RawParam", "Task.Param", "Task.RawParam", "Env.File", "Task.File")
        types_with_ns: dict[str, Any] = dict(types)
        for ns in namespaces:
            if not any(k == ns or k.startswith(ns + ".") for k in types):
                types_with_ns[ns] = SymbolTable()
        unresolved_symtab = SymbolTable(types_with_ns)
        # Use host context library for SESSION/TASK scope (runtime), default for TEMPLATE (submission)
        if scope in (ResolutionScope.SESSION, ResolutionScope.TASK):
            library = get_default_library().with_host_context()
        else:
            library = get_default_library()
        # Type check by evaluating with unresolved values
        try:
            evaluate_expression(self._parsed.expr, values=unresolved_symtab, library=library)
        except ExprExpressionError as exc:
            raise ValueError(str(exc))

        # Parse for local_bindings to check comprehension variable shadowing
        parsed = parse_expression(self._parsed.expr)
        if parsed.local_bindings:
            let_names = {k for k in types if k.islower() or k.startswith("_")}
            for var_name in parsed.local_bindings:
                if var_name in let_names:
                    raise ValueError(
                        f"List comprehension variable '{var_name}' shadows let binding '{var_name}'"
                    )

    def evaluate(
        self,
        *,
        symtab: SymbolTable,
        library: Optional[FunctionLibrary] = None,
        path_format: Optional[PathFormat] = None,
    ) -> Any:
        lib = library or get_default_library()
        # First try evaluating with STRING target type
        try:
            result = self._parsed.evaluate(
                values=symtab,
                library=lib,
                target_type=ExprType.STRING,
                path_format=path_format,
            )
            return result.to_string()
        except ExpressionTypeError:
            # If that fails, evaluate unconstrained and convert to string
            result = self._parsed.evaluate(
                values=symtab,
                library=lib,
                target_type=None,
                path_format=path_format,
            )
            return result.to_string()

    def evaluate_typed(
        self,
        *,
        symtab: SymbolTable,
        library: FunctionLibrary,
        target_type: Optional[ExprType] = None,
        path_format: Optional[PathFormat] = None,
    ) -> Any:
        """Evaluate and return the raw ExprValue."""
        return self._parsed.evaluate(
            values=symtab,
            library=library,
            target_type=target_type,
            path_format=path_format,
        )

    def __repr__(self) -> str:
        return f"ExprNode({self._parsed.expr})"


class FormatStringExprParser_v2023_09:
    """
    Parser used to build an AST of format strings for the 2023-09 specification.
    """

    def parse(self, expr: str) -> Node:
        """Generate an expression tree for the given string interpolation expression.

        Args:
            expr (str): A string interpolation expression

        Raises:
            ExpressionError: If the given expression does not adhere to the grammar.
            TokenError: If the given expression contains nonvalid or unexpected tokens.

        Returns:
            Node: Root of the expression tree.
        """

        # Raises: TokenError
        self._tokens = TokenStream(expr, supported_tokens=_tokens)

        result = self._expression()
        if not self._tokens.at_end():
            token = self._tokens.next()
            raise TokenError(self._tokens.expr, token.value, token.start)

        return result

    def _expression(self) -> Node:
        """Matches the root of the expression grammar.

        Grammar:
        <Expression> ::= <FullName>
        <FullName> ::= <Name> ( <Dot> <Name> )*
        <Name> ::= [A-Za-z_][A-Za-z0-9_]*
        <Dot> ::= '.'

        Raises:
            ExpressionError: When there is an error parsing the expression.
            TokenError: If the expression contains unexpected tokens.

        Returns:
            Node: Root node of the expression tree.
        """
        if self._tokens.at_end():
            raise ModelExpressionError("Empty expression")

        if isinstance(self._tokens.lookahead(0), NameToken):
            # Raises: ExpressionError, TokenError
            return self._match_name()

        token = self._tokens.next()
        raise TokenError(self._tokens.expr, token.value, token.start)

    def _match_name(self) -> FullNameNode:
        """Matches:
        <FullName> ::= <Name> ( <Dot> <Name> )*

        Raises:
            ExpressionError: When there is an error parsing the expression.
            TokenError: If the expression contains unexpected tokens.
        """
        token: Token = cast(NameToken, self._tokens.next())
        names = [token.value]

        try:
            while isinstance(self._tokens.lookahead(0), DotToken):
                _ = self._tokens.next()
                try:
                    token = self._tokens.next()
                except IndexError:
                    raise ModelExpressionError(
                        f"Unexpected end of name '{'.'.join(names)}.'",
                    )
                if not isinstance(token, NameToken):
                    raise TokenError(self._tokens.expr, token.value, token.start)
                names.append(token.value)
        except IndexError:
            # Catches the lookahead on the while condition. Not having a dot after the name is okay.
            pass

        return FullNameNode(".".join(names))
