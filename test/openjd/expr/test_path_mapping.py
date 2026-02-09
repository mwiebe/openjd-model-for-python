# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for PathMappingRule."""

import os
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from openjd.expr import PathMappingRule, PathFormat


class TestPathMappingRuleFromPosix:
    """Tests for mapping rules with POSIX source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PurePosixPath("/mnt/shared"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared/file.txt")
        assert matched is True
        assert result == str(dest / "file.txt")

    def test_exact_match(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PurePosixPath("/mnt/shared"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared")
        assert matched is True
        assert result == str(dest)

    def test_trailing_slash_preserved(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PurePosixPath("/mnt/shared"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared/dir/")
        assert matched is True
        assert result == str(dest / "dir") + os.sep

    def test_no_match_different_path(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PurePosixPath("/mnt/shared"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="/other/path/file.txt")
        assert matched is False
        assert result == "/other/path/file.txt"

    def test_no_match_same_prefix(self, tmp_path) -> None:
        """path mapping operates on the parts, not with string prefixes"""
        dest = tmp_path / "newprefix"
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PurePosixPath("/mnt/shared"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared2/file.txt")
        assert matched is False
        assert result == "/mnt/shared2/file.txt"

    def test_format_mismatch_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PureWindowsPath("C:\\path"),
                destination_path=tmp_path / "dest",
            )

    def test_from_dict(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "POSIX",
                "source_path": "/mnt/shared",
                "destination_path": str(dest),
            }
        )
        assert rule.source_path_format == PathFormat.POSIX
        assert rule.source_path == PurePosixPath("/mnt/shared")
        assert rule.destination_path == dest

    def test_to_dict(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path=PurePosixPath("/mnt/shared"),
            destination_path=dest,
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "POSIX"
        assert d["source_path"] == "/mnt/shared"
        assert d["destination_path"] == str(dest)


class TestPathMappingRuleFromWindows:
    """Tests for mapping rules with WINDOWS source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\file.txt")
        assert matched is True
        assert result == str(dest / "file.txt")

    def test_exact_match(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects")
        assert matched is True
        assert result == str(dest)

    def test_trailing_backslash_preserved(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\subdir\\")
        assert matched is True
        assert result == str(dest / "subdir") + os.sep

    def test_trailing_forward_slash_preserved(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\subdir/")
        assert matched is True
        assert result == str(dest / "subdir") + os.sep

    def test_no_match_different_path(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="D:\\other\\file.txt")
        assert matched is False
        assert result == "D:\\other\\file.txt"

    def test_no_match_same_prefix(self, tmp_path) -> None:
        """path mapping operates on the parts, not with string prefixes"""
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects2\\file.txt")
        assert matched is False
        assert result == "C:\\projects2\\file.txt"

    def test_format_mismatch_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            PathMappingRule(
                source_path_format=PathFormat.WINDOWS,
                source_path=PurePosixPath("/posix/path"),
                destination_path=tmp_path / "dest",
            )

    def test_from_dict(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "WINDOWS",
                "source_path": "C:\\projects",
                "destination_path": str(dest),
            }
        )
        assert rule.source_path_format == PathFormat.WINDOWS
        assert isinstance(rule.source_path, PureWindowsPath)
        assert rule.destination_path == dest

    def test_to_dict(self, tmp_path) -> None:
        dest = tmp_path / "mnt" / "projects"
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath("C:\\projects"),
            destination_path=dest,
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "WINDOWS"
        assert d["source_path"] == str(PureWindowsPath("C:\\projects"))
        assert d["destination_path"] == str(dest)


class TestPathMappingRuleFromUri:
    """Tests for mapping rules with URI source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = tmp_path / "local" / "assets"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://my-bucket/assets/teapot.obj")
        assert matched is True
        assert result == str(dest / "teapot.obj")

    def test_match_nested_subpath(self, tmp_path) -> None:
        dest = tmp_path / "local"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/a/b/c.txt")
        assert matched is True
        assert result == str(dest / "a" / "b" / "c.txt")

    def test_exact_match(self, tmp_path) -> None:
        dest = tmp_path / "local" / "assets"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://my-bucket/assets")
        assert matched is True
        assert result == str(dest)

    def test_trailing_slash_preserved(self, tmp_path) -> None:
        dest = tmp_path / "local"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/dir/")
        assert matched is True
        assert result == str(dest / "dir") + os.sep

    def test_no_match_different_bucket(self, tmp_path) -> None:
        dest = tmp_path / "local"
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
        dest = tmp_path / "local"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/dir",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/directory/file.txt")
        assert matched is False
        assert result == "s3://bucket/directory/file.txt"

    def test_no_match_different_scheme(self, tmp_path) -> None:
        dest = tmp_path / "local"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="https://bucket/assets/file.txt")
        assert matched is False
        assert result == "https://bucket/assets/file.txt"

    def test_no_match_filesystem_path(self, tmp_path) -> None:
        dest = tmp_path / "local"
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

    def test_format_mismatch_not_uri_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="URI"):
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path="/not/a/uri",
                destination_path=tmp_path / "dest",
            )

    def test_format_mismatch_purepath_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="URI"):
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path=PurePosixPath("/mnt/shared"),
                destination_path=tmp_path / "dest",
            )

    def test_from_dict(self, tmp_path) -> None:
        dest = tmp_path / "local"
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "URI",
                "source_path": "s3://bucket/assets",
                "destination_path": str(dest),
            }
        )
        assert rule.source_path_format == PathFormat.URI
        assert rule.source_path == "s3://bucket/assets"
        assert rule.destination_path == dest

    def test_from_dict_case_insensitive(self, tmp_path) -> None:
        dest = tmp_path / "local"
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "uri",
                "source_path": "s3://bucket",
                "destination_path": str(dest),
            }
        )
        assert rule.source_path_format == PathFormat.URI

    def test_to_dict(self, tmp_path) -> None:
        dest = tmp_path / "local"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path=dest,
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "URI"
        assert d["source_path"] == "s3://bucket/assets"
        assert d["destination_path"] == str(dest)

    def test_roundtrip_dict(self, tmp_path) -> None:
        dest = tmp_path / "local"
        original = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path=dest,
        )
        restored = PathMappingRule.from_dict(original.to_dict())
        assert restored.source_path_format == original.source_path_format
        assert restored.source_path == original.source_path
        assert restored.destination_path == original.destination_path


class TestPathMappingRuleValidation:
    """Tests for from_dict validation shared across formats."""

    def test_from_dict_empty(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            PathMappingRule.from_dict({})

    def test_from_dict_missing_field(self) -> None:
        with pytest.raises(ValueError):
            PathMappingRule.from_dict(
                {
                    "source_path_format": "POSIX",
                    "source_path": "/mnt/shared",
                }
            )

    def test_from_dict_extra_field(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            PathMappingRule.from_dict(
                {
                    "source_path_format": "POSIX",
                    "source_path": "/mnt/shared",
                    "destination_path": str(tmp_path / "newprefix"),
                    "extra": "field",
                }
            )

    def test_from_dict_case_insensitive(self, tmp_path) -> None:
        dest = tmp_path / "newprefix"
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "posix",
                "source_path": "/mnt/shared",
                "destination_path": str(dest),
            }
        )
        assert rule.source_path_format == PathFormat.POSIX
