# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for let bindings (EXPR extension)."""

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model import DecodeValidationError, create_job, decode_job_template
from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    EnvironmentScript,
    EnvironmentTemplate,
    JobTemplate,
    LetBinding,
    ModelParsingContext,
    StepScript,
    StepTemplate,
)


class TestLetBinding:
    """Tests for the LetBinding class."""

    @pytest.mark.parametrize(
        "value,expected_name,expected_expr",
        [
            pytest.param("x = 1", "x", "1", id="simple"),
            pytest.param("x=1", "x", "1", id="no-spaces"),
            pytest.param("x  =  1", "x", "1", id="extra-spaces"),
            pytest.param("x\t=\t1", "x", "1", id="tabs"),
            pytest.param("_private = 1", "_private", "1", id="underscore-prefix"),
            pytest.param("x2 = 1", "x2", "1", id="with-digit"),
            pytest.param("myVar = Param.Value + 1", "myVar", "Param.Value + 1", id="complex-expr"),
            pytest.param(
                "x = [i for i in range(10)]", "x", "[i for i in range(10)]", id="list-comp"
            ),
        ],
    )
    def test_parse_success(self, value: str, expected_name: str, expected_expr: str) -> None:
        binding = LetBinding(value)
        assert binding.name == expected_name
        assert binding.expression == expected_expr

    @pytest.mark.parametrize(
        "value,error_match",
        [
            pytest.param("x", "'='", id="no-equals"),
            pytest.param("= 1", "name before", id="no-name"),
            pytest.param("x =", "expression after", id="no-expression"),
            pytest.param("Param = 1", "lowercase", id="uppercase-start"),
            pytest.param("1x = 1", "lowercase", id="digit-start"),
            pytest.param("x = 1 +", "Invalid expression", id="syntax-error"),
            pytest.param("x = (1, 2", "Invalid expression", id="unclosed-paren"),
            pytest.param("a" * 513 + " = 1", "512", id="name-too-long"),
        ],
    )
    def test_parse_fails(self, value: str, error_match: str) -> None:
        with pytest.raises(ValueError, match=error_match):
            LetBinding(value)


class TestLetBindingSyntaxErrorCarets:
    """Test that syntax errors in let bindings include caret pointers."""

    def test_unclosed_paren_caret(self):
        """Unclosed parenthesis shows caret at opening paren in original binding."""
        with pytest.raises(ValueError) as exc_info:
            LetBinding("x = (1 + 2")
        expected = [
            "Invalid expression in let binding 'x': Syntax error: '(' was never closed\n",
            "  x = (1 + 2\n",
            "      ^",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unclosed_paren_with_whitespace(self):
        """Caret aligns correctly when binding has extra whitespace."""
        with pytest.raises(ValueError) as exc_info:
            LetBinding("  x  =  (1 + 2  ")
        expected = [
            "Invalid expression in let binding 'x': Syntax error: '(' was never closed\n",
            "    x  =  (1 + 2\n",
            "          ^",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_unclosed_bracket_caret(self):
        """Unclosed bracket shows caret at opening bracket."""
        with pytest.raises(ValueError) as exc_info:
            LetBinding("items = [1, 2, 3")
        expected = [
            "Invalid expression in let binding 'items': Syntax error: '[' was never closed\n",
            "  items = [1, 2, 3\n",
            "          ^",
        ]
        assert str(exc_info.value) == "".join(expected)

    def test_multiline_error_on_line_3(self):
        """Multi-line expression error shows caret on the correct line."""
        with pytest.raises(ValueError) as exc_info:
            LetBinding("x = (1 +\n  [2\n  3)")
        expected = [
            "Invalid expression in let binding 'x': Syntax error: closing parenthesis ')' does not match opening parenthesis '[' on line 3\n",
            "    3)\n",
            "     ^",
        ]
        assert str(exc_info.value) == "".join(expected)


class TestStepScriptLetBindings:
    """Tests for let bindings in StepScript."""

    def _parse(self, data: dict[str, Any]) -> StepScript:
        ctx = ModelParsingContext(supported_extensions=["EXPR"])
        return _parse_model(model=StepScript, obj=data, context=ctx)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {
                    "let": ["x = 1"],
                    "actions": {"onRun": {"command": "echo"}},
                },
                id="single-binding",
            ),
            pytest.param(
                {
                    "let": ["x = 1", "y = x + 1"],
                    "actions": {"onRun": {"command": "echo"}},
                },
                id="multiple-bindings",
            ),
            pytest.param(
                {
                    "let": ["udim = 1001 + Task.Param.TileV * 10"],
                    "actions": {"onRun": {"command": "echo", "args": ["{{ udim }}"]}},
                },
                id="binding-used-in-action",
            ),
        ],
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        self._parse(data)

    def test_requires_expr_extension(self) -> None:
        ctx = ModelParsingContext()  # No EXPR extension
        with pytest.raises(ValidationError, match="EXPR extension"):
            _parse_model(
                model=StepScript,
                obj={"let": ["x = 1"], "actions": {"onRun": {"command": "echo"}}},
                context=ctx,
            )

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            self._parse({"let": [], "actions": {"onRun": {"command": "echo"}}})

    def test_max_50_bindings(self) -> None:
        with pytest.raises(ValidationError, match="50"):
            self._parse(
                {
                    "let": [f"x{i} = {i}" for i in range(51)],
                    "actions": {"onRun": {"command": "echo"}},
                }
            )

    def test_no_shadowing_same_block(self) -> None:
        with pytest.raises(ValidationError, match="shadows"):
            self._parse(
                {
                    "let": ["x = 32", "y = x * 5", "x = -1"],
                    "actions": {"onRun": {"command": "echo"}},
                }
            )

    def test_no_self_reference(self) -> None:
        with pytest.raises(ValidationError, match="cannot reference itself"):
            self._parse(
                {
                    "let": ["x = x + 1"],
                    "actions": {"onRun": {"command": "echo"}},
                }
            )


