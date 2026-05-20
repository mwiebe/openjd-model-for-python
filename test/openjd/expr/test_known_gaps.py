# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Failing tests demonstrating behavioral gaps between the Rust-backed
bindings and the pure-Python reference. These started life as evidence
for `expr-bindings-quality-evaluation-report.md`. Tests for resolved
gaps are kept as passing regression tests under their original names so
git history shows the resolution.
"""

import pytest
from openjd.expr import (
    ExprProfile,
    ExprType,
    FormatString,
    FunctionLibrary,
    HostContext,
    PathFormat,
    PathMappingRule,
    RangeExpr,
    SymbolTable,
    evaluate_expression,
    parse_expression,
)


PATH_RULE = PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path="/mnt/shared",
    destination_path="/local/cache",
)


# ── Resolved by the path-mapping-via-profile reshape ──────────────


def _profile_with_rule() -> ExprProfile:
    return ExprProfile().with_host_context(HostContext.with_rules([PATH_RULE]))


def test_parsed_expression_evaluate_applies_path_mapping_rules():
    """Resolved by replacing the per-call `path_mapping_rules=` kwarg with
    `profile=` (where path-mapping rules live inside `HostContext.with_rules`)."""
    parsed = parse_expression("apply_path_mapping('/mnt/shared/file.exr')")
    result = parsed.evaluate(profile=_profile_with_rule())
    assert result.item() == "/local/cache/file.exr"


def test_format_string_resolve_string_applies_path_mapping_rules():
    """Same resolution at the `FormatString` boundary."""
    fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
    result = fs.resolve_string(SymbolTable({}), profile=_profile_with_rule())
    assert result == "/local/cache/file.exr"


def test_format_string_resolve_applies_path_mapping_rules():
    """And on the typed `FormatString.resolve` path."""
    fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
    result = fs.resolve(SymbolTable({}), profile=_profile_with_rule())
    assert result.item() == "/local/cache/file.exr"


# ── Still-failing gaps (xfail) ────────────────────────────────────


@pytest.mark.xfail(
    reason="Bindings reject string in target_type union; reference picks matching member"
)
def test_target_type_union_picks_matching_string():
    """`'42'` is a string; `int | string` should accept it as-is."""
    v = evaluate_expression("'42'", target_type=ExprType("int | string"))
    assert v.type == ExprType("string")
    assert v.item() == "42"


@pytest.mark.xfail(
    reason="Bindings coerce operands to target_type before evaluating; "
    "RFC 0005 says operators evaluate operands unconstrained"
)
def test_arithmetic_with_string_target_propagates_unconstrained():
    """RFC 0005 says operators evaluate operands unconstrained, then coerce result."""
    result = evaluate_expression(
        "Param.Count - 1",
        values={"Param.Count": 100},
        target_type=ExprType("string"),
    )
    assert result.item() == "99"


@pytest.mark.xfail(reason="Bindings SymbolTable.keys returns a list; spec advertises a set")
def test_symbol_table_keys_is_set():
    """`SymbolTable.keys` is documented as `set` of top-level keys (spec)."""
    st = SymbolTable({"a": 1, "b": 2})
    assert isinstance(st.keys, set)


@pytest.mark.xfail(reason="Bindings RangeExpr is not hashable; reference is")
def test_range_expr_is_hashable():
    r = RangeExpr("1-10")
    {r}  # raises if unhashable


# ── Resolved: PathFormat / PathMappingRule pickle ─────────────────


def test_path_format_is_pickleable():
    """Resolved by adding `__reduce__` on the Rust enum."""
    import pickle

    loaded = pickle.loads(pickle.dumps(PathFormat.POSIX))
    assert loaded == PathFormat.POSIX


def test_path_mapping_rule_is_pickleable():
    """Resolved by adding `__reduce__` on the Rust struct, round-tripping
    through `to_dict` / `from_dict`."""
    import pickle

    loaded = pickle.loads(pickle.dumps(PATH_RULE))
    assert loaded.to_dict() == PATH_RULE.to_dict()
