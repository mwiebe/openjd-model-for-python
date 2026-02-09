# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for let bindings in SimpleAction (FEATURE_BUNDLE_1 + EXPR extensions)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model import decode_job_template
from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    ModelParsingContext,
    SimpleAction,
    StepTemplate,
)

EXTENSIONS = ["FEATURE_BUNDLE_1", "EXPR"]


def fb1_expr_context() -> ModelParsingContext:
    """Context with both FEATURE_BUNDLE_1 and EXPR extensions."""
    return ModelParsingContext(supported_extensions=EXTENSIONS)


def fb1_only_context() -> ModelParsingContext:
    """Context with only FEATURE_BUNDLE_1 extension."""
    return ModelParsingContext(supported_extensions=["FEATURE_BUNDLE_1"])


class TestSimpleActionLetBindingsParsing:
    """Tests for parsing let bindings in SimpleAction with full validation."""

    def _decode(
        self,
        bash_data: dict[str, Any],
        param_defs: list[dict] | None = None,
        task_param_defs: list[dict] | None = None,
    ) -> Any:
        """Decode a job template with a bash SimpleAction."""
        step: dict[str, Any] = {"name": "TestStep", "bash": bash_data}
        if task_param_defs:
            step["parameterSpace"] = {"taskParameterDefinitions": task_param_defs}
        template: dict[str, Any] = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": list(EXTENSIONS),
            "name": "TestJob",
            "steps": [step],
        }
        if param_defs:
            template["parameterDefinitions"] = param_defs
        return decode_job_template(template=template, supported_extensions=EXTENSIONS)

    def test_single_binding(self) -> None:
        """SimpleAction with a single let binding."""
        template = self._decode({"let": ["x = 1"], "script": "echo {{x}}"})
        assert len(template.steps[0].bash.let) == 1
        assert template.steps[0].bash.let[0].name == "x"
        assert template.steps[0].bash.let[0].expression == "1"

    def test_multiple_bindings(self) -> None:
        """SimpleAction with multiple let bindings."""
        template = self._decode(
            {"let": ["x = 1", "y = 2", "z = 3"], "script": "echo {{x}} {{y}} {{z}}"}
        )
        assert len(template.steps[0].bash.let) == 3
        assert [b.name for b in template.steps[0].bash.let] == ["x", "y", "z"]
        assert [b.expression for b in template.steps[0].bash.let] == ["1", "2", "3"]

    def test_chained_bindings(self) -> None:
        """Later bindings can reference earlier ones."""
        template = self._decode({"let": ["a = 5", "b = a + 1"], "script": "echo {{b}}"})
        assert len(template.steps[0].bash.let) == 2
        assert template.steps[0].bash.let[0].name == "a"
        assert template.steps[0].bash.let[1].name == "b"
        assert template.steps[0].bash.let[1].expression == "a + 1"

    def test_binding_with_param_reference(self) -> None:
        """Binding can reference Param values."""
        template = self._decode(
            {"let": ["val = Param.Count + 1"], "script": "echo {{val}}"},
            param_defs=[{"name": "Count", "type": "INT", "default": "5"}],
        )
        assert template.steps[0].bash.let[0].name == "val"
        assert template.steps[0].bash.let[0].expression == "Param.Count + 1"

    def test_binding_with_task_param_reference(self) -> None:
        """Binding can reference Task.Param values."""
        template = self._decode(
            {"let": ["frame = Task.Param.Frame * 2"], "script": "echo {{frame}}"},
            task_param_defs=[{"name": "Frame", "type": "INT", "range": "1-10"}],
        )
        assert template.steps[0].bash.let[0].name == "frame"
        assert template.steps[0].bash.let[0].expression == "Task.Param.Frame * 2"

    def test_binding_with_list_comprehension(self) -> None:
        """Binding can use list comprehension."""
        template = self._decode(
            {"let": ["items = [x * 2 for x in range(5)]"], "script": "echo {{items}}"}
        )
        assert template.steps[0].bash.let[0].name == "items"
        assert template.steps[0].bash.let[0].expression == "[x * 2 for x in range(5)]"

    def test_binding_used_in_args(self) -> None:
        """Binding can be used in args field."""
        template = self._decode(
            {
                "let": ["output = '/tmp/out.txt'"],
                "script": "process",
                "args": ["--output", "{{output}}"],
            }
        )
        assert template.steps[0].bash.let[0].name == "output"
        assert len(template.steps[0].bash.args) == 2
        assert template.steps[0].bash.args[0] == "--output"
        assert "{{output}}" in str(template.steps[0].bash.args[1])


