# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for URI-aware path operations."""

from openjd.expr import evaluate_expression, ExprValue, SymbolTable
from openjd.expr._path_mapping import PathFormat
from openjd.expr._uri_path import (
    is_uri,
    split_uri,
    uri_parts,
    uri_name,
    uri_parent,
    uri_stem,
    uri_suffix,
    uri_suffixes,
    uri_join,
    uri_from_parts,
)


class TestUriDetection:
    """Tests for URI scheme detection (Expression Language §1.2.1)."""

    def test_s3_uri(self) -> None:
        assert is_uri("s3://bucket/key") is True

    def test_https_uri(self) -> None:
        assert is_uri("https://example.com/path") is True

    def test_fsx_uri(self) -> None:
        assert is_uri("fsx://vol/data") is True

    def test_custom_scheme(self) -> None:
        assert is_uri("my-scheme+2://server/path") is True

    def test_posix_absolute_not_uri(self) -> None:
        assert is_uri("/mnt/data/file.txt") is False

    def test_relative_not_uri(self) -> None:
        assert is_uri("relative/path") is False

    def test_colon_in_path_not_uri(self) -> None:
        assert is_uri("/mnt/c:/data") is False

    def test_windows_drive_not_uri(self) -> None:
        assert is_uri("C:\\Users\\test") is False

    def test_bare_scheme_no_slashes_not_uri(self) -> None:
        assert is_uri("s3:bucket/key") is False


class TestSplitUri:
    """Tests for split_uri helper."""

    def test_s3(self) -> None:
        assert split_uri("s3://bucket/dir/file.txt") == ("s3://bucket", "/dir/file.txt")

    def test_https(self) -> None:
        assert split_uri("https://host/path") == ("https://host", "/path")

    def test_bare_authority(self) -> None:
        assert split_uri("s3://bucket") == ("s3://bucket", "")

    def test_not_uri(self) -> None:
        assert split_uri("/local/path") is None


class TestUriParts:
    """Tests for uri_parts (Expression Language §2.3.1)."""

    def test_basic(self) -> None:
        assert uri_parts("s3://bucket/dir/file.obj") == ["s3://bucket", "dir", "file.obj"]

    def test_single_component(self) -> None:
        assert uri_parts("s3://bucket/key") == ["s3://bucket", "key"]

    def test_bare_authority(self) -> None:
        assert uri_parts("s3://bucket") == ["s3://bucket"]

    def test_double_slash_preserved(self) -> None:
        assert uri_parts("s3://bucket/a//b/c") == ["s3://bucket", "a", "", "b", "c"]

    def test_triple_slash_preserved(self) -> None:
        assert uri_parts("s3://bucket/a///b") == ["s3://bucket", "a", "", "", "b"]

    def test_dot_segments_preserved(self) -> None:
        assert uri_parts("s3://bucket/a/./b/../c") == ["s3://bucket", "a", ".", "b", "..", "c"]

    def test_trailing_slash(self) -> None:
        assert uri_parts("s3://bucket/prefix/") == ["s3://bucket", "prefix", ""]


class TestUriProperties:
    """Tests for URI path property helpers."""

    def test_name(self) -> None:
        assert uri_name("s3://bucket/dir/file.obj") == "file.obj"

    def test_name_bare(self) -> None:
        assert uri_name("s3://bucket") == ""

    def test_stem(self) -> None:
        assert uri_stem("s3://bucket/dir/file.obj") == "file"

    def test_stem_compound(self) -> None:
        assert uri_stem("s3://bucket/archive.tar.gz") == "archive.tar"

    def test_suffix(self) -> None:
        assert uri_suffix("s3://bucket/dir/file.obj") == ".obj"

    def test_suffix_compound(self) -> None:
        assert uri_suffix("s3://bucket/archive.tar.gz") == ".gz"

    def test_suffix_none(self) -> None:
        assert uri_suffix("s3://bucket/Makefile") == ""

    def test_suffixes(self) -> None:
        assert uri_suffixes("s3://bucket/archive.tar.gz") == [".tar", ".gz"]

    def test_suffixes_single(self) -> None:
        assert uri_suffixes("s3://bucket/file.txt") == [".txt"]

    def test_suffixes_none(self) -> None:
        assert uri_suffixes("s3://bucket/Makefile") == []

    def test_parent(self) -> None:
        assert uri_parent("s3://bucket/dir/file.obj") == "s3://bucket/dir"

    def test_parent_single_component(self) -> None:
        assert uri_parent("s3://bucket/key") == "s3://bucket"

    def test_parent_at_root(self) -> None:
        assert uri_parent("s3://bucket") == "s3://bucket"


