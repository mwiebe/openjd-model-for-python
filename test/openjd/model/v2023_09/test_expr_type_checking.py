# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""End-to-end tests for EXPR extension type checking during template parsing."""

import pytest
from openjd.model import decode_job_template, DecodeValidationError


class TestExprTypeCheckingInHostContext:
    """Tests for type checking in host context (command/args - SESSION/TASK scope)."""

    def test_path_join_in_args(self):
        """PATH / STRING should work in args (host context)."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "OutputDir", "type": "PATH", "default": "/output"},
                {"name": "Filename", "type": "STRING", "default": "result.txt"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{ Param.OutputDir / Param.Filename }}"],
                            }
                        }
                    },
                }
            ],
        }
        # Should not raise
        decode_job_template(template=template, supported_extensions=["EXPR"])

    def test_apply_path_mapping_in_args(self):
        """apply_path_mapping should be available in args (host context)."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "InputFile", "type": "PATH", "default": "/input/file.txt"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "cat",
                                "args": ["{{ apply_path_mapping(Param.InputFile) }}"],
                            }
                        }
                    },
                }
            ],
        }
        # Should not raise - apply_path_mapping is available in host context
        decode_job_template(template=template, supported_extensions=["EXPR"])

    def test_path_properties_in_args(self):
        """Path properties like .stem, .name should work in args."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "InputFile", "type": "PATH", "default": "/input/file.txt"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": [
                                    "{{ Param.InputFile.stem }}",
                                    "{{ Param.InputFile.name }}",
                                    "{{ Param.InputFile.parent }}",
                                ],
                            }
                        }
                    },
                }
            ],
        }
        decode_job_template(template=template, supported_extensions=["EXPR"])

    def test_type_error_in_args(self):
        """Type errors in args should be caught during parsing."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "Count", "type": "INT", "default": "5"},
                {"name": "Name", "type": "STRING", "default": "test"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                # INT doesn't have .upper() method
                                "args": ["{{ Param.Count.upper() }}"],
                            }
                        }
                    },
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=template, supported_extensions=["EXPR"])
        error = str(exc_info.value)
        expected = "".join(
            [
                "upper() is not available for int. Available for: string\n",
                "  Param.Count.upper()\n",
                "  ~~~~~~~~~~~~^~~~~~~",
            ]
        )
        assert expected in error

    def test_undefined_symbol_in_args(self):
        """Undefined symbols in args should be caught during parsing."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{ Param.DoesNotExist }}"],
                            }
                        }
                    },
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=template, supported_extensions=["EXPR"])
        error = str(exc_info.value)
        expected = "".join(
            [
                "Undefined variable: Param.DoesNotExist\n",
                "  Param.DoesNotExist\n",
                "  ~~~~~~^~~~~~~~~~~~",
            ]
        )
        assert expected in error


class TestExprTypeCheckingInSubmissionContext:
    """Tests for type checking in submission context (job name - TEMPLATE scope)."""

    def test_apply_path_mapping_not_in_job_name(self):
        """apply_path_mapping should NOT be available in job name (submission context)."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            # Use RawParam.InputFile since Param.InputFile is not available in TEMPLATE scope
            "name": "{{ apply_path_mapping(RawParam.InputFile) }}",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "InputFile", "type": "PATH", "default": "/input/file.txt"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=template, supported_extensions=["EXPR"])
        error = str(exc_info.value)
        expected = "".join(
            [
                "Unknown function: apply_path_mapping\n",
                "  apply_path_mapping(RawParam.InputFile)\n",
                "  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )
        assert expected in error

    def test_path_join_in_step_script(self):
        """PATH / STRING should work in step script (host context)."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "parameterDefinitions": [
                {"name": "OutputDir", "type": "PATH", "default": "/output"},
                {"name": "Filename", "type": "STRING", "default": "result.txt"},
            ],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {
                            "onRun": {"command": "echo {{ Param.OutputDir / Param.Filename }}"}
                        }
                    },
                }
            ],
        }
        decode_job_template(template=template, supported_extensions=["EXPR"])


class TestExprTypeCheckingInTaskContext:
    """Tests for type checking with task parameters (TASK scope)."""

    def test_task_param_in_args(self):
        """Task parameters should be available in args."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "steps": [
                {
                    "name": "Step",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": [1, 2, 3]}
                        ]
                    },
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "render",
                                "args": ["--frame", "{{ Task.Param.Frame }}"],
                            }
                        }
                    },
                }
            ],
        }
        decode_job_template(template=template, supported_extensions=["EXPR"])

    def test_task_param_type_error(self):
        """Type errors with task parameters should be caught."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test",
            "extensions": ["EXPR"],
            "steps": [
                {
                    "name": "Step",
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Frame", "type": "INT", "range": [1, 2, 3]}
                        ]
                    },
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "render",
                                # INT doesn't have .stem property
                                "args": ["{{ Task.Param.Frame.stem }}"],
                            }
                        }
                    },
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=template, supported_extensions=["EXPR"])
        error = str(exc_info.value)
        expected = "".join(
            [
                "'stem' property is not available for int. Available for: path\n",
                "  Task.Param.Frame.stem\n",
                "  ~~~~~~~~~~~~~~~~~^~~~",
            ]
        )
        assert expected in error