class TestSimpleActionLetBindingsExtensionRequirements:
    """Tests for extension requirements for SimpleAction let bindings."""

    def test_requires_expr_extension(self) -> None:
        """Let bindings require EXPR extension in addition to FEATURE_BUNDLE_1."""
        with pytest.raises(ValidationError, match="EXPR"):
            _parse_model(
                model=SimpleAction,
                obj={"let": ["x = 1"], "script": "echo"},
                context=fb1_only_context(),
            )

    def test_works_with_both_extensions(self) -> None:
        """Let bindings work when both extensions are enabled."""
        result = _parse_model(
            model=SimpleAction,
            obj={"let": ["x = 1"], "script": "echo {{x}}"},
            context=fb1_expr_context(),
        )
        assert result.let is not None


class TestSimpleActionLetBindingsValidation:
    """Tests for validation of let bindings in SimpleAction."""

    def _parse(self, data: dict[str, Any]) -> SimpleAction:
        return _parse_model(model=SimpleAction, obj=data, context=fb1_expr_context())

    def test_empty_list_rejected(self) -> None:
        """Empty let bindings list is rejected."""
        with pytest.raises(ValidationError, match="at least one"):
            self._parse({"let": [], "script": "echo"})

    def test_max_50_bindings(self) -> None:
        """Cannot exceed 50 bindings."""
        with pytest.raises(ValidationError, match="50"):
            self._parse({"let": [f"x{i} = {i}" for i in range(51)], "script": "echo"})

    def test_no_shadowing_same_block(self) -> None:
        """Cannot shadow a binding in the same block."""
        with pytest.raises(ValidationError, match="shadows"):
            self._parse({"let": ["x = 1", "y = 2", "x = 3"], "script": "echo"})

    def test_no_self_reference(self) -> None:
        """Binding cannot reference itself."""
        with pytest.raises(ValidationError, match="cannot reference itself"):
            self._parse({"let": ["x = x + 1"], "script": "echo"})


class TestSimpleActionLetBindingsInStepTemplate:
    """Tests for SimpleAction let bindings within StepTemplate context."""

    def _parse_step(self, data: dict[str, Any]) -> StepTemplate:
        return _parse_model(model=StepTemplate, obj=data, context=fb1_expr_context())

    def test_bash_with_let_bindings(self) -> None:
        """Bash SimpleAction with let bindings."""
        result = self._parse_step(
            {
                "name": "TestStep",
                "bash": {
                    "let": ["msg = 'hello world'"],
                    "script": "echo {{msg}}",
                },
            }
        )
        assert result.bash is not None
        assert result.bash.let is not None
        assert result.bash.let[0].name == "msg"

    def test_python_with_let_bindings(self) -> None:
        """Python SimpleAction with let bindings."""
        result = self._parse_step(
            {
                "name": "TestStep",
                "python": {
                    "let": ["count = 10"],
                    "script": "print({{count}})",
                },
            }
        )
        assert result.python is not None
        assert result.python.let is not None
        assert result.python.let[0].name == "count"

    def test_step_let_available_to_simple_action(self) -> None:
        """Step-level let bindings are available to SimpleAction."""
        result = self._parse_step(
            {
                "name": "TestStep",
                "let": ["step_val = 100"],
                "bash": {
                    "let": ["action_val = step_val + 1"],
                    "script": "echo {{action_val}}",
                },
            }
        )
        assert result.let is not None
        assert result.bash is not None
        assert result.bash.let is not None

    def test_simple_action_can_use_different_name(self) -> None:
        """SimpleAction can define different names than step."""
        result = self._parse_step(
            {
                "name": "TestStep",
                "let": ["x = 100"],
                "bash": {
                    "let": ["y = x + 1"],
                    "script": "echo {{y}}",
                },
            }
        )
        assert result.let is not None
        assert result.let[0].name == "x"
        assert result.bash is not None
        assert result.bash.let is not None
        assert result.bash.let[0].name == "y"


