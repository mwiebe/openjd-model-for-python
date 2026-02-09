# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Range expression implementation for the expression language."""

from __future__ import annotations

import re
from bisect import bisect, bisect_left
from collections.abc import Iterator, Sized
from dataclasses import dataclass
from enum import Enum
from itertools import chain
from typing import Tuple, Type


class RangeExprError(ValueError):
    """Error raised when parsing a range expression fails."""

    def __init__(self, expr: str, message: str, position: int | None = None):
        self.expr = expr
        self.position = position
        if position is not None:
            msg = f"{message} in '{expr}' after '{expr[:position]}'"
        else:
            msg = f"{message}: '{expr}'"
        super().__init__(msg)


class RangeExpr(Sized):
    """A range expression representing a set of integers as sorted, non-overlapping ranges.

    Examples:
        RangeExpr("1-10")        # 1, 2, 3, ..., 10
        RangeExpr("1-10:2")      # 1, 3, 5, 7, 9
        RangeExpr("1-5,10-15")   # 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15
    """

    _starts: list[int]
    _ends: list[int]
    _ranges: list[_IntRange]
    _length: int
    _range_length_indices: list[int]

    def __new__(cls, ranges: "list[_IntRange] | str") -> "RangeExpr":
        if isinstance(ranges, str):
            return cls.from_str(ranges)
        return object.__new__(cls)

    def __init__(self, ranges: "list[_IntRange] | str"):
        if isinstance(ranges, str):
            return  # Already initialized by __new__
        if len(ranges) <= 0:
            raise ValueError("Range expression cannot be empty")
        # Sort the ranges, then combine them where possible
        sorted_ranges = sorted(ranges, key=lambda v: (v._start, v._end, v._step))
        self._ranges = [sorted_ranges[0]]
        for range in sorted_ranges[1:]:
            if (
                self._ranges[-1].step == range.step
                and self._ranges[-1].end + range.step == range.start
            ):
                self._ranges[-1] = _IntRange(self._ranges[-1].start, range.end, range.step)
            else:
                self._ranges.append(range)
        self._starts = [v.start for v in self.ranges]
        self._ends = [v.end for v in self.ranges]

        # used to binary search ranges for __getitem__
        self._range_length_indices = []
        length = 0
        for r in self.ranges:
            length += len(r)
            self._range_length_indices.append(length)

        self._length = length
        self._validate()

    @classmethod
    def from_str(cls, range_str: str) -> "RangeExpr":
        """Create a range expression from a string like '1-10,15,20-25:2'."""
        return _Parser(cls).parse(range_str)

    @classmethod
    def from_list(cls, values: list[int] | list[str] | list[int | str]) -> "RangeExpr":
        """Create a range expression from a list of integers."""
        if len(values) == 0:
            raise ValueError("Range expression cannot be empty")
        elif len(values) == 1:
            value = int(values[0])
            return cls([_IntRange(value, value)])
        else:
            values_as_int: list[int] = sorted({int(i) for i in values})
            ranges = []
            start = end = values_as_int[0]
            step = None

            for value in values_as_int[1:]:
                if step is None:
                    end = value
                    step = end - start
                else:
                    if value - end == step:
                        end = value
                    else:
                        ranges.append(_IntRange(start, end, step))
                        start = end = value
                        step = None
            ranges.append(_IntRange(start, end, step or 1))
            return cls(ranges)

    def __len__(self) -> int:
        return self._length

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RangeExpr):
            return NotImplemented
        return self.ranges == other.ranges

    def __str__(self) -> str:
        return ",".join(str(r) for r in self.ranges)

    def __repr__(self) -> str:
        return f"RangeExpr({str(self)!r})"

    def __iter__(self) -> Iterator[int]:
        return chain(*self.ranges)

    def __getitem__(self, index: int) -> int:
        if index < 0:
            index = len(self) + index
        if not (0 <= index < self._length):
            raise IndexError(f"index {index} is out of range")
        range_index = bisect(self._range_length_indices, index)
        if range_index == 0:
            return self.ranges[0][index]
        else:
            actual_index = index - self._range_length_indices[range_index - 1]
            return self.ranges[range_index][actual_index]

    def __contains__(self, value: object) -> bool:
        if not isinstance(value, int):
            return False
        range_index = bisect_left(self._ends, value)
        if range_index >= len(self._ends):
            return False
        return value in self.ranges[range_index]._range

    @property
    def start(self) -> int:
        """The smallest value in the range expression."""
        return self._starts[0]

    @property
    def end(self) -> int:
        """The largest value in the range expression."""
        return self._ends[-1]

    @property
    def ranges(self) -> "list[_IntRange]":
        return self._ranges.copy()

    def _validate(self) -> None:
        prev_range: _IntRange | None = None
        for range_ in self.ranges:
            if prev_range and max(prev_range.start, prev_range.end) >= min(
                range_.start, range_.end
            ):
                raise ValueError(
                    f"Range expression is not valid due to overlapping ranges:\n"
                    f"\t{prev_range} overlaps with {range_}"
                )
            prev_range = range_