class TestUriFromParts:
    """Tests for uri_from_parts and uri_join."""

    def test_from_parts(self) -> None:
        assert uri_from_parts(["s3://bucket", "dir", "file.obj"]) == "s3://bucket/dir/file.obj"

    def test_from_parts_bare(self) -> None:
        assert uri_from_parts(["s3://bucket"]) == "s3://bucket"

    def test_from_parts_double_slash(self) -> None:
        assert uri_from_parts(["s3://bucket", "a", "", "b"]) == "s3://bucket/a//b"

    def test_join(self) -> None:
        assert uri_join("s3://bucket/dir", ["sub", "file.obj"]) == "s3://bucket/dir/sub/file.obj"

    def test_roundtrip(self) -> None:
        original = "s3://bucket/a//b/file.txt"
        assert uri_from_parts(uri_parts(original)) == original


class TestUriPathExpressions:
    """Tests for URI paths through the expression evaluator."""

    def test_uri_name(self) -> None:
        assert evaluate_expression('path("s3://bucket/dir/file.obj").name').item() == "file.obj"

    def test_uri_stem(self) -> None:
        assert evaluate_expression('path("s3://bucket/dir/file.obj").stem').item() == "file"

    def test_uri_suffix(self) -> None:
        assert evaluate_expression('path("s3://bucket/dir/file.obj").suffix').item() == ".obj"

    def test_uri_suffixes(self) -> None:
        result = evaluate_expression('path("https://host/archive.tar.gz").suffixes')
        assert result.item() == [".tar", ".gz"]

    def test_uri_parent(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/file.obj").parent')
        assert result.to_string() == "s3://bucket/dir"

    def test_uri_parts(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/file.obj").parts')
        assert result.item() == ["s3://bucket", "dir", "file.obj"]

    def test_uri_parent_chain(self) -> None:
        assert evaluate_expression('path("s3://bucket/a/b").parent').to_string() == "s3://bucket/a"
        assert (
            evaluate_expression('path("s3://bucket/a/b").parent.parent').to_string()
            == "s3://bucket"
        )
        assert (
            evaluate_expression('path("s3://bucket/a/b").parent.parent.parent').to_string()
            == "s3://bucket"
        )

    def test_uri_bare_authority(self) -> None:
        assert evaluate_expression('path("s3://bucket").name').item() == ""
        assert evaluate_expression('path("s3://bucket").parts').item() == ["s3://bucket"]
        assert evaluate_expression('path("s3://bucket").parent').to_string() == "s3://bucket"


class TestUriPathNoNormalization:
    """Tests that URI path portions are not normalized."""

    def test_double_slash_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/a//b/file.txt")')
        assert result.to_string() == "s3://bucket/a//b/file.txt"

    def test_double_slash_parts(self) -> None:
        result = evaluate_expression('path("s3://bucket/a//b/file.txt").parts')
        assert result.item() == ["s3://bucket", "a", "", "b", "file.txt"]

    def test_triple_slash_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/a///b")')
        assert result.to_string() == "s3://bucket/a///b"

    def test_dot_segments_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/a/./b/../c")')
        assert result.to_string() == "s3://bucket/a/./b/../c"

    def test_dot_segments_parts(self) -> None:
        result = evaluate_expression('path("s3://bucket/a/./b/../c").parts')
        assert result.item() == ["s3://bucket", "a", ".", "b", "..", "c"]

    def test_trailing_slash_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/prefix/")')
        assert result.to_string() == "s3://bucket/prefix/"

    def test_roundtrip_via_parts(self) -> None:
        result = evaluate_expression(
            'path(path("s3://bucket/a//b/file.txt").parts) == path("s3://bucket/a//b/file.txt")'
        )
        assert result.item() is True


class TestUriPathOperators:
    """Tests for operators on URI paths."""

    def test_join_string(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir") / "sub/file.obj"')
        assert result.to_string() == "s3://bucket/dir/sub/file.obj"

    def test_join_multi(self) -> None:
        result = evaluate_expression('path("s3://bucket") / "a" / "b" / "c.txt"')
        assert result.to_string() == "s3://bucket/a/b/c.txt"

    def test_join_absolute_replaces(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir") / path("/local/path")')
        assert result.to_string().endswith("/local/path")

    def test_join_trailing_slash_no_double(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/") / "file.obj"')
        assert result.to_string() == "s3://bucket/dir/file.obj"

    def test_concat(self) -> None:
        result = evaluate_expression('path("s3://bucket/file") + ".txt"')
        assert result.to_string() == "s3://bucket/file.txt"

    def test_with_suffix(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/scene.exr").with_suffix(".png")')
        assert result.to_string() == "s3://bucket/renders/scene.png"

    def test_with_name(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/scene.exr").with_name("other.obj")')
        assert result.to_string() == "s3://bucket/renders/other.obj"

    def test_with_stem(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/scene.exr").with_stem("final")')
        assert result.to_string() == "s3://bucket/renders/final.exr"

    def test_as_posix_identity(self) -> None:
        result = evaluate_expression('path("s3://bucket/a/b").as_posix()')
        assert result.item() == "s3://bucket/a/b"

    def test_with_number(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/shot_####.exr").with_number(42)')
        assert result.to_string() == "s3://bucket/renders/shot_0042.exr"


class TestUriPathConstruction:
    """Tests for URI path construction."""

    def test_from_string(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/file.obj")')
        assert result.to_string() == "s3://bucket/dir/file.obj"

    def test_from_parts(self) -> None:
        result = evaluate_expression('path(["s3://bucket", "dir", "file.obj"])')
        assert result.to_string() == "s3://bucket/dir/file.obj"

    def test_from_parts_with_empty_preserves_double_slash(self) -> None:
        result = evaluate_expression('path(["s3://bucket", "a", "", "b"])')
        assert result.to_string() == "s3://bucket/a//b"

    def test_from_parts_bare(self) -> None:
        result = evaluate_expression('path(["s3://bucket"])')
        assert result.to_string() == "s3://bucket"


class TestUriPathSchemeVariety:
    """Tests for various URI schemes."""

    def test_https(self) -> None:
        result = evaluate_expression('path("https://example.com/models/scene.obj")')
        assert result.to_string() == "https://example.com/models/scene.obj"
        assert (
            evaluate_expression('path("https://example.com/models/scene.obj").name').item()
            == "scene.obj"
        )

    def test_fsx(self) -> None:
        result = evaluate_expression('path("fsx://vol-123/data/file.bin").parts')
        assert result.item() == ["fsx://vol-123", "data", "file.bin"]

    def test_custom_scheme(self) -> None:
        result = evaluate_expression('path("my-scheme+2://server/path/file.txt").parent')
        assert result.to_string() == "my-scheme+2://server/path"


class TestUriPathInSymbolTable:
    """Tests for URI paths passed through symbol tables."""

    def test_uri_in_symtab(self) -> None:
        symtab = SymbolTable(
            {"P": ExprValue("s3://bucket/dir/file.obj", type="path", path_format=PathFormat.POSIX)}
        )
        assert (
            evaluate_expression("P.name", values=symtab, path_format=PathFormat.POSIX).item()
            == "file.obj"
        )
        assert (
            evaluate_expression("P.parent", values=symtab, path_format=PathFormat.POSIX).to_string()
            == "s3://bucket/dir"
        )

    def test_uri_join_in_symtab(self) -> None:
        symtab = SymbolTable(
            {"Dir": ExprValue("s3://bucket/assets", type="path", path_format=PathFormat.POSIX)}
        )
        result = evaluate_expression(
            "Dir / 'sub' / 'file.obj'", values=symtab, path_format=PathFormat.POSIX
        )
        assert result.to_string() == "s3://bucket/assets/sub/file.obj"

    def test_uri_with_suffix_in_symtab(self) -> None:
        symtab = SymbolTable(
            {"P": ExprValue("s3://bucket/scene.exr", type="path", path_format=PathFormat.POSIX)}
        )
        result = evaluate_expression(
            "P.with_suffix('.png')", values=symtab, path_format=PathFormat.POSIX
        )
        assert result.to_string() == "s3://bucket/scene.png"
