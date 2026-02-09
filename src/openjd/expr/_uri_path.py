# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""URI-aware path operations for the path type.

When a path value contains a URI (scheme://authority/path), path operations
use this module instead of pathlib. The scheme+authority prefix is preserved
as an opaque root, and the path portion is not normalized — consecutive
slashes, `.`, and `..` segments are preserved verbatim.
"""

from __future__ import annotations

import re
from typing import Optional

_URI_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*://[^/]*)(/.*)$")
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def is_uri(path_str: str) -> bool:
    """Return True if path_str is a URI (has a scheme:// prefix)."""
    return _URI_SCHEME_RE.match(path_str) is not None


def split_uri(path_str: str) -> Optional[tuple[str, str]]:
    """If path_str is a URI, return (prefix, path_portion). Otherwise None.

    The prefix is scheme://authority (no trailing slash).
    The path_portion starts with / (e.g., "/dir/file.txt").
    For bare URIs like "s3://bucket" with no path, returns ("s3://bucket", "").
    """
    m = _URI_RE.match(path_str)
    if m:
        return m.group(1), m.group(2)
    # Check for bare URI with no path portion (e.g., "s3://bucket")
    if _URI_SCHEME_RE.match(path_str) is not None:
        return path_str, ""
    return None


def uri_parts(path_str: str) -> list[str]:
    """Return parts for a URI path.

    The first element is scheme://authority. Remaining elements are the
    path portion split by '/'. The leading '/' is consumed by the split.
    """
    result = split_uri(path_str)
    if result is None:
        raise ValueError(f"Not a URI: {path_str}")
    prefix, path_portion = result
    if not path_portion:
        return [prefix]
    # Split "/a/b/c" -> ["", "a", "b", "c"], drop the leading empty string
    segments = path_portion.split("/")
    return [prefix] + segments[1:]


def uri_name(path_str: str) -> str:
    """Return the final component of a URI path."""
    parts = uri_parts(path_str)
    if len(parts) <= 1:
        return ""
    return parts[-1]


def uri_parent(path_str: str) -> str:
    """Return the parent of a URI path."""
    parts = uri_parts(path_str)
    if len(parts) <= 1:
        return parts[0] if parts else path_str
    return parts[0] + "/" + "/".join(parts[1:-1]) if len(parts) > 2 else parts[0]


def uri_suffix(path_str: str) -> str:
    """Return the last file extension of the final component."""
    name = uri_name(path_str)
    dot = name.rfind(".")
    if dot <= 0:
        return ""
    return name[dot:]


def uri_suffixes(path_str: str) -> list[str]:
    """Return all file extensions of the final component."""
    name = uri_name(path_str)
    # Find first dot (skip leading dot)
    parts = name.split(".")
    if len(parts) <= 1:
        return []
    return ["." + p for p in parts[1:]]


def uri_stem(path_str: str) -> str:
    """Return the final component without the last suffix."""
    name = uri_name(path_str)
    dot = name.rfind(".")
    if dot <= 0:
        return name
    return name[:dot]


def uri_join(path_str: str, child_parts: list[str]) -> str:
    """Join a URI path with child parts using '/'.

    A trailing empty part on the left side (from a trailing slash) is removed
    before appending, matching PurePath's join behavior.
    """
    parts = uri_parts(path_str)
    if len(parts) > 1 and parts[-1] == "":
        parts = parts[:-1]
    return uri_from_parts(parts + child_parts)


def uri_from_parts(parts: list[str]) -> str:
    """Reconstruct a URI from parts (first element is scheme://authority)."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[0] + "/" + "/".join(parts[1:])
