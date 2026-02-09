# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""String function implementations."""

from __future__ import annotations

import re
import shlex

from .._types import ExprType
from .._value import ExprValue
from .._errors import ExpressionError

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


# Unsupported regex features for cross-platform compatibility (Python re vs Rust regex)
# These are features in Python's re that don't exist or differ in Rust's regex crate
_UNSUPPORTED_SEQUENCES = [
    # Backreferences - not supported in Rust regex
    (r"\1", "backreferences"),
    (r"\2", "backreferences"),
    (r"\3", "backreferences"),
    (r"\4", "backreferences"),
    (r"\5", "backreferences"),
    (r"\6", "backreferences"),
    (r"\7", "backreferences"),
    (r"\8", "backreferences"),
    (r"\9", "backreferences"),
    # Lookahead/lookbehind - not supported in Rust regex
    ("(?=", "lookahead (?=...)"),
    ("(?!", "negative lookahead (?!...)"),
    ("(?<=", "lookbehind (?<=...)"),
    ("(?<!", "negative lookbehind (?<!...)"),
    # Conditional patterns and named backreferences - not supported in Rust regex
    ("(?(", "conditional patterns (?(...)...)"),
    ("(?P=", "named backreferences (?P=name)"),
    # \Z - Python uses \Z for end-of-string, Rust uses \z (different semantics)
    (r"\Z", r"end-of-string anchor \Z (use $ or \z in Rust-compatible patterns)"),
]


def _is_unescaped(pattern: str, pos: int) -> bool:
    """Check if position in pattern is not escaped (preceded by even number of backslashes)."""
    num_backslashes = 0
    i = pos - 1
    while i >= 0 and pattern[i] == "\\":
        num_backslashes += 1
        i -= 1
    return num_backslashes % 2 == 0


def _validate_regex_pattern(pattern: str) -> None:
    """Validate regex pattern uses only cross-platform compatible features."""
    if not pattern:
        raise ExpressionError("Empty regex pattern is not allowed")
    for seq, feature_name in _UNSUPPORTED_SEQUENCES:
        idx = 0
        while True:
            pos = pattern.find(seq, idx)
            if pos == -1:
                break
            if _is_unescaped(pattern, pos):
                raise ExpressionError(f"Unsupported regex feature: {feature_name}")
            idx = pos + 1


def _len_string(ev: Evaluator, s: ExprValue) -> ExprValue:
    return ExprValue(len(s.item()))


def _len_path(ev: Evaluator, p: ExprValue) -> ExprValue:
    return ExprValue(len(p.to_string()))


def _contains_string(ev: Evaluator, haystack: ExprValue, needle: ExprValue) -> ExprValue:
    """Check if needle is in haystack (substring test)."""
    haystack_str = haystack.item()
    needle_str = needle.item()
    ev._count_string_ops(len(haystack_str) + len(needle_str))
    return ExprValue(needle_str in haystack_str)


def _not_contains_string(ev: Evaluator, haystack: ExprValue, needle: ExprValue) -> ExprValue:
    """Check if needle is not in haystack (substring test)."""
    haystack_str = haystack.item()
    needle_str = needle.item()
    ev._count_string_ops(len(haystack_str) + len(needle_str))
    return ExprValue(needle_str not in haystack_str)


def _getitem_string(ev: Evaluator, s: ExprValue, index: ExprValue) -> ExprValue:
    """Get single character from string by index."""
    idx = index.item()
    s_str = s.item()
    if idx < 0:
        idx = len(s_str) + idx
    if idx < 0 or idx >= len(s_str):
        raise ExpressionError(
            f"Index {index.item()} out of bounds for string of length {len(s_str)}"
        )
    return ExprValue(s_str[idx])


def _slice_string(
    ev: Evaluator,
    s: ExprValue,
    start: ExprValue,
    stop: ExprValue,
    step: ExprValue,
) -> ExprValue:
    """Slice a string using Python slice semantics."""
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    start_val = start.item() if not start.is_null else None
    stop_val = stop.item() if not stop.is_null else None
    step_val = step.item() if not step.is_null else None
    if step_val == 0:
        raise ExpressionError("slice step cannot be zero")
    return ExprValue(s_str[start_val:stop_val:step_val])


def _upper(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.upper())


def _lower(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.lower())


def _strip(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.strip())


