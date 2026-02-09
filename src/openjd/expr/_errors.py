# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Expression language errors."""

from __future__ import annotations

import ast
from typing import Optional


class ExpressionError(ValueError):
    """Base exception for expression evaluation errors."""

    def __init__(
        self,
        message: str,
        *,
        expr: Optional[str] = None,
        node: Optional[ast.AST] = None,
        lineno: Optional[int] = None,
        col_offset: Optional[int] = None,
    ):
        self.expr = expr
        self.node = node
        self._lineno = lineno
        self._col_offset = col_offset
        self._base_message = message
        super().__init__(self._format_message())

    def _get_location(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
        """Get lineno, col_offset, end_col_offset from node or explicit values."""
        if self.node:
            return (
                getattr(self.node, "lineno", None),
                getattr(self.node, "col_offset", None),
                getattr(self.node, "end_col_offset", None),
            )
        return self._lineno, self._col_offset, None

    def _format_message(self) -> str:
        """Format the error message with location info if available."""
        lineno, col_offset, end_col_offset = self._get_location()

        if not self.expr or col_offset is None:
            return self._base_message

        end_lineno = getattr(self.node, "end_lineno", None) if self.node else None

        # Get the relevant line from the expression
        expr_lines = self.expr.split("\n")
        if lineno is not None and 1 <= lineno <= len(expr_lines):
            expr_line = expr_lines[lineno - 1]
        else:
            expr_line = self.expr

        # Build the error with caret pointer
        lines = [self._base_message]
        lines.append(f"  {expr_line}")

        # For multi-line nodes, only underline to end of first line
        if end_lineno is not None and lineno is not None and end_lineno > lineno:
            end_col_offset = len(expr_line)

        # Create caret line - point ^ at the most relevant part
        if end_col_offset is not None and end_col_offset > col_offset:
            caret_pos = col_offset  # Default: caret at start

            # For binary ops, find the operator position between left and right
            if isinstance(self.node, ast.BinOp):
                left = self.node.left
                right = self.node.right
                left_end = getattr(left, "end_col_offset", None)
                right_start = getattr(right, "col_offset", None)
                # Only use if on same line
                if (
                    left_end is not None
                    and right_start is not None
                    and getattr(left, "end_lineno", lineno) == lineno
                    and getattr(right, "lineno", lineno) == lineno
                ):
                    # Python's AST doesn't store the operator token position,
                    # so scan backwards from right operand, skipping whitespace and open parens
                    i = right_start - 1
                    while i >= left_end and expr_line[i] in " \t(":
                        i -= 1
                    if i >= left_end + 1 and expr_line[i - 1 : i + 1] in ("**", "//"):
                        caret_pos = i - 1
                    elif i >= left_end:
                        caret_pos = i

            # For attribute access, point at the attribute name (after the dot)
            elif isinstance(self.node, ast.Attribute):
                value_end = getattr(self.node.value, "end_col_offset", None)
                if (
                    value_end is not None
                    and getattr(self.node.value, "end_lineno", lineno) == lineno
                ):
                    caret_pos = value_end + 1  # +1 for the dot

            # For method calls (Call with Attribute func), point at method name
            elif isinstance(self.node, ast.Call) and isinstance(self.node.func, ast.Attribute):
                value_end = getattr(self.node.func.value, "end_col_offset", None)
                if (
                    value_end is not None
                    and getattr(self.node.func.value, "end_lineno", lineno) == lineno
                ):
                    caret_pos = value_end + 1  # +1 for the dot

            # For subscript, point at the '['
            elif isinstance(self.node, ast.Subscript):
                value_end = getattr(self.node.value, "end_col_offset", None)
                if (
                    value_end is not None
                    and getattr(self.node.value, "end_lineno", lineno) == lineno
                ):
                    caret_pos = value_end

            # Build: ~~^~~ with caret at caret_pos
            span_len = end_col_offset - col_offset
            caret_idx = caret_pos - col_offset
            before = "~" * caret_idx
            after = "~" * (span_len - caret_idx - 1)
            caret = " " * col_offset + before + "^" + after
        else:
            # Single caret
            caret = " " * col_offset + "^"
        lines.append(f"  {caret}")

        return "\n".join(lines)

    def with_context(self, expr: str, node: Optional[ast.AST] = None) -> "ExpressionError":
        """Return a new error with expression context added."""
        if self.expr is not None:
            return self  # Already has context
        return ExpressionError(self._base_message, expr=expr, node=node or self.node)

    def message_with_expr_prefix(self, prefix: str) -> str:
        """Return the error message with a prefix added to the expression line.

        The caret position is adjusted to account for the prefix length.
        Only works for single-line expressions with caret indicators.
        """
        lineno, col_offset, end_col_offset = self._get_location()

        if not self.expr or col_offset is None or "\n" in self.expr:
            return str(self)

        # Build message with prefixed expression line
        lines = [self._base_message]
        lines.append(f"  {prefix}{self.expr}")

        # Calculate caret position (same logic as _format_message)
        caret_pos = col_offset
        if end_col_offset is not None and end_col_offset > col_offset:
            # For binary ops, find the operator position
            if isinstance(self.node, ast.BinOp):
                left_end = getattr(self.node.left, "end_col_offset", None)
                right_start = getattr(self.node.right, "col_offset", None)
                if left_end is not None and right_start is not None:
                    i = right_start - 1
                    while i >= left_end and self.expr[i] in " \t(":
                        i -= 1
                    if i >= left_end + 1 and self.expr[i - 1 : i + 1] in ("**", "//"):
                        caret_pos = i - 1
                    elif i >= left_end:
                        caret_pos = i

            span_len = end_col_offset - col_offset
            caret_idx = caret_pos - col_offset
            before = "~" * caret_idx
            after = "~" * (span_len - caret_idx - 1)
            caret = " " * (col_offset + len(prefix)) + before + "^" + after
        else:
            caret = " " * (caret_pos + len(prefix)) + "^"
        lines.append(f"  {caret}")

        return "\n".join(lines)


class ExpressionTypeError(ExpressionError):
    """Type error during expression evaluation."""

    def with_context(self, expr: str, node: Optional[ast.AST] = None) -> "ExpressionTypeError":
        """Return a new error with expression context added."""
        if self.expr is not None:
            return self
        return ExpressionTypeError(self._base_message, expr=expr, node=node or self.node)
