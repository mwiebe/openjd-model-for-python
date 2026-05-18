# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Failing tests demonstrating behavioral gaps between Rust-backed bindings and the
pure-Python reference. These are intended as evidence for the
`expr-bindings-quality-evaluation-report.md`. Once the gaps are fixed in the
bindings, these tests should pass.
"""

import pytest
from openjd.expr import (
    FormatString,
    FunctionLibrary,
    ExprType,
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


@pytest.mark.xfail(reason="Bindings ParsedExpression.evaluate silently drops path_mapping_rules")
def test_parsed_expression_evaluate_applies_path_mapping_rules():
    parsed = parse_expression("apply_path_mapping('/mnt/shared/file.exr')")
    lib = FunctionLibrary().with_host_context()
    result = parsed.evaluate(library=lib, path_mapping_rules=[PATH_RULE])
    assert result.item() == "/local/cache/file.exr"


@pytest.mark.xfail(reason="Bindings FormatString.resolve_string silently drops path_mapping_rules")
def test_format_string_resolve_string_applies_path_mapping_rules():
    fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
    lib = FunctionLibrary().with_host_context()
    result = fs.resolve_string(SymbolTable({}), library=lib, path_mapping_rules=[PATH_RULE])
    assert result == "/local/cache/file.exr"


@pytest.mark.xfail(reason="Bindings FormatString.resolve silently drops path_mapping_rules")
def test_format_string_resolve_applies_path_mapping_rules():
    fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
    lib = FunctionLibrary().with_host_context()
    result = fs.resolve(SymbolTable({}), library=lib, path_mapping_rules=[PATH_RULE])
    assert result.item() == "/local/cache/file.exr"


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


@pytest.mark.xfail(reason="Bindings PathFormat is not pickleable; reference is")
def test_path_format_is_pickleable():
    import pickle
    pickle.dumps(PathFormat.POSIX)


@pytest.mark.xfail(reason="Bindings PathMappingRule is not pickleable; reference is")
def test_path_mapping_rule_is_pickleable():
    import pickle
    pickle.dumps(PATH_RULE)