class TestStepTemplateLetBindings:
    """Tests for let bindings in StepTemplate."""

    def _parse(self, data: dict[str, Any]) -> StepTemplate:
        ctx = ModelParsingContext(supported_extensions=["EXPR"])
        return _parse_model(model=StepTemplate, obj=data, context=ctx)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {
                    "name": "TestStep",
                    "let": ["x = 1"],
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                },
                id="step-level-binding",
            ),
            pytest.param(
                {
                    "name": "TestStep",
                    "let": ["max_u = 9"],
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "U", "type": "INT", "range": "0-{{ max_u }}"}
                        ]
                    },
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                },
                id="binding-used-in-param-space",
            ),
        ],
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        self._parse(data)

    def test_no_shadowing_step_to_script(self) -> None:
        with pytest.raises(ValidationError, match="shadows"):
            self._parse(
                {
                    "name": "TestStep",
                    "let": ["x = 1"],
                    "script": {
                        "let": ["x = 2"],  # Shadows step-level x
                        "actions": {"onRun": {"command": "echo"}},
                    },
                }
            )

    def test_no_shadowing_step_to_environment(self) -> None:
        with pytest.raises(ValidationError, match="shadows"):
            self._parse(
                {
                    "name": "TestStep",
                    "let": ["x = 1"],
                    "stepEnvironments": [
                        {
                            "name": "TestEnv",
                            "script": {
                                "let": ["x = 2"],  # Shadows step-level x
                                "actions": {"onEnter": {"command": "setup"}},
                            },
                        }
                    ],
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            )

    def test_script_can_use_different_name(self) -> None:
        # Script can define different names than step
        step = self._parse(
            {
                "name": "TestStep",
                "let": ["x = 1"],
                "script": {
                    "let": ["y = 2"],
                    "actions": {"onRun": {"command": "echo"}},
                },
            }
        )
        assert step.let is not None
        assert step.let[0].name == "x"
        assert step.script is not None
        assert step.script.let is not None
        assert step.script.let[0].name == "y"


class TestEnvironmentScriptLetBindings:
    """Tests for let bindings in EnvironmentScript."""

    def _parse(self, data: dict[str, Any]) -> EnvironmentScript:
        ctx = ModelParsingContext(supported_extensions=["EXPR"])
        return _parse_model(model=EnvironmentScript, obj=data, context=ctx)

    def test_parse_success(self) -> None:
        script = self._parse(
            {
                "let": ["config_path = Env.File.config"],
                "actions": {"onEnter": {"command": "setup"}},
            }
        )
        assert script.let is not None
        assert script.let[0].name == "config_path"

    def test_requires_expr_extension(self) -> None:
        ctx = ModelParsingContext()
        with pytest.raises(ValidationError, match="EXPR extension"):
            _parse_model(
                model=EnvironmentScript,
                obj={"let": ["x = 1"], "actions": {"onEnter": {"command": "setup"}}},
                context=ctx,
            )


class TestLetBindingsCreateJob:
    """Tests for let bindings runtime evaluation in create_job.

    Note: Only step-level let bindings are evaluated at job creation time.
    Script-level let bindings are evaluated at task execution time by the sessions library.
    """

    def test_step_let_binding_in_param_space(self) -> None:
        """Step-level let binding used in parameterSpace range."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["max_frame = 10"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Frame", "type": "INT", "range": "1-{{ max_frame }}"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        # The range should be resolved to "1-10"
        assert step.parameterSpace is not None
        assert str(step.parameterSpace.taskParameterDefinitions["Frame"].range) == "1-10"

    def test_step_let_binding_arithmetic(self) -> None:
        """Step-level let binding with arithmetic expression."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [{"name": "StartFrame", "type": "INT", "default": "1"}],
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["end_frame = Param.StartFrame + 9"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {
                                    "name": "Frame",
                                    "type": "INT",
                                    "range": "{{ Param.StartFrame }}-{{ end_frame }}",
                                }
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        assert step.parameterSpace is not None
        assert str(step.parameterSpace.taskParameterDefinitions["Frame"].range) == "1-10"

    def test_chained_let_bindings(self) -> None:
        """Later let bindings can reference earlier ones."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["a = 5", "b = a * 2", "c = b + 1"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Val", "type": "INT", "range": "1-{{ c }}"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        # c = (5 * 2) + 1 = 11
        assert step.parameterSpace is not None
        assert str(step.parameterSpace.taskParameterDefinitions["Val"].range) == "1-11"

    def test_step_let_binding_with_list(self) -> None:
        """Step-level let binding that produces a list for range."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["frames = [1, 5, 10]"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Frame", "type": "INT", "range": "{{ frames }}"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        assert step.parameterSpace is not None
        assert list(step.parameterSpace.taskParameterDefinitions["Frame"].range) == [1, 5, 10]

    def test_step_let_binding_string_concat(self) -> None:
        """Step-level let binding with string concatenation."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [{"name": "Prefix", "type": "STRING", "default": "shot"}],
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["shot_name = Param.Prefix + '_001'"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Shot", "type": "STRING", "range": ["{{ shot_name }}"]}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        assert step.parameterSpace is not None
        assert list(step.parameterSpace.taskParameterDefinitions["Shot"].range) == ["shot_001"]

    def test_multiple_steps_independent_let_bindings(self) -> None:
        """Let bindings in different steps are independent with no cross-talk."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "Step1",
                        "let": ["a = 10", "b = a + 5"],  # b is int (15)
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Val", "type": "INT", "range": "1-{{ b }}"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    },
                    {
                        "name": "Step2",
                        "let": ["b = 'hello'", "c = b + '_world'"],  # b is string
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Name", "type": "STRING", "range": ["{{ c }}"]}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    },
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})

        # Step1: b = 10 + 5 = 15 (int)
        step1 = job.steps[0]
        assert step1.parameterSpace is not None
        assert str(step1.parameterSpace.taskParameterDefinitions["Val"].range) == "1-15"

        # Step2: b = 'hello', c = 'hello_world' (string) - no interference from Step1's b
        step2 = job.steps[1]
        assert step2.parameterSpace is not None
        assert list(step2.parameterSpace.taskParameterDefinitions["Name"].range) == ["hello_world"]

    def test_let_binding_with_path_operations(self) -> None:
        """Let binding with path concatenation used in STRING range."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [
                    {"name": "OutputDir", "type": "PATH", "default": "/renders"}
                ],
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["output_path = string(Param.OutputDir / 'frames')"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Path", "type": "STRING", "range": ["{{ output_path }}"]}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        assert step.parameterSpace is not None
        paths = list(step.parameterSpace.taskParameterDefinitions["Path"].range)
        assert len(paths) == 1
        assert isinstance(paths[0], str)
        assert paths[0].replace("\\", "/") == "/renders/frames"

    def test_let_binding_error_propagates(self) -> None:
        """Division by zero in let binding is caught at decode_job_template time."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ["x = 1 / 0"],  # Division by zero
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Val", "type": "INT", "range": "1-{{ x }}"}
                                ]
                            },
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        expected = "".join(
            [
                "Division by zero\n",
                "  x = 1 / 0\n",
                "      ~~^~~",
            ]
        )
        assert expected in str(exc_info.value)

    def test_let_binding_undefined_symbol_error(self) -> None:
        """Undefined symbol in let binding expression is caught at decode_job_template time.

        This validates that undefined symbols in let bindings are caught at parse time
        (decode_job_template) rather than runtime (create_job), providing better UX
        by failing fast with clear error messages.
        """

        with pytest.raises(DecodeValidationError, match="undefined_var"):
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ["x = undefined_var + 1"],
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "Val", "type": "INT", "range": "1-{{ x }}"}
                                ]
                            },
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )


