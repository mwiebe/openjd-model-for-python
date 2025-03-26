# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations
import ast
from typing import Type, cast
from keyword import kwlist
import secrets
import string

from .._errors import ExpressionError, TokenError
from .._tokenstream import Token, TokenStream, TokenType
from ._nodes import FullNameNode, Node
from ._tokens import DotToken, NameToken
from .._types import ModelParsingContextInterface

_tokens: dict[TokenType, Type[Token]] = {TokenType.NAME: NameToken, TokenType.DOT: DotToken}

_KW_SUB_CHARS = string.ascii_letters + string.digits


class FixupRenamedKeywordsVisitor(ast.NodeTransformer):
    def __init__(self, keywords_renamed: dict[str, str]):
        self._rename = {value: key for key, value in keywords_renamed.items()}
        super().__init__()

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        value = self.visit(node.value)
        return ast.Attribute(value=value, attr=self._rename.get(node.attr, node.attr), ctx=node.ctx)


def ast_parse_keyword_context(source: str) -> ast.AST:
    """Performs a context-sensitive mode="eval" parse, where Python keywords can be
    names after a '.' property access.
    """
    keywords_renamed: dict[str, str] = {}
    while True:
        try:
            ast_node = ast.parse(source, mode="eval")

            if keywords_renamed:
                ast_node = FixupRenamedKeywordsVisitor(keywords_renamed).visit(ast_node)

            return ast_node
        except SyntaxError as exc:
            # Check for keyword after '.' - either at offset-2 or end_offset-1 (0-indexed)
            kw_start = None
            end_offset: int | None = getattr(exc, "end_offset", None)
            if exc.offset is not None and exc.offset >= 2 and source[exc.offset - 2] == ".":
                kw_start = exc.offset - 1
            elif end_offset is not None and end_offset >= 1 and source[end_offset - 1] == ".":
                kw_start = end_offset

            if kw_start is not None:
                # Find the keyword length
                kw_end = kw_start
                while kw_end < len(source) and (source[kw_end].isalnum() or source[kw_end] == "_"):
                    kw_end += 1
                keyword = source[kw_start:kw_end]

                if keyword in kwlist:
                    keyword_sub = keywords_renamed.get(keyword)
                    if not keyword_sub:
                        while True:
                            keyword_sub = secrets.choice(string.ascii_letters) + "".join(
                                secrets.choice(_KW_SUB_CHARS) for _ in range(len(keyword) - 1)
                            )
                            if keyword_sub not in source:
                                break
                        keywords_renamed[keyword] = keyword_sub
                    source = source[:kw_start] + keyword_sub + source[kw_end:]
                    continue
            raise


def parse_format_string_expr(expr: str, *, context: ModelParsingContextInterface) -> Node:
    """Generate an expression tree for the given string interpolation expression.

    Args:
        expr (str): A string interpolation expression

    Raises:
        ExpressionError: If the given expression does not adhere to the grammar.
        TokenError: If the given expression contains nonvalid or unexpected tokens.

    Returns:
        Node: Root of the expression tree.
    """

    ## With this code commented out, it will always use the Python grammar-based expressions
    # if not ("EXPR" in context.extensions or context.spec_rev > SpecificationRevision.v2023_09):
    #     return FormatStringExprParser_v2023_09().parse(expr)

    # With the EXPR extension, the expression grammar is defined as a subset of Python.
    # Therefore we can use the Python standard library 'ast' module to parse it.

    if "\n" in expr:
        raise ExpressionError("Format string expression cannot be split across multiple lines")

    # Parse the expression using the Python grammar
    expr_stripped = expr.lstrip()

    try:
        ast_node = ast.parse(expr_stripped, mode="eval")

        return FormatStringAstVisitor(expr_stripped).visit(ast_node)
    except SyntaxError as exc:
        leading_space = expr[: len(expr) - len(expr_stripped)]
        raise ExpressionError(
            "Syntax error in format string expression:\n  {{"
            + expr
            + "}}"
            + f"\n    {leading_space}{' ' * (exc.offset - 1)}^"  # type: ignore
        )


class FormatStringAstVisitor(ast.NodeVisitor):
    def __init__(self, expr: str):
        self._expr = expr
        super().__init__()

    def raise_error(self, node: ast.AST) -> Node:
        # Convert the utf-8 byte offset value into a character offset
        line: str = self._expr.splitlines()[node.lineno - 1]  # type: ignore
        line_bytes = line.encode("utf-8")
        offset = len(line_bytes[: node.col_offset].decode("utf-8"))  # type: ignore

        raise SyntaxError("Syntax error", (None, node.lineno, offset, None))  # type: ignore

    def visit_Expression(self, node: ast.Expression) -> Node:
        return self.visit(node.body)

    def visit_Name(self, node: ast.Name):
        return FullNameNode(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> Node:
        # The value should produce a FullNameNode
        value = self.visit(node.value)
        if not isinstance(value, FullNameNode):
            return self.raise_error(node)

        return FullNameNode(f"{value.name}.{node.attr}")

    def generic_visit(self, node: ast.AST) -> Node:
        # Any AST nodes not handled explicitly by a function above
        # will be handled by this function, and therefore produce a syntax error.
        return self.raise_error(node)


class FormatStringExprParser_v2023_09:
    """
    Parser used to build an AST of the currently supported operations.

    This class is only applicable to the 2023-09 specification without the EXPR extension.
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
