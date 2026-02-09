# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for PATH and LIST[PATH] parameter Param.* accessibility.

PATH and LIST[PATH] parameters define two variables:
- Param.<name>: Only accessible in host contexts (SESSION and TASK scopes)
- RawParam.<name>: Accessible in all contexts (TEMPLATE, SESSION, and TASK scopes)

The Param.* variable for path types is restricted to host contexts because
path mapping may be applied at runtime, so the resolved path value is only
available when running on a worker host.
"""

import pytest

from openjd.model import DecodeValidationError, decode_job_template


class TestPathParameterScope:
    """Tests that PATH parameter Param.* is only accessible in host contexts."""

    # --- TEMPLATE scope (non-host) - Param.* should NOT be accessible ---

    def test_path_param_not_in_job_name(self) -> None:
        """PATH Param.Foo should NOT be accessible in job name (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo {{Param.Foo}}",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=data)
        assert "name:" in str(exc_info.value)
        assert "Param.Foo" in str(exc_info.value)

    def test_path_param_not_in_parameter_space_range(self) -> None:
        """PATH Param.Foo should NOT be accessible in parameter space range (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Bar", "type": "STRING", "range": ["{{Param.Foo}}"]}
                        ]
                    },
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=data)
        assert "steps[0] -> parameterSpace -> taskParameterDefinitions[0] -> range[0]:" in str(
            exc_info.value
        )
        assert "Param.Foo" in str(exc_info.value)

    def test_path_param_not_in_int_range_start(self) -> None:
        """PATH Param.Foo should NOT be accessible in INT range start (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Bar", "type": "INT", "range": "{{Param.Foo}}"}
                        ]
                    },
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=data)
        assert "steps[0] -> parameterSpace -> taskParameterDefinitions[0] -> range:" in str(
            exc_info.value
        )
        assert "Param.Foo" in str(exc_info.value)

    # --- TEMPLATE scope (non-host) - RawParam.* SHOULD be accessible ---

    def test_path_rawparam_in_job_name(self) -> None:
        """PATH RawParam.Foo should be accessible in job name (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo {{RawParam.Foo}}",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        decode_job_template(template=data)

    def test_path_rawparam_in_parameter_space_range(self) -> None:
        """PATH RawParam.Foo should be accessible in parameter space range (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Bar", "type": "STRING", "range": ["{{RawParam.Foo}}"]}
                        ]
                    },
                }
            ],
        }
        decode_job_template(template=data)

    # --- SESSION scope (host) - Param.* SHOULD be accessible ---

    def test_path_param_in_environment_script(self) -> None:
        """PATH Param.Foo should be accessible in environment script (SESSION scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            "jobEnvironments": [
                {
                    "name": "Env",
                    "script": {"actions": {"onEnter": {"command": "echo {{Param.Foo}}"}}},
                }
            ],
        }
        decode_job_template(template=data)

    def test_path_param_in_step_environment_script(self) -> None:
        """PATH Param.Foo should be accessible in step environment script (SESSION scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "stepEnvironments": [
                        {
                            "name": "StepEnv",
                            "script": {"actions": {"onEnter": {"command": "echo {{Param.Foo}}"}}},
                        }
                    ],
                }
            ],
        }
        decode_job_template(template=data)

    # --- TASK scope (host) - Param.* SHOULD be accessible ---

    def test_path_param_in_step_script(self) -> None:
        """PATH Param.Foo should be accessible in step script (TASK scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo {{Param.Foo}}"}}},
                }
            ],
        }
        decode_job_template(template=data)

    def test_path_param_in_step_script_args(self) -> None:
        """PATH Param.Foo should be accessible in step script args (TASK scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "PATH"}],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {"onRun": {"command": "echo", "args": ["{{Param.Foo}}"]}}
                    },
                }
            ],
        }
        decode_job_template(template=data)


class TestListPathParameterScope:
    """Tests that LIST[PATH] parameter Param.* is only accessible in host contexts."""

    # --- TEMPLATE scope (non-host) - Param.* should NOT be accessible ---

    def test_list_path_param_not_in_job_name(self) -> None:
        """LIST[PATH] Param.Foo should NOT be accessible in job name (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo {{Param.Foo}}",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=data, supported_extensions=["EXPR"])
        assert "name:" in str(exc_info.value)
        assert "Param.Foo" in str(exc_info.value)

    def test_list_path_param_not_in_parameter_space_range(self) -> None:
        """LIST[PATH] Param.Foo should NOT be accessible in parameter space range (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Bar", "type": "STRING", "range": ["{{Param.Foo}}"]}
                        ]
                    },
                }
            ],
        }
        with pytest.raises(DecodeValidationError) as exc_info:
            decode_job_template(template=data, supported_extensions=["EXPR"])
        assert "steps[0] -> parameterSpace -> taskParameterDefinitions[0] -> range[0]:" in str(
            exc_info.value
        )
        assert "Param.Foo" in str(exc_info.value)

    # --- TEMPLATE scope (non-host) - RawParam.* SHOULD be accessible ---

    def test_list_path_rawparam_in_job_name(self) -> None:
        """LIST[PATH] RawParam.Foo should be accessible in job name (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo {{RawParam.Foo}}",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
        }
        decode_job_template(template=data, supported_extensions=["EXPR"])

    def test_list_path_rawparam_in_parameter_space_range(self) -> None:
        """LIST[PATH] RawParam.Foo should be accessible in parameter space range (TEMPLATE scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "parameterSpace": {
                        "taskParameterDefinitions": [
                            {"name": "Bar", "type": "STRING", "range": ["{{RawParam.Foo}}"]}
                        ]
                    },
                }
            ],
        }
        decode_job_template(template=data, supported_extensions=["EXPR"])

    # --- SESSION scope (host) - Param.* SHOULD be accessible ---

    def test_list_path_param_in_environment_script(self) -> None:
        """LIST[PATH] Param.Foo should be accessible in environment script (SESSION scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [{"name": "Step", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            "jobEnvironments": [
                {
                    "name": "Env",
                    "script": {"actions": {"onEnter": {"command": "echo {{Param.Foo}}"}}},
                }
            ],
        }
        decode_job_template(template=data, supported_extensions=["EXPR"])

    def test_list_path_param_in_step_environment_script(self) -> None:
        """LIST[PATH] Param.Foo should be accessible in step environment script (SESSION scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo"}}},
                    "stepEnvironments": [
                        {
                            "name": "StepEnv",
                            "script": {"actions": {"onEnter": {"command": "echo {{Param.Foo}}"}}},
                        }
                    ],
                }
            ],
        }
        decode_job_template(template=data, supported_extensions=["EXPR"])

    # --- TASK scope (host) - Param.* SHOULD be accessible ---

    def test_list_path_param_in_step_script(self) -> None:
        """LIST[PATH] Param.Foo should be accessible in step script (TASK scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [
                {
                    "name": "Step",
                    "script": {"actions": {"onRun": {"command": "echo {{Param.Foo}}"}}},
                }
            ],
        }
        decode_job_template(template=data, supported_extensions=["EXPR"])

    def test_list_path_param_in_step_script_args(self) -> None:
        """LIST[PATH] Param.Foo should be accessible in step script args (TASK scope)."""
        data = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "Foo",
            "parameterDefinitions": [{"name": "Foo", "type": "LIST[PATH]", "default": ["/tmp"]}],
            "steps": [
                {
                    "name": "Step",
                    "script": {
                        "actions": {"onRun": {"command": "echo", "args": ["{{Param.Foo}}"]}}
                    },
                }
            ],
        }
        decode_job_template(template=data, supported_extensions=["EXPR"])