class TestLetBindingTypeErrors:
    """Test that type errors in let bindings are caught with proper error messages and carets."""

    def test_int_plus_string_type_error(self) -> None:
        """Adding int and string produces type error with caret at operator."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Count", "type": "INT", "default": "5"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ['bad = Param.Count + "hello"'],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        expected = [
            "Cannot use '+' operator with int and string\n",
            '  bad = Param.Count + "hello"\n',
            "        ~~~~~~~~~~~~^~~~~~~~~",
        ]
        assert "".join(expected) in str(exc_info.value)

    def test_type_propagation_catches_chained_error(self) -> None:
        """Type error in chained binding where earlier binding's type propagates."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Count", "type": "INT", "default": "5"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": [
                                "x = Param.Count",  # x is INT
                                "y = x + 1",  # y is INT
                                'bad = y + "oops"',  # INT + STRING = error
                            ],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        expected = [
            "Cannot use '+' operator with int and string\n",
            '  bad = y + "oops"\n',
            "        ~~^~~~~~~~",
        ]
        assert "".join(expected) in str(exc_info.value)

    def test_string_minus_error(self) -> None:
        """Subtraction on strings produces type error."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Name", "type": "STRING", "default": "test"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ['bad = Param.Name - "x"'],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        expected = [
            "Cannot use '-' operator with string and string\n",
            '  bad = Param.Name - "x"\n',
            "        ~~~~~~~~~~~^~~~~",
        ]
        assert "".join(expected) in str(exc_info.value)

    def test_valid_type_propagation_succeeds(self) -> None:
        """Valid chained bindings with correct types succeed."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [{"name": "Count", "type": "INT", "default": "5"}],
                "steps": [
                    {
                        "name": "TestStep",
                        "let": [
                            "x = Param.Count",  # INT
                            "y = x + 1",  # INT + INT = INT
                            "z = string(y)",  # string(INT) = STRING
                            'result = z + "_suffix"',  # STRING + STRING = STRING
                        ],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Out", "type": "STRING", "range": ["{{ result }}"]}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        step = job.steps[0]
        assert step.parameterSpace is not None
        assert list(step.parameterSpace.taskParameterDefinitions["Out"].range) == ["6_suffix"]

    def test_function_type_mismatch_error(self) -> None:
        """Calling function with wrong argument type produces error."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Name", "type": "STRING", "default": "test"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ["bad = abs(Param.Name)"],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        assert "No matching signature for abs(string)" in str(exc_info.value)

    def test_multiplication_type_error(self) -> None:
        """Invalid multiplication produces type error with caret."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "parameterDefinitions": [{"name": "Count", "type": "INT", "default": "5"}],
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ['bad = Param.Count * "five"'],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        expected = [
            "Cannot use '*' operator with int and string\n",
            '  bad = Param.Count * "five"\n',
            "        ~~~~~~~~~~~~^~~~~~~~",
        ]
        assert "".join(expected) in str(exc_info.value)


class TestJobEnvironmentLetBindings:
    """Tests for let bindings in job-level environments."""

    def test_job_environment_let_binding(self) -> None:
        """Job environment can have let bindings."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "jobEnvironments": [
                    {
                        "name": "TestEnv",
                        "script": {
                            "let": ["env_val = 42"],
                            "actions": {"onEnter": {"command": "echo", "args": ["{{ env_val }}"]}},
                        },
                    }
                ],
                "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR"],
        )
        assert template.jobEnvironments is not None
        assert template.jobEnvironments[0].script is not None
        assert template.jobEnvironments[0].script.let is not None
        assert template.jobEnvironments[0].script.let[0].name == "env_val"

    def test_job_environment_chained_let_bindings(self) -> None:
        """Job environment let bindings can reference earlier bindings."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "jobEnvironments": [
                    {
                        "name": "TestEnv",
                        "script": {
                            "let": ["a = 10", "b = a * 2", "msg = 'Value: ' + string(b)"],
                            "actions": {"onEnter": {"command": "echo", "args": ["{{ msg }}"]}},
                        },
                    }
                ],
                "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR"],
        )
        assert template.jobEnvironments is not None
        script = template.jobEnvironments[0].script
        assert script is not None
        env_let = script.let
        assert env_let is not None
        assert [b.name for b in env_let] == ["a", "b", "msg"]


