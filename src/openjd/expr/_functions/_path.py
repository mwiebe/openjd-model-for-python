# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Path function implementations."""

from __future__ import annotations

import re
import typing

from .._types import ExprType
from .._value import ExprValue
from .._errors import ExpressionError
from .._uri_path import (
    is_uri,
    uri_name,
    uri_stem,
    uri_suffix,
    uri_suffixes,
    uri_parent,
    uri_parts,
    uri_join,
    uri_from_parts,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._eval import Evaluator


def _path_name(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue(uri_name(p_str))
    return ExprValue(ev.pure_path(p_str).name)


def _path_stem(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue(uri_stem(p_str))
    return ExprValue(ev.pure_path(p_str).stem)


def _path_suffix(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue(uri_suffix(p_str))
    return ExprValue(ev.pure_path(p_str).suffix)


def _path_parent(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ev.make_path_value(uri_parent(p_str))
    return ev.make_path_value(str(ev.pure_path(p_str).parent))


def _path_from_string(ev: Evaluator, s: ExprValue) -> ExprValue:
    ev._count_string_ops(len(s.item()))
    s_str = s.item()
    if is_uri(s_str):
        return ev.make_path_value(s_str)
    return ev.make_path_value(str(ev.pure_path(s_str)))


def _path_from_list(ev: Evaluator, parts: ExprValue) -> ExprValue:
    """Construct a path from a list of path components."""
    items = parts.to_expr_value_list()
    if not items:
        return ev.make_path_value("")
    ev._count_operations(len(items))
    part_strings = [p.item() for p in items]
    # If first part is a URI prefix, use URI join
    if is_uri(part_strings[0]):
        return ev.make_path_value(uri_from_parts(part_strings))
    # Filesystem path
    base = ev.pure_path(part_strings[0])
    for part in part_strings[1:]:
        base = base / part
    return ev.make_path_value(str(base))


def _with_suffix(ev: Evaluator, p: ExprValue, suffix: ExprValue) -> ExprValue:
    p_str = p.to_string()
    suffix_str = suffix.to_string()
    ev._count_string_ops(len(p_str) + len(suffix_str))
    if is_uri(p_str):
        name = uri_name(p_str)
        parent = uri_parent(p_str)
        dot = name.rfind(".")
        if dot <= 0:
            new_name = name + suffix_str
        else:
            new_name = name[:dot] + suffix_str
        return ev.make_path_value(parent + "/" + new_name)
    p_path = ev.pure_path(p_str)
    try:
        new_path = p_path.with_suffix(suffix_str)
    except ValueError as e:
        raise ExpressionError(f"with_suffix failed: {e}")
    return ev.make_path_value(str(new_path))


def _path_join_path(ev: Evaluator, p: ExprValue, child: ExprValue) -> ExprValue:
    p_str = p.to_string()
    child_str = child.to_string()
    ev._count_string_ops(len(p_str) + len(child_str))
    if is_uri(p_str):
        if is_uri(child_str):
            return ev.make_path_value(child_str)
        child_path = ev.pure_path(child_str)
        if child_path.is_absolute():
            return ev.make_path_value(str(child_path))
        return ev.make_path_value(uri_join(p_str, list(child_path.parts)))
    joined_path = ev.pure_path(p_str) / child_str
    return ev.make_path_value(str(joined_path))


def _path_suffixes(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue._create(
            ExprType.LIST_STRING,
            list_value=[ExprValue(sf) for sf in uri_suffixes(p_str)],
        )
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(sf) for sf in ev.pure_path(p_str).suffixes],
    )


def _path_parts(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue._create(
            ExprType.LIST_STRING,
            list_value=[ExprValue(part) for part in uri_parts(p_str)],
        )
    return ExprValue._create(
        ExprType.LIST_STRING,
        list_value=[ExprValue(part) for part in ev.pure_path(p_str).parts],
    )


def _with_name(ev: Evaluator, p: ExprValue, name: ExprValue) -> ExprValue:
    p_str = p.to_string()
    name_str = name.to_string()
    ev._count_string_ops(len(p_str) + len(name_str))
    if is_uri(p_str):
        parent = uri_parent(p_str)
        parts = uri_parts(parent)
        if len(parts) <= 1:
            return ev.make_path_value(parts[0] + "/" + name_str)
        return ev.make_path_value(parent + "/" + name_str)
    path = ev.pure_path(p_str)
    try:
        new_path = path.with_name(name_str)
    except ValueError as e:
        raise ExpressionError(f"with_name failed: {e}")
    return ev.make_path_value(str(new_path))


def _with_stem(ev: Evaluator, p: ExprValue, stem: ExprValue) -> ExprValue:
    p_str = p.to_string()
    stem_str = stem.to_string()
    ev._count_string_ops(len(p_str) + len(stem_str))
    if is_uri(p_str):
        suf = uri_suffix(p_str)
        parent = uri_parent(p_str)
        new_name = stem_str + suf
        parts = uri_parts(parent)
        if len(parts) <= 1:
            return ev.make_path_value(parts[0] + "/" + new_name)
        return ev.make_path_value(parent + "/" + new_name)
    p_path = ev.pure_path(p_str)
    suffix = p_path.suffix
    new_path = p_path.parent / (stem_str + suffix)
    return ev.make_path_value(str(new_path))


def _as_posix(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue(p_str)  # URIs already use forward slashes
    return ExprValue(ev.pure_path(p_str).as_posix())


def _is_absolute(ev: Evaluator, p: ExprValue) -> ExprValue:
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    if is_uri(p_str):
        return ExprValue(True)  # URIs are always absolute
    return ExprValue(ev.pure_path(p_str).is_absolute())


def _is_relative_to(ev: Evaluator, p: ExprValue, other: ExprValue) -> ExprValue:
    p_str = p.to_string()
    other_str = other.to_string()
    ev._count_string_ops(len(p_str) + len(other_str))
    if is_uri(p_str):
        if not is_uri(other_str):
            return ExprValue(False)
        # URI: check if path starts with other's full prefix
        return ExprValue(p_str == other_str or p_str.startswith(other_str.rstrip("/") + "/"))
    if is_uri(other_str):
        return ExprValue(False)
    try:
        return ExprValue(ev.pure_path(p_str).is_relative_to(ev.pure_path(other_str)))
    except TypeError:
        return ExprValue(False)


def _relative_to(ev: Evaluator, p: ExprValue, other: ExprValue) -> ExprValue:
    p_str = p.to_string()
    other_str = other.to_string()
    ev._count_string_ops(len(p_str) + len(other_str))
    if is_uri(p_str):
        if not is_uri(other_str):
            raise ExpressionError(
                "relative_to failed: cannot compute relative path from URI to non-URI"
            )
        base = other_str.rstrip("/") + "/"
        if p_str == other_str or p_str == other_str.rstrip("/"):
            return ev.make_path_value(".")
        if not p_str.startswith(base):
            raise ExpressionError(f"relative_to failed: '{p_str}' is not relative to '{other_str}'")
        return ev.make_path_value(p_str[len(base) :])
    if is_uri(other_str):
        raise ExpressionError(
            "relative_to failed: cannot compute relative path from filesystem path to URI"
        )
    try:
        result = ev.pure_path(p_str).relative_to(ev.pure_path(other_str))
        return ev.make_path_value(str(result))
    except ValueError:
        raise ExpressionError(f"relative_to failed: '{p_str}' is not relative to '{other_str}'")


def _with_number_path(ev: Evaluator, p: ExprValue, num: ExprValue) -> ExprValue:
    """Replace frame number placeholder in path with given number."""
    p_str = p.to_string()
    ev._count_string_ops(len(p_str))
    result = _with_number_impl(ev, p_str, num.item())
    return ev.make_path_value(result)


def _with_number_string(ev: Evaluator, s: ExprValue, num: ExprValue) -> ExprValue:
    """String version of with_number."""
    s_str = s.to_string()
    ev._count_string_ops(len(s_str))
    result = _with_number_impl(ev, s_str, num.item())
    return ExprValue(result)


def _with_number_impl(ev: Evaluator, path_str: str, n: int) -> str:
    """Core implementation for with_number."""

    if is_uri(path_str):
        name = uri_name(path_str)
        parent = uri_parent(path_str)
        new_name = _replace_number_in_name(name, n)
        if parent == path_str:
            # No path portion
            return parent + "/" + new_name
        parts = uri_parts(parent)
        if len(parts) <= 1:
            return parts[0] + "/" + new_name
        return parent + "/" + new_name
    else:
        path = ev.pure_path(path_str)
        name = path.name
        new_name = _replace_number_in_name(name, n)
        new_path = path.parent / new_name
        return str(new_path)


def _replace_number_in_name(name: str, n: int) -> str:
    """Replace frame number pattern in a filename.

    Searches the stem from the end for printf, hash, and digit patterns.
    Whichever pattern appears last (rightmost) in the stem is replaced.
    """

    # Split into stem and suffix (last dot, matching pathlib's .stem/.suffix)
    if "." in name:
        idx = name.rindex(".")
        stem, suffix = name[:idx], name[idx:]
    else:
        stem, suffix = name, ""

    _MAX_PADDING_WIDTH = 32

    def _format_printf(m: re.Match) -> str:
        width = int(m.group(1)) if m.group(1) else 0
        if width > _MAX_PADDING_WIDTH:
            raise ExpressionError(
                f"with_number: padding width {width} exceeds maximum of {_MAX_PADDING_WIDTH}"
            )
        return str(n).zfill(width) if width else str(n)

    def _format_hash(m: re.Match) -> str:
        width = len(m.group())
        if width > _MAX_PADDING_WIDTH:
            raise ExpressionError(
                f"with_number: padding width {width} exceeds maximum of {_MAX_PADDING_WIDTH}"
            )
        return str(n).zfill(width)

    def _format_digits(m: re.Match) -> str:
        return str(n).zfill(len(m.group()))

    # Find the last match of each pattern type
    candidates: list[tuple[re.Match, typing.Callable]] = []
    for pattern, formatter in [
        (r"%(\d*)d", _format_printf),
        (r"#+", _format_hash),
        (r"\d+$", _format_digits),
    ]:
        matches = list(re.finditer(pattern, stem))
        if matches:
            candidates.append((matches[-1], formatter))

    if candidates:
        # Pick the rightmost match across all pattern types
        best_match, best_formatter = max(candidates, key=lambda c: c[0].end())
        replacement = best_formatter(best_match)
        return stem[: best_match.start()] + replacement + stem[best_match.end() :] + suffix

    # No pattern found, append frame number to stem
    return stem + "_" + str(n).zfill(4) + suffix


def _apply_path_mapping(ev: "Evaluator", s: ExprValue) -> ExprValue:
    """Apply path mapping rules to a string path."""
    if not ev.library.host_context_enabled:
        raise ExpressionError(
            "apply_path_mapping is only available in host context. "
            "Call library.with_host_context() to enable it."
        )
    s_str = s.to_string()
    ev._count_string_ops(len(s_str))
    rules = ev.library.path_mapping_rules
    if rules is None:
        return ev.make_path_value(s_str)
    for rule in rules:
        matched, result = rule.apply(path=s_str)
        if matched:
            return ev.make_path_value(result)
    return ev.make_path_value(s_str)