class _IntRange(Sized):
    """A single contiguous range of integers."""

    _start: int
    _end: int
    _step: int
    _range: range

    def __init__(self, start: int, end: int, step: int = 1):
        if step > 0:
            if start > end:
                raise ValueError("Range: a descending range must have a negative step")
            self._range = range(start, end + 1, step)
            self._start = start
            self._end = self._range[-1]
            self._step = step
        elif step < 0:
            if start < end:
                raise ValueError("Range: an ascending range must have a positive step")
            self._range = range(start, end - 1, step)
            self._start = self._range[-1]
            self._end = start
            self._step = -step
        else:
            raise ValueError("Range: step must not be zero")

    def __str__(self) -> str:
        if len(self) == 1:
            return str(self._start)
        elif len(self) == 2:
            return f"{self._start},{self._end}"
        elif self.step == 1:
            return f"{self._start}-{self._end}"
        else:
            return f"{self._start}-{self._end}:{self._step}"

    def __repr__(self) -> str:
        # Use "IntRange" for backward compatibility (re-exported from openjd.model)
        return f"IntRange(start={self._start}, end={self._end}, step={self._step})"

    def __len__(self):
        return len(self._range)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _IntRange):
            return NotImplemented
        return (self.start, self.end, self.step) == (other.start, other.end, other.step)

    def __iter__(self) -> Iterator[int]:
        return iter(self._range)

    def __getitem__(self, index: int) -> int:
        if index >= len(self):
            raise IndexError(f"index {index} is out of range")
        return self._range[index]

    @property
    def start(self) -> int:
        return self._start

    @property
    def end(self) -> int:
        return self._end

    @property
    def step(self) -> int:
        return self._step


# --- Tokenizer and Parser (self-contained) ---


class _TokenType(Enum):
    POSINT = "POSINT"
    HYPHEN = "HYPHEN"
    COLON = "COLON"
    COMMA = "COMMA"


@dataclass
class _Token:
    value: str
    start: int
    end: int


class _PosIntToken(_Token):
    pass


class _HyphenToken(_Token):
    pass


class _ColonToken(_Token):
    pass


class _CommaToken(_Token):
    pass


_TOKEN_MAP: dict[_TokenType, Type[_Token]] = {
    _TokenType.POSINT: _PosIntToken,
    _TokenType.HYPHEN: _HyphenToken,
    _TokenType.COLON: _ColonToken,
    _TokenType.COMMA: _CommaToken,
}

_TOKEN_PATTERNS = [
    (_TokenType.POSINT, r"[0-9]+"),
    (_TokenType.HYPHEN, r"-"),
    (_TokenType.COLON, r":"),
    (_TokenType.COMMA, r","),
]

_LEXER_REGEX = (
    "|".join(f"(?P<{tt.value}>{pat})" for tt, pat in _TOKEN_PATTERNS)
    + r"|(?P<WS>\s+)|(?P<INVALID>.)"
)
_LEXER = re.compile(_LEXER_REGEX)


class _Tokenizer:
    def __init__(self, expr: str):
        self._tokens: list[_Token] = []
        self._pos = 0
        self._expr = expr
        for m in _LEXER.finditer(expr):
            if m.lastgroup == "WS":
                continue
            if m.lastgroup == "INVALID":
                raise RangeExprError(expr, f"Unexpected '{m.group()}'", m.start())
            tt = _TokenType(m.lastgroup)
            token_cls = _TOKEN_MAP[tt]
            self._tokens.append(token_cls(m.group(), m.start(), m.end()))

    @property
    def expr(self) -> str:
        return self._expr

    def at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    def next(self) -> _Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def lookahead(self, n: int) -> _Token:
        return self._tokens[self._pos + n]


class _Parser:
    """Range expression parser."""

    def __init__(self, range_cls: type | None = None):
        self._range_cls = range_cls or RangeExpr
        self._expr: str = ""

    def parse(self, expr: str) -> RangeExpr:
        self._expr = expr
        self._tokens = _Tokenizer(expr)
        if self._tokens.at_end():
            raise RangeExprError(expr, "Empty expression")
        result = self._expression()
        if not self._tokens.at_end():
            token = self._tokens.next()
            raise RangeExprError(expr, f"Unexpected '{token.value}'", token.start)
        return result

    def _integer(self) -> Tuple[str, _PosIntToken]:
        num_sign = "+"
        try:
            if isinstance(self._tokens.lookahead(0), _HyphenToken):
                num_sign = "-"
                self._tokens.next()
            token = self._tokens.next()
            if not isinstance(token, _PosIntToken):
                raise RangeExprError(
                    self._expr, f"Expected integer, got '{token.value}'", token.start
                )
        except IndexError:
            raise RangeExprError(self._expr, "Unexpected end of expression")
        return num_sign, token

    def _range(self) -> _IntRange:
        start_sign, start = self._integer()
        if self._tokens.at_end() or isinstance(self._tokens.lookahead(0), _CommaToken):
            return _IntRange(int(start_sign + start.value), int(start_sign + start.value), 1)

        token = self._tokens.next()
        if not isinstance(token, _HyphenToken):
            raise RangeExprError(self._expr, f"Expected '-', got '{token.value}'", token.start)

        end_sign, end = self._integer()
        if self._tokens.at_end() or isinstance(self._tokens.lookahead(0), _CommaToken):
            return _IntRange(int(start_sign + start.value), int(end_sign + end.value), 1)

        if self._tokens.at_end():
            raise RangeExprError(self._expr, "Expected ':'", len(self._expr))
        token = self._tokens.next()
        if not isinstance(token, _ColonToken):
            raise RangeExprError(self._expr, f"Expected ':', got '{token.value}'", token.start)

        step_sign, step = self._integer()
        return _IntRange(
            int(start_sign + start.value),
            int(end_sign + end.value),
            int(step_sign + step.value),
        )

    def _expression(self) -> RangeExpr:
        ranges: list[_IntRange] = [self._range()]
        try:
            while not self._tokens.at_end() and isinstance(self._tokens.lookahead(0), _CommaToken):
                self._tokens.next()
                ranges.append(self._range())
        except IndexError:
            pass
        return self._range_cls(ranges)