class TestStepEnvironmentLetBindings:
    """Tests for let bindings in step environments referencing step-level bindings."""

    def test_step_environment_can_reference_step_let_binding(self) -> None:
        """Step environment let bindings can reference step-level let bindings."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["step_val = 100"],
                        "stepEnvironments": [
                            {
                                "name": "TestEnv",
                                "script": {
                                    "let": ["env_val = step_val + 5"],
                                    "actions": {
                                        "onEnter": {
                                            "command": "echo",
                                            "args": ["{{ env_val }}"],
                                        }
                                    },
                                },
                            }
                        ],
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        # Verify parsing succeeded - the step env references step_val
        job = create_job(job_template=template, job_parameter_values={})
        assert job.steps[0].stepEnvironments is not None

    def test_step_environment_chained_with_step_binding(self) -> None:
        """Step environment can chain bindings that start from step-level binding."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [{"name": "Base", "type": "INT", "default": "10"}],
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["multiplier = Param.Base * 2"],  # 20
                        "stepEnvironments": [
                            {
                                "name": "TestEnv",
                                "script": {
                                    "let": [
                                        "env_a = multiplier + 5",  # 25
                                        "env_b = env_a * 2",  # 50
                                    ],
                                    "actions": {
                                        "onEnter": {
                                            "command": "echo",
                                            "args": ["{{ env_b }}"],
                                        }
                                    },
                                },
                            }
                        ],
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        assert job.steps[0].stepEnvironments is not None

    def test_step_environment_cannot_shadow_step_binding(self) -> None:
        """Step environment let binding cannot shadow step-level binding."""

        with pytest.raises(DecodeValidationError, match="shadows"):
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "steps": [
                        {
                            "name": "TestStep",
                            "let": ["x = 100"],
                            "stepEnvironments": [
                                {
                                    "name": "TestEnv",
                                    "script": {
                                        "let": ["x = 200"],  # Shadows step-level x
                                        "actions": {"onEnter": {"command": "echo"}},
                                    },
                                }
                            ],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )

    def test_multiple_step_environments_reference_step_binding(self) -> None:
        """Multiple step environments can each reference step-level bindings."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "let": ["base = 50"],
                        "stepEnvironments": [
                            {
                                "name": "Env1",
                                "script": {
                                    "let": ["val1 = base + 1"],
                                    "actions": {
                                        "onEnter": {"command": "echo", "args": ["{{ val1 }}"]}
                                    },
                                },
                            },
                            {
                                "name": "Env2",
                                "script": {
                                    "let": ["val2 = base + 2"],
                                    "actions": {
                                        "onEnter": {"command": "echo", "args": ["{{ val2 }}"]}
                                    },
                                },
                            },
                        ],
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        assert job.steps[0].stepEnvironments is not None
        assert len(job.steps[0].stepEnvironments) == 2


class TestLetBindingsRequireExprInTemplate:
    """Tests that let bindings are rejected when the template does not declare
    the EXPR extension, even when EXPR is in supported_extensions.

    This validates that the extensions field validator runs (via validate_default=True)
    to clear context.extensions when the template omits the extensions field.
    """

    def test_job_template_let_rejected_without_extensions_field(self) -> None:
        """JobTemplate with let but no extensions field should fail."""
        with pytest.raises(ValidationError, match="EXPR extension"):
            _parse_model(
                model=JobTemplate,
                obj={
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": "Test",
                    "steps": [
                        {
                            "name": "S1",
                            "let": ["x = 1"],
                            "script": {"actions": {"onRun": {"command": "echo"}}},
                        }
                    ],
                },
                context=ModelParsingContext(supported_extensions=["EXPR"]),
            )

    def test_job_template_let_accepted_with_expr_extension(self) -> None:
        """JobTemplate with let and extensions: [EXPR] should pass."""
        result = _parse_model(
            model=JobTemplate,
            obj={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "Test",
                "steps": [
                    {
                        "name": "S1",
                        "let": ["x = 1"],
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            context=ModelParsingContext(supported_extensions=["EXPR"]),
        )
        assert result.steps[0].let is not None

    def test_env_template_let_rejected_without_extensions_field(self) -> None:
        """EnvironmentTemplate with let but no extensions field should fail."""
        with pytest.raises(ValidationError, match="EXPR extension"):
            _parse_model(
                model=EnvironmentTemplate,
                obj={
                    "specificationVersion": "environment-2023-09",
                    "environment": {
                        "name": "TestEnv",
                        "script": {
                            "let": ["x = 1"],
                            "actions": {"onEnter": {"command": "setup"}},
                        },
                    },
                },
                context=ModelParsingContext(supported_extensions=["EXPR"]),
            )

    def test_env_template_let_accepted_with_expr_extension(self) -> None:
        """EnvironmentTemplate with let and extensions: [EXPR] should pass."""
        result = _parse_model(
            model=EnvironmentTemplate,
            obj={
                "specificationVersion": "environment-2023-09",
                "extensions": ["EXPR"],
                "environment": {
                    "name": "TestEnv",
                    "script": {
                        "let": ["x = 1"],
                        "actions": {"onEnter": {"command": "setup"}},
                    },
                },
            },
            context=ModelParsingContext(supported_extensions=["EXPR"]),
        )
        assert result.environment.script is not None
        assert result.environment.script.let is not None

    def test_let_binding_float_list_preserves_precision(self) -> None:
        """Float values in list let bindings preserve trailing zeros and scientific notation."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "Step",
                        "let": ["vals = [1.70, 2.50, 1.5e3]"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "X", "type": "INT", "range": "1-1"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        let_values = job.steps[0].resolvedBindings
        assert let_values is not None
        vals_binding = next(b for b in let_values if b["name"] == "vals")
        assert vals_binding["value"] == ["1.70", "2.50", "1.5e3"]

    def test_let_binding_scalar_float_preserves_precision(self) -> None:
        """Scalar float let bindings preserve trailing zeros and scientific notation."""

        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "Step",
                        "let": ["x = 1.30", "y = 2.5e10"],
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "V", "type": "INT", "range": "1-1"}
                            ]
                        },
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
        job = create_job(job_template=template, job_parameter_values={})
        let_values = job.steps[0].resolvedBindings
        assert let_values is not None
        x_binding = next(b for b in let_values if b["name"] == "x")
        assert x_binding["value"] == "1.30"
        y_binding = next(b for b in let_values if b["name"] == "y")
        assert y_binding["value"] == "2.5e10"