class TestSimpleActionLetBindingsCreateJob:
    """Integration tests for SimpleAction let bindings with create_job.

    Note: When create_job is called, SimpleAction syntax sugar is resolved into
    a regular StepScript. The SimpleAction let bindings are transferred
    to the StepScript.let field.
    """

    def test_simple_action_let_binding_preserved_after_desugar(self) -> None:
        """SimpleAction let bindings are preserved in StepScript after de-sugaring."""
        from openjd.model import create_job, decode_job_template

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1", "EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "bash": {
                            "let": ["msg = 'hello'"],
                            "script": "echo {{msg}}",
                        },
                    }
                ],
            },
            supported_extensions=["FEATURE_BUNDLE_1", "EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        # After de-sugaring, the step has a script (not bash)
        assert job.steps[0].script is not None
        # The let bindings from SimpleAction should be in the StepScript
        assert job.steps[0].script.let is not None
        assert job.steps[0].script.let[0].name == "msg"

    def test_step_and_simple_action_let_bindings_combined(self) -> None:
        """Step-level and SimpleAction let bindings work together after de-sugaring."""
        from openjd.model import create_job, decode_job_template

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1", "EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [{"name": "Base", "type": "INT", "default": "10"}],
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["multiplier = Param.Base * 2"],  # Step-level
                        "bash": {
                            "let": ["result = multiplier + 5"],  # SimpleAction-level
                            "script": "echo {{result}}",
                        },
                    }
                ],
            },
            supported_extensions=["FEATURE_BUNDLE_1", "EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        # SimpleAction let bindings should be in the StepScript
        assert job.steps[0].script is not None
        assert job.steps[0].script.let is not None
        assert job.steps[0].script.let[0].name == "result"

    def test_simple_action_let_binding_with_task_param(self) -> None:
        """SimpleAction let binding referencing Task.Param is preserved."""
        from openjd.model import create_job, decode_job_template

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["FEATURE_BUNDLE_1", "EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Frame", "type": "INT", "range": "1-10"}
                            ]
                        },
                        "bash": {
                            "let": ["output = '/renders/frame_' + string(Task.Param.Frame)"],
                            "script": "render --output {{output}}",
                        },
                    }
                ],
            },
            supported_extensions=["FEATURE_BUNDLE_1", "EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        assert job.steps[0].script is not None
        # SimpleAction let bindings should be preserved
        assert job.steps[0].script.let is not None
        assert job.steps[0].script.let[0].name == "output"


class TestSimpleActionLetBindingsTypeErrors:
    """Tests for type errors in SimpleAction let bindings."""

    def test_type_error_in_simple_action_binding(self) -> None:
        """Type error in SimpleAction let binding is caught at decode time."""
        from openjd.model import decode_job_template
        from openjd.model._errors import DecodeValidationError

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["FEATURE_BUNDLE_1", "EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Count", "type": "INT", "default": "5"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "bash": {
                                "let": ['bad = Param.Count + "hello"'],
                                "script": "echo",
                            },
                        }
                    ],
                },
                supported_extensions=["FEATURE_BUNDLE_1", "EXPR"],
            )
        expected = "".join(
            [
                "Cannot use '+' operator with int and string\n",
                '  bad = Param.Count + "hello"\n',
                "        ~~~~~~~~~~~~^~~~~~~~~",
            ]
        )
        assert expected in str(exc_info.value)

    def test_chained_type_error_in_simple_action(self) -> None:
        """Chained type error in SimpleAction let bindings."""
        from openjd.model import decode_job_template
        from openjd.model._errors import DecodeValidationError

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["FEATURE_BUNDLE_1", "EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Count", "type": "INT", "default": "5"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "bash": {
                                "let": [
                                    "x = Param.Count",  # INT
                                    "y = x + 1",  # INT
                                    'bad = y + "oops"',  # INT + STRING = error
                                ],
                                "script": "echo",
                            },
                        }
                    ],
                },
                supported_extensions=["FEATURE_BUNDLE_1", "EXPR"],
            )
        expected = "".join(
            [
                "Cannot use '+' operator with int and string\n",
                '  bad = y + "oops"\n',
                "        ~~^~~~~~~~",
            ]
        )
        assert expected in str(exc_info.value)


class TestSimpleActionLetBindingsWithAllInterpreters:
    """Tests for let bindings with all interpreter types."""

    def _parse_step(self, data: dict[str, Any]) -> StepTemplate:
        return _parse_model(model=StepTemplate, obj=data, context=fb1_expr_context())

    @pytest.mark.parametrize("interpreter", ["bash", "python", "cmd", "powershell", "node"])
    def test_interpreter_with_let_bindings(self, interpreter: str) -> None:
        """All interpreter types support let bindings."""
        result = self._parse_step(
            {
                "name": "TestStep",
                interpreter: {
                    "let": ["x = 42"],
                    "script": "echo {{x}}",
                },
            }
        )
        action = getattr(result, interpreter)
        assert action is not None
        assert action.let is not None
        assert action.let[0].name == "x"

    @pytest.mark.parametrize("interpreter", ["bash", "python", "cmd", "powershell", "node"])
    def test_interpreter_let_with_args(self, interpreter: str) -> None:
        """All interpreter types support let bindings used in args."""
        result = self._parse_step(
            {
                "name": "TestStep",
                interpreter: {
                    "let": ["output = '/tmp/out'"],
                    "script": "process",
                    "args": ["--output", "{{output}}"],
                },
            }
        )
        action = getattr(result, interpreter)
        assert action is not None
        assert action.let is not None
        assert action.args is not None
