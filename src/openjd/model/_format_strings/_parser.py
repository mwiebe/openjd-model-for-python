# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import ast
from typing import Type, cast

from .._errors import ExpressionError, TokenError
from .._tokenstream import Token, TokenStream, TokenType
from ._nodes import FullNameNode, Node
from ._tokens import DotToken, NameToken
from .._types import ModelParsingContextInterface

_tokens: dict[TokenType, Type[Token]] = {TokenType.NAME: NameToken, TokenType.DOT: DotToken}


def format_string_expr_parse(expr: str, *, context: ModelParsingContextInterface) -> Node:
    """Generate an expression tree for the given string interpolation expression.

    Args:
        expr (str): A string interpolation expression

    Raises:
        ExpressionError: If the given expression does not adhere to the grammar.
        TokenError: If the given expression contains nonvalid or unexpected tokens.

    Returns:
        Node: Root of the expression tree.
    """

    # Prior to the TEMPLATE_EXPR extension, the expression grammar was not defined in terms of the Python grammar.
    print(f"context is {context}")
    if "TEMPLATE_EXPR" not in context.extensions:
        return Parser().parse(expr)

    # With the TEMPLATE_EXPR, the expression grammar is defined as a subset of Python.
    # Therefore we can use the Python standard library 'ast' module to parse it.

    if "\n" in expr:
        raise ExpressionError("Format string expression cannot be split across multiple lines")

    # Parse the expression using the Python grammar
    expr_stripped = expr.lstrip()

    try:
        ast_node = ast.parse(expr_stripped, mode="eval")

        return FormatStringAstVisitor(expr_stripped).visit(ast_node)
    except SyntaxError as exc:
        leading_space = expr[:len(expr) - len(expr_stripped)]
        raise ExpressionError("Syntax error in format string expression:\n  {{" + expr + "}}" + f"\n    {leading_space}{' ' * (exc.offset - 1)}^")


class FormatStringAstVisitor(ast.NodeVisitor):
    def __init__(self, expr: str):
        self._expr = expr
        super().__init__()

    def raise_error(self, node: ast.AST):
        # Convert the utf-8 byte offset value into a character offset
        line = self._expr.splitlines()[node.lineno - 1]
        line_bytes = line.encode("utf-8")
        offset = len(line_bytes[:node.col_offset].decode("utf-8"))

        raise SyntaxError("Syntax error", (None, node.lineno, offset, None))

    def visit_Expression(self, node: ast.Expression) -> Node:
        return self.visit(node.body)

    def visit_Name(self, node: ast.Name):
        return FullNameNode(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> Node:
        # The value should produce a FullNameNode
        value = self.visit(node.value)
        if not isinstance(value, FullNameNode):
            self.raise_error(node)

        return FullNameNode(f"{value.name}.{node.attr}")

    def generic_visit(self, node: ast.AST) -> Node:
        # Any AST nodes not handled explicitly by a function above
        # will be handled by this function, and therefore produce a syntax error.
        self.raise_error(node)


class Parser:
    """
    Parser used to build an AST of the currently supported operations.

    This class is only applicable to the 2023-09 specification without the TEMPLATE_EXPR extension.
    That extension changed the grammar to be a subset of the Python language.
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
            raise ExpressionError("Empty expression")

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
                    raise ExpressionError(
                        f"Unexpected end of name '{'.'.join(names)}.'",
                    )
                if not isinstance(token, NameToken):
                    raise TokenError(self._tokens.expr, token.value, token.start)
                names.append(token.value)
        except IndexError:
            # Catches the lookahead on the while condition. Not having a dot after the name is okay.
            pass

        return FullNameNode(".".join(names))
