# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Path mapping rule for expression evaluation."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from os import name as os_name
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Tuple, Union

from ._uri_path import is_uri


class PathFormat(str, Enum):
    POSIX = "POSIX"
    WINDOWS = "WINDOWS"
    URI = "URI"


@dataclass(frozen=True)
class PathMappingRule:
    """A rule for mapping paths from one location to another.

    Used by apply_path_mapping() to transform paths, typically for
    cross-platform job submission scenarios.
    """

    source_path_format: PathFormat
    source_path: Union[PurePath, str]  # str for URI format
    destination_path: PurePath

    def __init__(
        self,
        *,
        source_path_format: PathFormat,
        source_path: Union[PurePath, str],
        destination_path: PurePath,
    ):
        if source_path_format == PathFormat.URI:
            if not isinstance(source_path, str) or not is_uri(source_path):
                raise ValueError(
                    "Path mapping rule with URI source_path_format requires a URI string source_path"
                )
        elif source_path_format == PathFormat.POSIX:
            if not isinstance(source_path, PurePosixPath):
                raise ValueError(
                    "Path mapping rule source_path_format does not match source_path type"
                )
        else:
            if not isinstance(source_path, PureWindowsPath):
                raise ValueError(
                    "Path mapping rule source_path_format does not match source_path type"
                )

        # This roundabout way can set the attributes of a frozen dataclass
        object.__setattr__(self, "source_path_format", source_path_format)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "destination_path", destination_path)

    @staticmethod
    def from_dict(rule: dict[str, str]) -> "PathMappingRule":
        """Builds a PathMappingRule from a dictionary representation
        with strings as values."""
        if not rule:
            raise ValueError("Empty path mapping rule")

        field_names = [field.name for field in fields(PathMappingRule)]
        for name in field_names:
            if name not in rule:
                raise ValueError(f"Path mapping rule requires the following fields: {field_names}")

        source_path_format = PathFormat(rule["source_path_format"].upper())
        source_path: Union[PurePath, str]
        if source_path_format == PathFormat.URI:
            source_path = rule["source_path"]
        elif source_path_format == PathFormat.POSIX:
            source_path = PurePosixPath(rule["source_path"])
        else:
            source_path = PureWindowsPath(rule["source_path"])
        destination_path = PurePath(rule["destination_path"])

        unsupported_fields = set(rule.keys()) - set(field_names)
        if unsupported_fields:
            raise ValueError(
                f"Unsupported fields for constructing path mapping rule: {unsupported_fields}"
            )

        return PathMappingRule(
            source_path_format=source_path_format,
            source_path=source_path,
            destination_path=destination_path,
        )

    def to_dict(self) -> dict[str, str]:
        """Returns a dictionary representation of the PathMappingRule."""
        return {
            "source_path_format": self.source_path_format.name,
            "source_path": str(self.source_path),
            "destination_path": str(self.destination_path),
        }

    def apply(self, *, path: str) -> Tuple[bool, str]:
        """Applies the path mapping rule on the given path, if it matches the rule.
        Does not collapse ".." since symbolic paths could be used.

        Returns: tuple[bool, str] - indicating if the path matched the rule and the resulting
        mapped path. If it doesn't match, then it returns the original path unmodified.
        """
        if self.source_path_format == PathFormat.URI:
            return self._apply_uri(path)

        # After the URI early return, source_path is always PurePath
        source_path: PurePath = self.source_path  # type: ignore[assignment]

        pure_path: PurePath
        if self.source_path_format == PathFormat.POSIX:
            pure_path = PurePosixPath(path)
        else:
            pure_path = PureWindowsPath(path)

        if not pure_path.is_relative_to(source_path):
            return False, path

        remapped_parts = self.destination_path.parts + pure_path.parts[len(source_path.parts) :]
        if os_name == "posix":
            result = str(PurePosixPath(*remapped_parts))
            if self._has_trailing_slash(self.source_path_format, path):
                result += "/"
        else:
            result = str(PureWindowsPath(*remapped_parts))
            if self._has_trailing_slash(self.source_path_format, path):
                result += "\\"

        return True, result

    def _apply_uri(self, path: str) -> Tuple[bool, str]:
        """Apply URI path mapping using string prefix matching."""
        source = str(self.source_path)
        if not path.startswith(source):
            return False, path
        # The remainder after the source prefix
        remainder = path[len(source) :]
        # remainder should be empty or start with /
        if remainder and not remainder.startswith("/"):
            return False, path
        # Split remainder into parts (drop leading /)
        if remainder:
            child_parts = remainder[1:].split("/")
        else:
            child_parts = []
        remapped_parts = self.destination_path.parts + tuple(child_parts)
        if os_name == "posix":
            result = (
                str(PurePosixPath(*remapped_parts))
                if remapped_parts
                else str(self.destination_path)
            )
            if path.endswith("/"):
                result += "/"
        else:
            result = (
                str(PureWindowsPath(*remapped_parts))
                if remapped_parts
                else str(self.destination_path)
            )
            if path.endswith("/"):
                result += "\\"
        return True, result

    def _has_trailing_slash(self, path_format: PathFormat, path: str) -> bool:
        if path_format == PathFormat.POSIX:
            return path.endswith("/")
        else:
            # On Windows, both a trailing \ and / count
            return path.endswith("\\") or path.endswith("/")
