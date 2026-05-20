# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Verify every Rust-backed PyO3 class advertises the module where it is
conceptually exposed (e.g. `openjd.expr.FormatString`,
`openjd.model._v1.Job`, `openjd.sessions._v1.Session`) rather than the
default `builtins`.

The module string is compiled into the class by the `#[pyclass(module = ...)]`
attribute on the Rust side, and surfaces via:

* ``cls.__module__``
* ``repr(cls)``            (`<class 'openjd.model._v1.Job'>`)
* ``pickle`` / error messages (`TypeError: cannot create 'openjd.model._v1.X'`)

A class reporting `builtins` is a bug — it breaks pickling, makes error
messages unhelpful, and fools tools (Sphinx, IDEs) into looking for the
type in the wrong place.
"""

from __future__ import annotations

import pytest

from openjd import _openjd_rs

# Canonical module for each Rust-backed class. The left-hand column is the
# class name as exported from `openjd._openjd_rs`; the right-hand column is
# the module that class's `__module__` should report.
#
# Most classes report their public-facing module (e.g. ``openjd.model._v1``)
# so that ``repr`` and pickle produce friendly names. ``SpecificationRevision``
# and ``TemplateSpecificationVersion`` are exceptions: the ``_v1`` wrapper
# module shadows them with Python ``Enum`` shims of the same name (for
# backwards-compat with consumers that rely on ``str``-Enum semantics),
# so the Rust pyclasses report ``openjd._openjd_rs`` to keep pickle
# resolution unambiguous. The Python Enum shims pickle independently
# under ``openjd.model._v1`` via Python's standard Enum support.
EXPECTED_MODULES: dict[str, str] = {
    # openjd.expr
    "ExprExtension": "openjd.expr",
    "ExprProfile": "openjd.expr",
    "ExprRevision": "openjd.expr",
    "ExprType": "openjd.expr",
    "ExprValue": "openjd.expr",
    "FormatString": "openjd.expr",
    "FunctionLibrary": "openjd.expr",
    "HostContext": "openjd.expr",
    "ParsedExpression": "openjd.expr",
    "PathFormat": "openjd.expr",
    "PathMappingRule": "openjd.expr",
    "RangeExpr": "openjd.expr",
    "SymbolTable": "openjd.expr",
    "TypeCode": "openjd.expr",
    # openjd.model._v1
    "Action": "openjd.model._v1",
    "CallerLimits": "openjd.model._v1",
    "CancelationMode": "openjd.model._v1",
    "DocumentType": "openjd.model._v1",
    "EmbeddedFile": "openjd.model._v1",
    "Environment": "openjd.model._v1",
    "EnvironmentActions": "openjd.model._v1",
    "EnvironmentScript": "openjd.model._v1",
    "EnvironmentTemplate": "openjd.model._v1",
    "Job": "openjd.model._v1",
    "JobParameter": "openjd.model._v1",
    "JobParameterType": "openjd.model._v1",
    "JobParameterValue": "openjd.model._v1",
    "JobTemplate": "openjd.model._v1",
    "ModelExtension": "openjd.model._v1",
    "ModelProfile": "openjd.model._v1",
    "SpecificationRevision": "openjd._openjd_rs",
    "Step": "openjd.model._v1",
    "StepActions": "openjd.model._v1",
    "StepDependency": "openjd.model._v1",
    "StepDependencyEdge": "openjd.model._v1",
    "StepDependencyGraph": "openjd.model._v1",
    "StepDependencyNode": "openjd.model._v1",
    "StepParameterSpace": "openjd.model._v1",
    "StepParameterSpaceIterator": "openjd.model._v1",
    "StepScript": "openjd.model._v1",
    "TaskParameterType": "openjd.model._v1",
    "TaskParameterValue": "openjd.model._v1",
    "TemplateSpecificationVersion": "openjd._openjd_rs",
    "ValidationContext": "openjd.model._v1",
    # openjd.sessions._v1
    "ActionResult": "openjd.sessions._v1",
    "ActionState": "openjd.sessions._v1",
    "ActionStatus": "openjd.sessions._v1",
    "PosixSessionUser": "openjd.sessions._v1",
    "ScriptRunnerState": "openjd.sessions._v1",
    "Session": "openjd.sessions._v1",
    "SessionState": "openjd.sessions._v1",
    "WindowsSessionUser": "openjd.sessions._v1",
}


# Exception classes created via PyO3's create_exception! macro. That macro
# cannot accept a dotted Python module path (it uses stringify! on the
# identifier), so the user-facing module and name are fixed up from the Rust
# `_openjd_rs` module init via `setattr` on the type. These tests verify the
# fixup ran successfully, and that every consumer-facing exception has its
# module / name set correctly.
EXPECTED_EXCEPTION_MODULES: dict[str, str] = {
    # openjd.expr
    "ExpressionError": "openjd.expr",
    "ExpressionTypeError": "openjd.expr",
    "FormatStringValidationError": "openjd.expr",
    "RangeExprError": "openjd.expr",
    # openjd.model._v1
    "DecodeValidationError": "openjd.model._v1",
    "ModelValidationError": "openjd.model._v1",
    "UnsupportedSchema": "openjd.model._v1",
    # openjd.sessions._v1
    "SessionError": "openjd.sessions._v1",
    "BadCredentialsException": "openjd.sessions._v1",
}


class TestPyClassModules:
    """Every Rust-backed class reports the correct __module__."""

    # ── pyclass (struct/enum) tests ──

    @pytest.mark.parametrize(
        ("class_name", "expected_module"),
        sorted(EXPECTED_MODULES.items()),
        ids=lambda v: v,
    )
    def test_class_module_attribute(self, class_name: str, expected_module: str) -> None:
        # GIVEN a pyclass exported from the openjd._openjd_rs native module
        cls = getattr(_openjd_rs, class_name)
        # THEN it should report the user-facing module where it is conceptually
        # exposed, NOT the PyO3 default of 'builtins'.
        assert cls.__module__ == expected_module, (
            f"{class_name}.__module__ = {cls.__module__!r}, expected {expected_module!r}. "
            f"Add `module = {expected_module!r}` to the `#[pyclass(...)]` attribute in Rust."
        )

    @pytest.mark.parametrize(
        ("class_name", "expected_module"),
        sorted(EXPECTED_MODULES.items()),
        ids=lambda v: v,
    )
    def test_class_repr_contains_module(self, class_name: str, expected_module: str) -> None:
        # GIVEN a pyclass exported from the openjd._openjd_rs native module
        cls = getattr(_openjd_rs, class_name)
        # THEN its type repr should embed the user-facing module path, so that
        # Python error messages and `repr(cls)` show the class by its
        # conceptually-correct dotted name.
        expected_fqn = f"{expected_module}.{class_name}"
        assert expected_fqn in repr(cls), (
            f"repr({class_name}) = {repr(cls)!r}, expected to contain {expected_fqn!r}"
        )

    # ── exception class tests ──
    #
    # Exception classes are created by PyO3's `create_exception!` macro, which
    # cannot accept a dotted module path (it stringifies an identifier). The
    # fix is applied in the `_openjd_rs` Rust module init, which sets
    # `__module__`, `__name__`, and `__qualname__` on each exception type
    # immediately after creating it. The tests below verify that fix-up runs
    # at extension-module load time (no Python package import is required).

    @pytest.mark.parametrize(
        ("class_name", "expected_module"),
        sorted(EXPECTED_EXCEPTION_MODULES.items()),
        ids=lambda v: v,
    )
    def test_exception_module_attribute(
        self, class_name: str, expected_module: str
    ) -> None:
        # GIVEN an exception class created via PyO3's create_exception! macro
        cls = getattr(_openjd_rs, class_name)
        # THEN the `_openjd_rs` Rust module init should have fixed its
        # __module__ to the canonical user-facing module.
        assert cls.__module__ == expected_module, (
            f"{class_name}.__module__ = {cls.__module__!r}, expected {expected_module!r}. "
            f"The Rust `_openjd_rs` module init should call "
            f"`register_renamed_exception` with module={expected_module!r}."
        )

    @pytest.mark.parametrize(
        ("class_name", "expected_module"),
        sorted(EXPECTED_EXCEPTION_MODULES.items()),
        ids=lambda v: v,
    )
    def test_exception_name_attribute(
        self, class_name: str, expected_module: str
    ) -> None:
        # GIVEN an exception class created via PyO3's create_exception! macro.
        # The macro bakes a `Py` prefix into the class's __name__, e.g.
        # `PyDecodeValidationError`. The Rust module init's
        # `register_renamed_exception` helper strips it so tracebacks show
        # `openjd.model._v1.DecodeValidationError: ...` rather than
        # `_openjd_rs.PyDecodeValidationError: ...`.
        cls = getattr(_openjd_rs, class_name)
        # THEN __name__ should match the user-facing class name (no Py prefix)
        assert cls.__name__ == class_name, (
            f"{class_name}.__name__ = {cls.__name__!r}, expected {class_name!r}. "
            f"The Rust `register_renamed_exception` helper should set "
            f"__name__ to {class_name!r}."
        )
        # AND __qualname__ should agree with __name__.
        assert cls.__qualname__ == class_name, (
            f"{class_name}.__qualname__ = {cls.__qualname__!r}, expected {class_name!r}"
        )

    @pytest.mark.parametrize(
        ("class_name", "expected_module"),
        sorted(EXPECTED_EXCEPTION_MODULES.items()),
        ids=lambda v: v,
    )
    def test_exception_traceback_shows_module(
        self, class_name: str, expected_module: str
    ) -> None:
        # GIVEN an exception class from the openjd._openjd_rs native module
        cls = getattr(_openjd_rs, class_name)
        # WHEN the exception is raised and formatted via repr(type(exc))
        try:
            raise cls("test message")
        except BaseException as e:
            rendered = repr(type(e))
        # THEN the rendered form includes the user-facing dotted name, so the
        # exception is identifiable in error logs and tracebacks.
        expected_fqn = f"{expected_module}.{class_name}"
        assert expected_fqn in rendered, (
            f"repr(type({class_name}(...))) = {rendered!r}, "
            f"expected to contain {expected_fqn!r}"
        )

    # ── regression guards ──

    def test_no_pyclass_reports_builtins(self) -> None:
        """Regression guard: catch any new pyclass added without `module = ...`.

        Any class reachable from `openjd._openjd_rs` whose `__module__` is
        'builtins' is almost certainly missing its `module = "..."` attribute
        on the Rust side. If a new pyclass legitimately belongs in `builtins`,
        add it to an allowlist here — but that's very unlikely.
        """
        # GIVEN every class-valued attribute exported from openjd._openjd_rs
        offenders: list[str] = []
        for name in dir(_openjd_rs):
            if name.startswith("_"):
                continue
            obj = getattr(_openjd_rs, name)
            if not isinstance(obj, type):
                continue
            if getattr(obj, "__module__", None) == "builtins":
                offenders.append(name)

        # THEN none of them should still report 'builtins'
        assert not offenders, (
            "The following Rust-backed classes still report __module__='builtins'. "
            "Add `module = \"openjd.X\"` to their `#[pyclass(...)]` attributes:\n  "
            + "\n  ".join(offenders)
        )

    def test_every_rust_class_is_covered(self) -> None:
        """Regression guard: every Rust-backed class is listed in one of the
        EXPECTED_* mappings.

        Without this check, someone could add a new pyclass (with module set
        to any value) and `test_no_pyclass_reports_builtins` would pass
        silently even if the module string were wrong.
        """
        # Load packages so the exception fixup has run — exception classes
        # otherwise still show `_openjd_rs` as their module and would be
        # misclassified by this scan.
        import openjd.expr  # noqa: F401
        import openjd.model._v1  # noqa: F401
        try:
            import openjd.sessions._v1  # noqa: F401
        except ImportError:
            pass

        # GIVEN every class-valued attribute exported from openjd._openjd_rs
        # whose __module__ starts with "openjd." (i.e. our classes, not
        # re-exported stdlib types).
        discovered: set[str] = set()
        for name in dir(_openjd_rs):
            if name.startswith("_"):
                continue
            obj = getattr(_openjd_rs, name)
            if not isinstance(obj, type):
                continue
            mod = getattr(obj, "__module__", "")
            if mod.startswith("openjd."):
                discovered.add(name)

        covered = set(EXPECTED_MODULES) | set(EXPECTED_EXCEPTION_MODULES)
        # THEN every discovered class must be in one of the EXPECTED_* maps.
        missing = discovered - covered
        assert not missing, (
            "New Rust-backed classes discovered that are not listed in "
            "EXPECTED_MODULES or EXPECTED_EXCEPTION_MODULES:\n  "
            + "\n  ".join(sorted(missing))
            + "\nAdd them (with their canonical module) so their __module__ "
            "attribute is covered by regression tests."
        )

    def test_expected_mappings_have_no_stale_entries(self) -> None:
        """EXPECTED_* mappings shouldn't reference classes that no longer exist."""
        # GIVEN the set of classes documented in both mappings
        all_expected = {**EXPECTED_MODULES, **EXPECTED_EXCEPTION_MODULES}
        stale = [name for name in all_expected if not hasattr(_openjd_rs, name)]
        # THEN every one should still be present on the PyO3 module.
        assert not stale, (
            "EXPECTED_MODULES / EXPECTED_EXCEPTION_MODULES reference classes "
            "that no longer exist on openjd._openjd_rs:\n  " + "\n  ".join(stale)
        )

    def test_expected_mappings_do_not_overlap(self) -> None:
        """EXPECTED_MODULES and EXPECTED_EXCEPTION_MODULES must be disjoint."""
        overlap = set(EXPECTED_MODULES) & set(EXPECTED_EXCEPTION_MODULES)
        assert not overlap, (
            "A class name appears in both EXPECTED_MODULES (pyclasses) and "
            "EXPECTED_EXCEPTION_MODULES (exceptions). Each class is one or "
            "the other:\n  " + "\n  ".join(sorted(overlap))
        )