def _strip_chars(ev: Evaluator, s: ExprValue, chars: ExprValue) -> ExprValue:
    s_str = s.item()
    chars_str = chars.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.strip(chars_str))


def _startswith(ev: Evaluator, s: ExprValue, prefix: ExprValue) -> ExprValue:
    s_str = s.item()
    prefix_str = prefix.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.startswith(prefix_str))


def _endswith(ev: Evaluator, s: ExprValue, suffix: ExprValue) -> ExprValue:
    s_str = s.item()
    suffix_str = suffix.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.endswith(suffix_str))


def _replace(ev: Evaluator, s: ExprValue, old: ExprValue, new: ExprValue) -> ExprValue:
    s_str = s.item()
    old_str = old.item()
    new_str = new.item()
    if not old_str:
        raise ExpressionError("replace failed: empty old string")
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.replace(old_str, new_str))


def _split_whitespace(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    parts = s_str.split()
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(p) for p in parts],
    )


def _split(ev: Evaluator, s: ExprValue, sep: ExprValue) -> ExprValue:
    s_str = s.item()
    sep_str = sep.item()
    ev._count_string_ops(len(s_str))
    try:
        parts = s_str.split(sep_str)
    except ValueError as e:
        raise ExpressionError(f"split failed: {e}")
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(p) for p in parts],
    )


def _split_maxsplit(ev: Evaluator, s: ExprValue, sep: ExprValue, maxsplit: ExprValue) -> ExprValue:
    s_str = s.item()
    sep_str = sep.item()
    ev._count_string_ops(len(s_str))
    try:
        parts = s_str.split(sep_str, maxsplit.item())
    except ValueError as e:
        raise ExpressionError(f"split failed: {e}")
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(p) for p in parts],
    )


def _rsplit_whitespace(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    parts = s_str.rsplit()
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(p) for p in parts],
    )


def _rsplit(ev: Evaluator, s: ExprValue, sep: ExprValue) -> ExprValue:
    s_str = s.item()
    sep_str = sep.item()
    ev._count_string_ops(len(s_str))
    try:
        parts = s_str.rsplit(sep_str)
    except ValueError as e:
        raise ExpressionError(f"rsplit failed: {e}")
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(p) for p in parts],
    )


def _rsplit_maxsplit(ev: Evaluator, s: ExprValue, sep: ExprValue, maxsplit: ExprValue) -> ExprValue:
    s_str = s.item()
    sep_str = sep.item()
    ev._count_string_ops(len(s_str))
    try:
        parts = s_str.rsplit(sep_str, maxsplit.item())
    except ValueError as e:
        raise ExpressionError(f"rsplit failed: {e}")
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(p) for p in parts],
    )


def _check_string_result_size(ev: Evaluator, result_len: int) -> None:
    """Check if string result would exceed memory limit."""
    import sys

    result_size = sys.getsizeof("") + result_len  # Approximate
    if ev._current_memory + result_size > ev.memory_limit:
        raise ExpressionError(
            f"String operation would exceed memory limit "
            f"({ev._current_memory + result_size} > {ev.memory_limit} bytes)"
        )


def _zfill_string(ev: Evaluator, s: ExprValue, width: ExprValue) -> ExprValue:
    s_str = s.item()
    w = width.item()
    ev._count_string_ops(len(s_str))
    if w > len(s_str):
        _check_string_result_size(ev, w)
    return ExprValue(s_str.zfill(w))


def _zfill_int(ev: Evaluator, n: ExprValue, width: ExprValue) -> ExprValue:
    n_str = str(n.item())
    w = width.item()
    _check_string_result_size(ev, max(w, len(n_str)))
    return ExprValue(n_str.zfill(w))


def _zfill_float(ev: Evaluator, x: ExprValue, width: ExprValue) -> ExprValue:
    x_str = x.to_string()
    w = width.item()
    _check_string_result_size(ev, max(w, len(x_str)))
    return ExprValue(x_str.zfill(w))


def _repr_sh(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(shlex.quote(s_str))


def _capitalize(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.capitalize())


def _title(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.title())


def _lstrip(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.lstrip())


def _lstrip_chars(ev: Evaluator, s: ExprValue, chars: ExprValue) -> ExprValue:
    s_str = s.item()
    chars_str = chars.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.lstrip(chars_str))


def _rstrip(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.rstrip())