class TestLetBindingsHostContextSymbols:
    """Tests that let bindings in host-context scopes can reference Session.*, Task.Param.*, etc."""

    def test_script_let_session_working_directory(self) -> None:
        """StepScript let binding can reference Session.WorkingDirectory."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "script": {
                            "let": ["work_dir = Session.WorkingDirectory / 'output'"],
                            "actions": {"onRun": {"command": "echo", "args": ["{{work_dir}}"]}},
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )

    def test_script_let_task_param(self) -> None:
        """StepScript let binding can reference Task.Param.*."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "Frame", "type": "INT", "range": "1-10"}
                            ]
                        },
                        "script": {
                            "let": ["frame_str = string(Task.Param.Frame)"],
                            "actions": {"onRun": {"command": "echo", "args": ["{{frame_str}}"]}},
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )

    def test_script_let_session_has_path_mapping_rules(self) -> None:
        """StepScript let binding can reference Session.HasPathMappingRules."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "script": {
                            "let": ["has_rules = Session.HasPathMappingRules"],
                            "actions": {"onRun": {"command": "echo", "args": ["{{has_rules}}"]}},
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )

    def test_env_script_let_session_symbols(self) -> None:
        """EnvironmentScript let binding can reference Session.WorkingDirectory."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "steps": [
                    {
                        "name": "TestStep",
                        "stepEnvironments": [
                            {
                                "name": "Setup",
                                "script": {
                                    "let": ["work_dir = Session.WorkingDirectory / 'workspace'"],
                                    "actions": {
                                        "onEnter": {
                                            "command": "echo",
                                            "args": ["{{work_dir}}"],
                                        }
                                    },
                                },
                            }
                        ],
                        "script": {"actions": {"onRun": {"command": "echo"}}},
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )

    def test_simple_action_let_session_symbols(self) -> None:
        """SimpleAction let binding can reference Session.* and Task.Param.*."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR", "FEATURE_BUNDLE_1"],
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
                            "let": [
                                "out = Session.WorkingDirectory / 'renders'",
                                "frame_str = string(Task.Param.Frame)",
                            ],
                            "script": "echo {{repr_sh(out)}} {{frame_str}}",
                        },
                    }
                ],
            },
            supported_extensions=["EXPR", "FEATURE_BUNDLE_1"],
        )

    def test_script_let_type_error_with_session_symbol(self) -> None:
        """Type errors involving host-context symbols are still caught."""

        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(
                template={
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "TestJob",
                    "steps": [
                        {
                            "name": "TestStep",
                            "script": {
                                "let": ["bad = Session.WorkingDirectory + 5"],
                                "actions": {"onRun": {"command": "echo"}},
                            },
                        }
                    ],
                },
                supported_extensions=["EXPR"],
            )
        expected = [
            "Cannot use '+' operator with path and int\n",
            "  bad = Session.WorkingDirectory + 5\n",
            "        ~~~~~~~~~~~~~~~~~~~~~~~~~^~~",
        ]
        assert "".join(expected) in str(exc_info.value)

    def test_script_let_chained_with_session_symbol(self) -> None:
        """Chained let bindings work with host-context symbols."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [{"name": "SubDir", "type": "STRING", "default": "output"}],
                "steps": [
                    {
                        "name": "TestStep",
                        "script": {
                            "let": [
                                "work_dir = Session.WorkingDirectory / Param.SubDir",
                                "log_file = work_dir / 'render.log'",
                            ],
                            "actions": {"onRun": {"command": "echo", "args": ["{{log_file}}"]}},
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )

    def test_script_let_apply_path_mapping_available(self) -> None:
        """apply_path_mapping() is available in host-context let bindings."""

        decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": "TestJob",
                "parameterDefinitions": [
                    {"name": "InputFile", "type": "PATH", "default": "/input/file.exr"}
                ],
                "steps": [
                    {
                        "name": "TestStep",
                        "script": {
                            "let": [
                                "mapped = RawParam.InputFile.apply_path_mapping()",
                            ],
                            "actions": {"onRun": {"command": "echo", "args": ["{{mapped}}"]}},
                        },
                    }
                ],
            },
            supported_extensions=["EXPR"],
        )
