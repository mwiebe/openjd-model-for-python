# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.expr import (
    evaluate_expression,
    ExprProfile,
    FunctionLibrary,
    HostContext,
    ExpressionError,
    PathMappingRule,
    PathFormat,
)


class TestFunctionLibraryContext:
    """Test that functions are available/unavailable based on profile."""

    def test_default_library_no_host_context(self) -> None:
        """Default library should not have host context enabled."""
        library = FunctionLibrary()
        assert library.host_context_enabled is False

    def test_for_profile_returns_new_library(self) -> None:
        """`FunctionLibrary.for_profile(...)` returns a fresh library."""
        default_lib = FunctionLibrary()
        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = FunctionLibrary.for_profile(profile)
        assert result is not default_lib
        assert result.host_context_enabled is True
        assert default_lib.host_context_enabled is False

    def test_for_profile_with_unresolved_host_context(self) -> None:
        """`HostContext.unresolved()` enables stub host functions."""
        profile = ExprProfile().with_host_context(HostContext.unresolved())
        lib = FunctionLibrary.for_profile(profile)
        assert lib.host_context_enabled is True


class TestApplyPathMappingContext:
    """Test apply_path_mapping availability based on profile (RFC 0006)."""

    def test_not_available_without_host_context(self) -> None:
        """apply_path_mapping should error without host context."""
        library = FunctionLibrary()
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("apply_path_mapping('/path')", library=library)

    def test_not_available_with_default_library(self) -> None:
        """apply_path_mapping should error with the default library."""
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("apply_path_mapping('/path')")

    def test_available_with_host_context(self) -> None:
        """apply_path_mapping should work when host context is enabled."""
        from pathlib import PurePath

        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = evaluate_expression("apply_path_mapping('/some/path')", profile=profile)
        # No rules configured, path returned normalized to OS-native format
        assert str(result) == str(PurePath("/some/path"))

    def test_method_syntax_without_host_context(self) -> None:
        """Method syntax should also error without host context."""
        library = FunctionLibrary()
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("'/path'.apply_path_mapping()", library=library)

    def test_method_syntax_with_host_context(self) -> None:
        """Method syntax should work with host context."""
        from pathlib import PurePath

        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = evaluate_expression("'/some/path'.apply_path_mapping()", profile=profile)
        assert str(result) == str(PurePath("/some/path"))

    def test_with_path_mapping_rules(self, tmp_path) -> None:
        """apply_path_mapping should apply rules when configured on the profile."""
        from pathlib import PurePosixPath

        dest = tmp_path / "new" / "path"
        rules = [
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PurePosixPath("/old/path"),
                destination_path=dest,
            )
        ]
        profile = ExprProfile().with_host_context(HostContext.with_rules(rules))

        result = evaluate_expression("apply_path_mapping('/old/path/file.txt')", profile=profile)
        assert str(result) == str(dest / "file.txt")

    def test_unmatched_path_unchanged(self, tmp_path) -> None:
        """Paths not matching any rule should be returned normalized to OS-native format."""
        from pathlib import PurePosixPath, PurePath

        dest = tmp_path / "mapped" / "path"
        rules = [
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PurePosixPath("/specific/path"),
                destination_path=dest,
            )
        ]
        profile = ExprProfile().with_host_context(HostContext.with_rules(rules))

        result = evaluate_expression("apply_path_mapping('/other/path/file.txt')", profile=profile)
        assert str(result) == str(PurePath("/other/path/file.txt"))

    def test_no_rules_returns_path_unchanged(self) -> None:
        """With no rules configured, path should be returned normalized to OS-native format."""
        from pathlib import PurePath

        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = evaluate_expression("apply_path_mapping('/any/path')", profile=profile)
        assert str(result) == str(PurePath("/any/path"))


class TestSubmissionContextFunctions:
    """Test that submission-time functions work without host context."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            pytest.param("1 + 2", 3, id="arithmetic"),
            pytest.param("min(5, 3)", 3, id="min"),
            pytest.param("upper('hello')", "HELLO", id="upper"),
            pytest.param("len('test')", 4, id="len"),
        ],
    )
    def test_submission_functions_available(self, expr: str, expected) -> None:
        """Core functions should work without host context."""
        library = FunctionLibrary()
        result = evaluate_expression(expr, library=library)
        if isinstance(expected, int):
            assert result.item() == expected
        else:
            assert result.item() == expected

    def test_path_functions_available_without_host_context(self, tmp_path) -> None:
        """Path manipulation functions should work without host context."""
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        library = FunctionLibrary()
        render_file = tmp_path / "projects" / "render.exr"
        symtab = SymbolTable({"P": ExprValue(str(render_file), type="path", path_format=host_pf)})

        # These should all work without host context
        result = evaluate_expression("P.stem", values=symtab, library=library)
        assert result.item() == "render"

        result = evaluate_expression("P.suffix", values=symtab, library=library)
        assert result.item() == ".exr"

        result = evaluate_expression("with_suffix(P, '.png')", values=symtab, library=library)
        assert str(result).endswith("render.png")


class TestUnresolvedHostContext:
    """Test HostContext.unresolved() for job creation time type checking."""

    def test_for_profile_unresolved_returns_enabled_library(self) -> None:
        default_lib = FunctionLibrary()
        profile = ExprProfile().with_host_context(HostContext.unresolved())
        result = FunctionLibrary.for_profile(profile)
        assert result is not default_lib
        assert result.host_context_enabled is True
        assert default_lib.host_context_enabled is False

    def test_apply_path_mapping_returns_unresolved_path(self) -> None:
        """At job creation time, apply_path_mapping returns unresolved[path]."""
        from openjd.expr import TypeCode

        profile = ExprProfile().with_host_context(HostContext.unresolved())
        result = evaluate_expression("apply_path_mapping('/some/path')", profile=profile)
        assert result.type.type_code == TypeCode.UNRESOLVED

    def test_apply_path_mapping_method_returns_unresolved_path(self) -> None:
        """Method syntax also returns unresolved[path] at job creation time."""
        from openjd.expr import TypeCode

        profile = ExprProfile().with_host_context(HostContext.unresolved())
        result = evaluate_expression("'/some/path'.apply_path_mapping()", profile=profile)
        assert result.type.type_code == TypeCode.UNRESOLVED

    def test_not_available_without_any_context(self) -> None:
        """apply_path_mapping should still error without any host context."""
        library = FunctionLibrary()
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("apply_path_mapping('/path')", library=library)