def _rstrip_chars(ev: Evaluator, s: ExprValue, chars: ExprValue) -> ExprValue:
    s_str = s.item()
    chars_str = chars.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.rstrip(chars_str))


def _isdigit(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.isdigit())


def _isalpha(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.isalpha())


def _isalnum(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.isalnum())


def _isspace(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.isspace())


def _isupper(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.isupper())


def _islower(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.islower())


def _isascii(ev: Evaluator, s: ExprValue) -> ExprValue:
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.isascii())


def _removeprefix(ev: Evaluator, s: ExprValue, prefix: ExprValue) -> ExprValue:
    s_str = s.item()
    prefix_str = prefix.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.removeprefix(prefix_str))


def _removesuffix(ev: Evaluator, s: ExprValue, suffix: ExprValue) -> ExprValue:
    s_str = s.item()
    suffix_str = suffix.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.removesuffix(suffix_str))


def _count(ev: Evaluator, s: ExprValue, sub: ExprValue) -> ExprValue:
    s_str = s.item()
    sub_str = sub.item()
    if not sub_str:
        raise ExpressionError("count failed: empty substring")
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.count(sub_str))


def _find(ev: Evaluator, s: ExprValue, sub: ExprValue) -> ExprValue:
    s_str = s.item()
    sub_str = sub.item()
    if not sub_str:
        raise ExpressionError("find failed: empty substring")
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.find(sub_str))


def _rfind(ev: Evaluator, s: ExprValue, sub: ExprValue) -> ExprValue:
    s_str = s.item()
    sub_str = sub.item()
    if not sub_str:
        raise ExpressionError("rfind failed: empty substring")
    ev._count_string_ops(len(s_str))
    return ExprValue(s_str.rfind(sub_str))


def _index(ev: Evaluator, s: ExprValue, sub: ExprValue) -> ExprValue:
    s_str = s.item()
    sub_str = sub.item()
    if not sub_str:
        raise ExpressionError("index failed: empty substring")
    ev._count_string_ops(len(s_str))
    idx = s_str.find(sub_str)
    if idx < 0:
        raise ExpressionError(f"index failed: substring {sub_str!r} not found")
    return ExprValue(idx)


def _rindex(ev: Evaluator, s: ExprValue, sub: ExprValue) -> ExprValue:
    s_str = s.item()
    sub_str = sub.item()
    if not sub_str:
        raise ExpressionError("rindex failed: empty substring")
    ev._count_string_ops(len(s_str))
    idx = s_str.rfind(sub_str)
    if idx < 0:
        raise ExpressionError(f"rindex failed: substring {sub_str!r} not found")
    return ExprValue(idx)


def _join(ev: Evaluator, items: ExprValue, sep: ExprValue) -> ExprValue:
    item_list = items.to_expr_value_list()
    ev._count_operations(len(item_list))
    sep_str = sep.item()
    strings = [v.item() for v in item_list]
    return ExprValue(sep_str.join(strings))


def _join_empty(ev: Evaluator, items: ExprValue, sep: ExprValue) -> ExprValue:
    return ExprValue("")


def _ljust(ev: Evaluator, s: ExprValue, width: ExprValue) -> ExprValue:
    s_str = s.item()
    w = width.item()
    ev._count_string_ops(len(s_str))
    if w > len(s_str):
        _check_string_result_size(ev, w)
    return ExprValue(s_str.ljust(w))


def _rjust(ev: Evaluator, s: ExprValue, width: ExprValue) -> ExprValue:
    s_str = s.item()
    w = width.item()
    ev._count_string_ops(len(s_str))
    if w > len(s_str):
        _check_string_result_size(ev, w)
    return ExprValue(s_str.rjust(w))


def _center(ev: Evaluator, s: ExprValue, width: ExprValue) -> ExprValue:
    s_str = s.item()
    w = width.item()
    ev._count_string_ops(len(s_str))
    if w > len(s_str):
        _check_string_result_size(ev, w)
    return ExprValue(s_str.center(w))


def _re_match(ev: Evaluator, s: ExprValue, pattern: ExprValue) -> ExprValue:
    """Match regex at START of string, return [full_match, group1, ...] or null."""
    s_str = s.item()
    pattern_str = pattern.item()
    ev._count_string_ops(len(s_str) + len(pattern_str))
    try:
        _validate_regex_pattern(pattern_str)
        match = re.match(pattern_str, s_str)
        if match is None:
            return ExprValue(None)
        return ExprValue([match.group(0)] + list(match.groups()))
    except re.error as e:
        raise ExpressionError(f"Invalid regex pattern: {e}")


