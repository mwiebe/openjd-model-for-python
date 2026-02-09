# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests that TEMPLATE scope expression evaluation uses POSIX path semantics regardless of OS."""


from openjd.model import (
    create_job,
    decode_job_template,
    ParameterValue,
    ParameterValueType,
)
from openjd.model._format_strings._parser import ExprNode, parse_format_string_expr
from openjd.expr import SymbolTable
from openjd.model._internal._create_job import evaluate_let_bindings
from openjd.model.v2023_09 import ModelParsingContext, LetBinding
from openjd.expr import ExprType, ExprValue, get_default_library
from openjd.expr._path_mapping import PathFormat


class TestExprNodeEvaluateUsesPosixPaths:
    """ExprNode.evaluate() must produce forward-slash paths on Windows and POSIX."""

    def _make_expr_node(self, expr: str) -> ExprNode:
        context = ModelParsingContext(supported_extensions=["EXPR"])
        node = parse_format_string_expr(expr, context=context)
        assert isinstance(node, ExprNode)
        return node

    def test_path_parent_uses_forward_slashes(self):
        """path('/a/b/c').parent should return '/a/b', not '\\a\\b'."""
        node = self._make_expr_node("path('/a/b/c').parent")
        symtab = SymbolTable()
        result = node.evaluate(symtab=symtab, path_format=PathFormat.POSIX)
        assert result == "/a/b"

    def test_path_join_uses_forward_slashes(self):
        """path('/a/b') / 'c' should return '/a/b/c', not '\\a\\b\\c'."""
        node = self._make_expr_node("path('/a/b') / 'c'")
        symtab = SymbolTable()
        result = node.evaluate(symtab=symtab, path_format=PathFormat.POSIX)
        assert result == "/a/b/c"

    def test_path_name_from_posix_path(self):
        """path('/a/b/file.txt').name should return 'file.txt'."""
        node = self._make_expr_node("path('/a/b/file.txt').name")
        symtab = SymbolTable()
        result = node.evaluate(symtab=symtab, path_format=PathFormat.POSIX)
        assert result == "file.txt"

    def test_path_parts_are_posix(self):
        """path('/a/b/c').parts should split on '/' not '\\'."""
        node = self._make_expr_node("path('/a/b/c').parts")
        symtab = SymbolTable()
        result = node.evaluate(symtab=symtab, path_format=PathFormat.POSIX)
        # PurePosixPath('/a/b/c').parts == ('/', 'a', 'b', 'c')
        assert result == '["/", "a", "b", "c"]'

    def test_param_path_parent_uses_forward_slashes(self):
        """Param.Dir.parent should use forward slashes when Param.Dir is a PATH."""
        node = self._make_expr_node("Param.Dir.parent")
        symtab = SymbolTable()
        symtab["Param.Dir"] = ExprValue._create(
            ExprType.PATH, string_value="/projects/shot01/render", path_format=PathFormat.POSIX
        )
        result = node.evaluate(symtab=symtab, path_format=PathFormat.POSIX)
        assert result == "/projects/shot01"


class TestExprNodeEvaluateTypedUsesPosixPaths:
    """ExprNode.evaluate_typed() must produce PurePosixPath-style values on Windows and POSIX."""

    def _make_expr_node(self, expr: str) -> ExprNode:
        context = ModelParsingContext(supported_extensions=["EXPR"])
        node = parse_format_string_expr(expr, context=context)
        assert isinstance(node, ExprNode)
        return node

    def test_path_parent_typed(self):
        """evaluate_typed for path().parent should use forward slashes."""
        node = self._make_expr_node("path('/x/y/z').parent")
        symtab = SymbolTable()
        lib = get_default_library()
        result = node.evaluate_typed(symtab=symtab, library=lib, path_format=PathFormat.POSIX)
        assert result.to_string() == "/x/y"

    def test_path_join_typed(self):
        """evaluate_typed for path join should use forward slashes."""
        node = self._make_expr_node("path('/a') / 'b' / 'c'")
        symtab = SymbolTable()
        lib = get_default_library()
        result = node.evaluate_typed(symtab=symtab, library=lib, path_format=PathFormat.POSIX)
        assert result.to_string() == "/a/b/c"


class TestEvaluateLetBindingsUsesPosixPaths:
    """evaluate_let_bindings() must use POSIX path semantics on Windows and POSIX."""

    def test_let_binding_path_parent(self):
        """A let binding like 'p = path('/a/b/c').parent' should produce '/a/b'."""
        binding = LetBinding("p = path('/a/b/c').parent")
        symtab = SymbolTable()
        lib = get_default_library()
        result = evaluate_let_bindings([binding], symtab, lib, PathFormat.POSIX)
        value = result["p"]
        assert isinstance(value, ExprValue)
        assert "\\" not in value.to_string()
        assert value.to_string() == "/a/b"

    def test_let_binding_path_join(self):
        """A let binding with path join should produce forward slashes."""
        binding = LetBinding("p = path('/root') / 'sub' / 'file.txt'")
        symtab = SymbolTable()
        lib = get_default_library()
        result = evaluate_let_bindings([binding], symtab, lib, PathFormat.POSIX)
        value = result["p"]
        assert isinstance(value, ExprValue)
        assert "\\" not in value.to_string()
        assert value.to_string() == "/root/sub/file.txt"


class TestCreateJobUsesPosixPaths:
    """End-to-end: create_job must produce POSIX paths in TEMPLATE scope."""

    def test_job_name_with_path_parent(self):
        """Job name using path().parent in EXPR should have forward slashes."""
        template_dict = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "{{ path(Param.Dir).parent }}",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "Dir", "type": "STRING", "default": "/projects/shot01/render"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo hello"}}},
                }
            ],
        }
        job_template = decode_job_template(template=template_dict, supported_extensions=["EXPR"])
        job = create_job(
            job_template=job_template,
            job_parameter_values={
                "Dir": ParameterValue(
                    type=ParameterValueType.STRING, value="/projects/shot01/render"
                ),
            },
        )
        assert "\\" not in job.name
        assert job.name == "/projects/shot01"
