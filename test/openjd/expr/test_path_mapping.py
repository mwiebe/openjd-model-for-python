# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for PathMappingRule."""

import os
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from openjd.expr import PathMappingRule, PathFormat, ExprProfile, HostContext


class TestPathMappingRuleFromPosix:
    """Tests for mapping rules with POSIX source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared/file.txt")
        assert matched is True
        assert result == dest + os.sep + "file.txt"

    def test_exact_match(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared")
        assert matched is True
        assert result == str(dest)

    def test_no_match_different_path(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/other/path/file.txt")
        assert matched is False
        assert result == "/other/path/file.txt"

    def test_no_match_same_prefix(self, tmp_path) -> None:
        """path mapping operates on the parts, not with string prefixes"""
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared2/file.txt")
        assert matched is False
        assert result == "/mnt/shared2/file.txt"


class TestPathMappingRuleFromWindows:
    """Tests for mapping rules with WINDOWS source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\file.txt")
        assert matched is True
        assert result == dest + os.sep + "file.txt"

    def test_exact_match(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects")
        assert matched is True
        assert result == str(dest)

    def test_no_match_different_path(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="D:\\other\\file.txt")
        assert matched is False
        assert result == "D:\\other\\file.txt"

    def test_no_match_same_prefix(self, tmp_path) -> None:
        """path mapping operates on the parts, not with string prefixes"""
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects2\\file.txt")
        assert matched is False
        assert result == "C:\\projects2\\file.txt"


class TestPathMappingRuleFromUri:
    """Tests for mapping rules with URI source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "local" / "assets")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://my-bucket/assets/teapot.obj")
        assert matched is True
        assert result == dest + os.sep + "teapot.obj"

    def test_match_nested_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/a/b/c.txt")
        assert matched is True
        assert result == dest + os.sep + os.sep.join(["a", "b", "c.txt"])

    def test_exact_match(self, tmp_path) -> None:
        dest = str(tmp_path / "local" / "assets")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://my-bucket/assets")
        assert matched is True
        assert result == str(dest)

    def test_no_match_different_bucket(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://other-bucket/assets/file.obj")
        assert matched is False
        assert result == "s3://other-bucket/assets/file.obj"

    def test_no_match_prefix_overlap(self, tmp_path) -> None:
        """URI matching is on path boundaries, not string prefixes."""
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/dir",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/directory/file.txt")
        assert matched is False
        assert result == "s3://bucket/directory/file.txt"

    def test_no_match_different_scheme(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="https://bucket/assets/file.txt")
        assert matched is False
        assert result == "https://bucket/assets/file.txt"

    def test_no_match_filesystem_path(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/local/file.txt")
        assert matched is False
        assert result == "/mnt/local/file.txt"

    def test_https_scheme(self, tmp_path) -> None:
        dest = tmp_path / "cache"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="https://example.com/models",
            destination_path=dest,
        )
        matched, result = rule.apply(path="https://example.com/models/scene.obj")
        assert matched is True
        assert result == str(dest / "scene.obj")

    def test_custom_scheme(self, tmp_path) -> None:
        dest = tmp_path / "mount"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="fsx://vol-123/data",
            destination_path=dest,
        )
        matched, result = rule.apply(path="fsx://vol-123/data/file.bin")
        assert matched is True
        assert result == str(dest / "file.bin")


class TestPathMappingRuleValidation:
    """Tests for from_dict validation shared across formats."""


class TestPathMappingRuleSerialization:
    """Tests for from_dict/to_dict serialization."""

    def test_from_dict_posix(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "POSIX",
                "source_path": "/mnt/shared",
                "destination_path": str(tmp_path / "newprefix"),
            }
        )
        assert rule.source_path_format == PathFormat.POSIX
        assert rule.source_path == "/mnt/shared"
        assert rule.destination_path == str(tmp_path / "newprefix")

    def test_from_dict_windows(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "WINDOWS",
                "source_path": "C:\\projects",
                "destination_path": str(tmp_path / "mnt" / "projects"),
            }
        )
        assert rule.source_path_format == PathFormat.WINDOWS
        assert rule.source_path == "C:\\projects"

    def test_from_dict_uri(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "URI",
                "source_path": "s3://bucket/assets",
                "destination_path": str(tmp_path / "local"),
            }
        )
        assert rule.source_path_format == PathFormat.URI
        assert rule.source_path == "s3://bucket/assets"

    def test_from_dict_case_insensitive(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "posix",
                "source_path": "/mnt/shared",
                "destination_path": str(tmp_path),
            }
        )
        assert rule.source_path_format == PathFormat.POSIX

    def test_from_dict_empty(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            PathMappingRule.from_dict({})

    def test_from_dict_missing_field(self) -> None:
        with pytest.raises(ValueError, match="requires"):
            PathMappingRule.from_dict({"source_path_format": "POSIX", "source_path": "/mnt"})

    def test_to_dict_posix(self, tmp_path) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=str(tmp_path / "newprefix"),
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "POSIX"
        assert d["source_path"] == "/mnt/shared"
        assert d["destination_path"] == str(tmp_path / "newprefix")

    def test_to_dict_windows(self) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path="D:\\local",
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "WINDOWS"
        assert d["source_path"] == "C:\\projects"

    def test_to_dict_uri(self) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path="/local/cache",
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "URI"
        assert d["source_path"] == "s3://bucket/assets"

    def test_roundtrip(self, tmp_path) -> None:
        original = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=str(tmp_path / "local"),
        )
        restored = PathMappingRule.from_dict(original.to_dict())
        assert restored.source_path_format == original.source_path_format
        assert restored.source_path == original.source_path
        assert restored.destination_path == original.destination_path


class TestTrailingSlash:
    """Tests that trailing separators are preserved after mapping."""

    def test_posix_trailing_slash(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared/dir/")
        assert matched is True
        assert result.endswith("/") or result.endswith(os.sep)

    def test_windows_trailing_backslash(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\subdir\\")
        assert matched is True
        assert result.endswith("\\") or result.endswith(os.sep)

    def test_windows_trailing_forward_slash(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\subdir/")
        assert matched is True
        assert result.endswith("/") or result.endswith(os.sep) or result.endswith("\\")


class TestFormatMismatch:
    """Tests that constructor rejects wrong path types for the format."""

    def test_posix_rejects_windows_path(self) -> None:
        with pytest.raises(TypeError, match="PurePosixPath"):
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PureWindowsPath("C:\\path"),
                destination_path="/dest",
            )

    def test_windows_rejects_posix_path(self) -> None:
        with pytest.raises(TypeError, match="PureWindowsPath"):
            PathMappingRule(
                source_path_format=PathFormat.WINDOWS,
                source_path=PurePosixPath("/posix/path"),
                destination_path="/dest",
            )

    def test_uri_rejects_purepath(self) -> None:
        with pytest.raises(TypeError, match="str"):
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path=PurePosixPath("/mnt/shared"),
                destination_path="/dest",
            )


class TestFromDictValidation:
    """Tests for from_dict edge cases."""

    def test_from_dict_extra_field_rejected(self) -> None:
        """Extra fields raise ``ValueError`` matching the pure-Python
        reference's ``Unsupported fields ...`` contract."""
        with pytest.raises(ValueError, match="Unsupported fields"):
            PathMappingRule.from_dict(
                {
                    "source_path_format": "POSIX",
                    "source_path": "/mnt/shared",
                    "destination_path": "/local",
                    "extra": "field",
                }
            )

    def test_from_dict_multiple_extra_fields_in_message(self) -> None:
        """All offending field names appear in the error message,
        sorted for determinism."""
        with pytest.raises(ValueError) as exc_info:
            PathMappingRule.from_dict(
                {
                    "source_path_format": "POSIX",
                    "source_path": "/mnt/shared",
                    "destination_path": "/local",
                    "zeta": 1,
                    "alpha": 2,
                }
            )
        assert "'alpha'" in str(exc_info.value)
        assert "'zeta'" in str(exc_info.value)
        # Sorted: alpha before zeta.
        assert str(exc_info.value).index("'alpha'") < str(exc_info.value).index("'zeta'")


class TestPathMappingViaProfile:
    """Tests that path-mapping rules registered on an :class:`ExprProfile`
    via :meth:`HostContext.with_rules` flow through every evaluation entry
    point.

    These exercise the canonical wiring for path mapping: a caller builds
    an :class:`ExprProfile` with rules attached and passes it as
    ``profile=`` rather than using a per-call ``path_mapping_rules=``
    kwarg. The profile-based plumbing is shared across
    :func:`evaluate_expression`, :meth:`ParsedExpression.evaluate`,
    :meth:`FormatString.resolve_string`, and :meth:`FormatString.resolve`.
    """

    @staticmethod
    def _profile_with_rule() -> ExprProfile:
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path="/local/cache",
        )
        return ExprProfile().with_host_context(HostContext.with_rules([rule]))

    def test_parsed_expression_evaluate_applies_rules(self) -> None:
        from openjd.expr import parse_expression

        parsed = parse_expression("apply_path_mapping('/mnt/shared/file.exr')")
        result = parsed.evaluate(profile=self._profile_with_rule())
        assert result.item() == "/local/cache/file.exr"

    def test_format_string_resolve_string_applies_rules(self) -> None:
        from openjd.expr import FormatString, SymbolTable

        fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
        result = fs.resolve_string(SymbolTable({}), profile=self._profile_with_rule())
        assert result == "/local/cache/file.exr"

    def test_format_string_resolve_applies_rules(self) -> None:
        from openjd.expr import FormatString, SymbolTable

        fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
        result = fs.resolve(SymbolTable({}), profile=self._profile_with_rule())
        assert result.item() == "/local/cache/file.exr"