def _re_search(ev: Evaluator, s: ExprValue, pattern: ExprValue) -> ExprValue:
    """Match regex ANYWHERE in string, return [full_match, group1, ...] or null."""
    s_str = s.item()
    pattern_str = pattern.item()
    ev._count_string_ops(len(s_str) + len(pattern_str))
    try:
        _validate_regex_pattern(pattern_str)
        match = re.search(pattern_str, s_str)
        if match is None:
            return ExprValue(None)
        return ExprValue([match.group(0)] + list(match.groups()))
    except re.error as e:
        raise ExpressionError(f"Invalid regex pattern: {e}")


def _re_findall(ev: Evaluator, s: ExprValue, pattern: ExprValue) -> ExprValue:
    """Find all non-overlapping matches.

    Returns:
        - list[string] of full matches if no capture groups
        - list[string] of captured values if exactly one capture group
        - list[list[string]] of group lists if multiple capture groups
    """
    s_str = s.item()
    pattern_str = pattern.item()
    ev._count_string_ops(len(s_str) + len(pattern_str))
    try:
        _validate_regex_pattern(pattern_str)
        matches = re.findall(pattern_str, s_str)
        # re.findall returns tuples when there are multiple groups
        if matches and isinstance(matches[0], tuple):
            return ExprValue([list(m) for m in matches])
        return ExprValue(matches)
    except re.error as e:
        raise ExpressionError(f"Invalid regex pattern: {e}")


def _validate_regex_replacement(repl: str) -> None:
    """Validate that replacement string contains no group references."""
    import re as _re

    if _re.search(r"(?<!\\)\\(?:\d|g<)", repl):
        raise ExpressionError(
            "Group references (\\1, \\g<1>) in replacement strings are not supported"
        )
    if _re.search(r"(?<!\$)\$(?:\d|\{)", repl):
        raise ExpressionError(
            "Group references ($1, ${1}) in replacement strings are not supported"
        )


def _re_replace(
    ev: Evaluator, s: ExprValue, pattern: ExprValue, replacement: ExprValue
) -> ExprValue:
    s_str = s.item()
    pattern_str = pattern.item()
    replacement_str = replacement.item()
    ev._count_string_ops(len(s_str) + len(pattern_str) + len(replacement_str))
    try:
        _validate_regex_pattern(pattern_str)
        _validate_regex_replacement(replacement_str)
        result = re.sub(pattern_str, replacement_str, s_str)
        return ExprValue(result)
    except re.error as e:
        raise ExpressionError(f"Invalid regex pattern: {e}")


def _re_escape(ev: Evaluator, s: ExprValue) -> ExprValue:
    """Escape regex metacharacters for literal matching."""
    s_str = s.item()
    ev._count_string_ops(len(s_str))
    return ExprValue(re.escape(s_str))


def _re_split(ev: Evaluator, s: ExprValue, pattern: ExprValue) -> ExprValue:
    """Split string by regex pattern."""
    s_str = s.item()
    pattern_str = pattern.item()
    ev._count_string_ops(len(s_str) + len(pattern_str))
    try:
        _validate_regex_pattern(pattern_str)
        parts = re.split(pattern_str, s_str)
        return ExprValue._create(ExprType.LIST_STRING, list_value=[ExprValue(p) for p in parts])
    except re.error as e:
        raise ExpressionError(f"Invalid regex pattern: {e}")


def _re_split_maxsplit(
    ev: Evaluator, s: ExprValue, pattern: ExprValue, maxsplit: ExprValue
) -> ExprValue:
    """Split string by regex pattern, at most maxsplit times."""
    s_str = s.item()
    pattern_str = pattern.item()
    ev._count_string_ops(len(s_str) + len(pattern_str))
    try:
        _validate_regex_pattern(pattern_str)
        parts = re.split(pattern_str, s_str, maxsplit=maxsplit.item())
        return ExprValue._create(ExprType.LIST_STRING, list_value=[ExprValue(p) for p in parts])
    except re.error as e:
        raise ExpressionError(f"Invalid regex pattern: {e}")
