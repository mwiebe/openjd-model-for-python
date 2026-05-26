# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import tempfile
import pytest
from pathlib import Path
from typing import Any

from openjd.model._v1 import (
    JobParameterInputValues,
    ParameterValue,
    ParameterValueType,
    create_job,
    decode_environment_template,
    decode_job_template,
    preprocess_job_parameters,
)
from openjd.model._v1.types import (
    JobParameterType,
)
from openjd.model._v1.errors import (
    DecodeValidationError,
)


class _JobParamTypeCompat:
    """Wrapper to give Rust enum members a .value attribute like Python's enum.Enum."""

    def __init__(self, member):
        self._member = member
        self.value = member.as_str()

    def __repr__(self):
        return repr(self._member)


# The 2023-09 schema supported these four job parameter types.
JobParameterType_2023_09 = [
    _JobParamTypeCompat(JobParameterType.STRING),
    _JobParamTypeCompat(JobParameterType.INT),
    _JobParamTypeCompat(JobParameterType.FLOAT),
    _JobParamTypeCompat(JobParameterType.PATH),
]


def _parameter_value_type_from_str(s: str) -> JobParameterType:
    """Look up a JobParameterType member by its string name."""
    return getattr(JobParameterType, s)


minimal_steps_v2023_09 = [
    {"name": "step", "script": {"actions": {"onRun": {"command": "do thing"}}}}
]
minimal_environment_2023_09 = {
    "name": "env",
    "script": {"actions": {"onEnter": {"command": "do a thing"}}},
}


class TestPreprocessJobParameters_2023_09:  # noqa: N801
    """Tests for preprocess_job_parameters with the 2023-09 schema."""

    template_dir: Path
    current_working_dir: Path

    @staticmethod
    @pytest.fixture(scope="class", autouse=True)
    def fake_template_dir_and_cwd():
        """Creates two temporary directories for the test to use as the template dir and cwd, respectively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            TestPreprocessJobParameters_2023_09.template_dir = Path(tmpdir) / "template_dir"
            TestPreprocessJobParameters_2023_09.current_working_dir = (
                Path(tmpdir) / "current_working_dir"
            )
            os.makedirs(TestPreprocessJobParameters_2023_09.template_dir)
            os.makedirs(TestPreprocessJobParameters_2023_09.current_working_dir)
            yield None

    @pytest.mark.parametrize(
        "param_type",
        [
            pytest.param(param_type.value, id=f"{param_type.value} type")
            for param_type in JobParameterType_2023_09
        ],
    )
    def test_preprocess_job_parameters_handles_parameter_type(self, param_type: str) -> None:
        # Test that we can process all known kinds of parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "12"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": param_type}],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert len(result) == 1
        assert "Foo" in result
        if param_type == "PATH":
            # "12" is a relative path that gets joined with the current working directory
            assert result["Foo"].value == str(self.current_working_dir / "12")
        else:
            assert result["Foo"].value == "12"
        assert result["Foo"].type == _parameter_value_type_from_str(param_type)

    @pytest.mark.parametrize(
        "param_type",
        [
            pytest.param(param_type.value, id=f"{param_type.value} type")
            for param_type in JobParameterType_2023_09
        ],
    )
    def test_handles_parameter_type_without_path_escape_validation(self, param_type: str) -> None:
        # Test that we can process all known kinds of parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "12"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": param_type}],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )

        # THEN
        assert len(result) == 1
        assert "Foo" in result
        # "12" remains the same relative path when used as a PATH parameter
        assert result["Foo"].value == "12"
        assert result["Foo"].type == _parameter_value_type_from_str(param_type)

    @pytest.mark.parametrize(
        "escaping_dir,expect_in_exc",
        [
            pytest.param(
                "..",
                "references a path outside of the template directory",
                id="relative dir up one level",
            ),
            pytest.param(
                "./..",
                "references a path outside of the template directory",
                id="relative dir up one level variation 1",
            ),
            pytest.param(
                "../.",
                "references a path outside of the template directory",
                id="relative dir one level variation 2",
            ),
            pytest.param(
                "down/down/../../down/../..",
                "references a path outside of the template directory",
                id="up and down, ending up escaped",
            ),
            pytest.param(
                os.getcwd(),
                "is an absolute path. Default paths must be relative, and are joined to the job template's directory.",
                id="current working directory, an abs path",
            ),
        ],
    )
    def test_path_parameter_default_cannot_escape(
        self, escaping_dir: str, expect_in_exc: str
    ) -> None:
        # Test that defaults provided for path parameters are not permitted to escape the job template directory

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert expect_in_exc in str(excinfo.value)

    def test_job_template_dir_must_be_absolute(self) -> None:
        # Test that the provided job template dir must be absolute (by default)

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": "defaultValue"}],
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=Path("relative/path"),
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "the job template dir" in str(excinfo.value)
        assert "is not an absolute path. It must be absolute to enforce that" in str(excinfo.value)
        # Regression for report rec #17: the user-supplied relative
        # path must appear verbatim in the diagnostic. Earlier
        # versions stripped it (the message read "..., , is not an
        # absolute path." with an empty placeholder).
        assert "relative/path" in str(excinfo.value)

    @pytest.mark.parametrize(
        "tdir,expected_in_message",
        [
            pytest.param(Path("."), ".", id="dot-path"),
            pytest.param(Path(""), ".", id="empty-path"),  # PathBuf normalises "" -> "."
            pytest.param(Path("rel/dir"), "rel/dir", id="relative-multi-segment"),
            pytest.param(Path("relative"), "relative", id="relative-single-segment"),
        ],
    )
    def test_preprocess_relative_path_error_includes_path(
        self, tdir: Path, expected_in_message: str
    ) -> None:
        """``preprocess_job_parameters`` rejects relative or sentinel
        ``job_template_dir`` values when ``allow_job_template_dir_walk_up``
        is False, and the diagnostic must name the user-supplied
        path so the caller can identify which value was wrong.
        Regression for report rec #17 — earlier versions emitted
        ``"the job template dir, ,"`` with an empty placeholder for
        ``Path(".")`` and ``Path("")`` because the binding rewrote
        them to ``""`` before validation."""
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": "defaultValue"}],
            )
        )
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values={},
                job_template_dir=tdir,
                current_working_dir=self.current_working_dir,
            )
        msg = str(excinfo.value)
        # The path appears verbatim in the diagnostic.
        assert (
            f"the job template dir, {expected_in_message}," in msg
        ), f"Expected path {expected_in_message!r} in {msg!r}"

    def test_preprocess_walk_up_true_accepts_dot_path(self) -> None:
        """With ``allow_job_template_dir_walk_up=True``, the
        ``"."`` / ``""`` sentinel paths are accepted (used by
        ``create_job`` itself when the caller hasn't supplied a
        real template directory). This is the inverse of
        ``test_preprocess_relative_path_error_includes_path``: the
        same path that's rejected with walk-up disabled is
        accepted with walk-up enabled."""
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "x"}],
            )
        )
        # No exception.
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values={},
            job_template_dir=Path("."),
            current_working_dir=Path("."),
            allow_job_template_dir_walk_up=True,
        )
        assert "Foo" in result

    @pytest.mark.parametrize(
        "escaping_dir",
        [
            pytest.param("..", id="relative dir up one level"),
            pytest.param("./..", id="relative dir up one level variation 1"),
            pytest.param("../.", id="relative dir one level variation 2"),
            pytest.param("down/down/../../down/../..", id="up and down, ending up escaped"),
            pytest.param(os.getcwd(), id="current working directory, an abs path"),
        ],
    )
    def test_path_parameter_default_escape_without_validation(self, escaping_dir: str) -> None:
        # Test that when path parameters are permitted to escape, the result is a normalized path join.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
            allow_job_template_dir_walk_up=True,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(
            type=ParameterValueType.PATH, value=os.path.normpath(self.template_dir / escaping_dir)
        )

    @pytest.mark.parametrize(
        "escaping_dir",
        [
            pytest.param("..", id="relative dir up one level"),
            pytest.param("./..", id="relative dir up one level variation 1"),
            pytest.param("../.", id="relative dir one level variation 2"),
            pytest.param("down/down/../../down/../..", id="up and down, ending up escaped"),
            pytest.param(os.getcwd(), id="current working directory, an abs path"),
        ],
    )
    def test_path_parameter_default_escape_without_validation_and_empty_paths(
        self, escaping_dir: str
    ) -> None:
        # Test that when path parameters are permitted to escape, and empty paths are provided
        # for the template dir and cwd, the result is to leave the input as-is.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
                parameterDefinitions=[{"name": "Foo", "type": "PATH", "default": escaping_dir}],
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=Path(),
            current_working_dir=Path(),
            allow_job_template_dir_walk_up=True,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.PATH, value=escaping_dir)

    def test_reports_extra(self) -> None:
        # Test that we get errors if we have extra job parameters defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"ThisIsUnknown": "value"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert (
            "Job parameter values provided for parameters that are not defined in the template: ThisIsUnknown"
            in str(excinfo.value)
        )

    def test_reports_extra_with_environments(self) -> None:
        # Test that we get errors if we have extra job parameters defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {
            "ThisIsUnknown": "value",
            "ThisIsKnown": "value",
        }
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[{"name": "ThisIsKnown", "type": "STRING"}],
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
                environment_templates=[env_template],
            )

        # THEN
        assert (
            "Job parameter values provided for parameters that are not defined in the template: ThisIsUnknown"
            in str(excinfo.value)
        )

    def test_reports_missing(self) -> None:
        # Test that we get errors if we have missed defining job parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = dict()
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "ThisIsNotDefined", "type": "STRING"}],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert "Values missing for required job parameters: ThisIsNotDefined" in str(excinfo.value)

    def test_reports_missing_with_environments(self) -> None:
        # Test that we get errors if we have missed defining job parameters

        # GIVEN
        job_parameter_values: JobParameterInputValues = dict()
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "ThisIsNotDefined", "type": "STRING"}],
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[{"name": "ThisIsAlsoMissing", "type": "STRING"}],
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
                environment_templates=[env_template],
            )

        # THEN
        assert (
            "Values missing for required job parameters: ThisIsAlsoMissing, ThisIsNotDefined"
            in str(excinfo.value)
        )

    def test_collects_defaults(self) -> None:
        # Test that we add values for missing job parameters that have
        # defaults defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[
                    {"name": "Foo", "type": "STRING", "default": "defaultValue"},
                    {"name": "Bar", "type": "PATH", "default": "defaultPathValue"},
                ],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="defaultValue")
        assert "Bar" in result
        assert result["Bar"] == ParameterValue(
            type=ParameterValueType.PATH, value=str(self.template_dir / "defaultPathValue")
        )

    def test_empty_path_parameter_passthrough(self) -> None:
        # Test that empty values for PATH parameter defaults or passed parameters are
        # passed through instead of being treated as the directory "."

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Bar": ""}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[
                    {"name": "Foo", "type": "PATH", "default": ""},
                    {"name": "Bar", "type": "PATH", "default": "defaultPathValue"},
                ],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.PATH, value="")
        assert "Bar" in result
        assert result["Bar"] == ParameterValue(type=ParameterValueType.PATH, value="")

    def test_collects_defaults_with_environments(self) -> None:
        # Test that we add values for missing job parameters that have
        # defaults defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "defaultValue"}],
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[
                    {"name": "Bar", "type": "STRING", "default": "alsoDefaultValue"}
                ],
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
            environment_templates=[env_template],
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="defaultValue")
        assert "Bar" in result
        assert result["Bar"] == ParameterValue(
            type=ParameterValueType.STRING, value="alsoDefaultValue"
        )

    def test_ignores_defaults(self) -> None:
        # Test that we do not add values for job parameters that have
        # defaults defined, but that we've already defined.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "FooValue"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "default": "defaultValue"}],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        result = preprocess_job_parameters(
            job_template=job_template,
            job_parameter_values=job_parameter_values,
            job_template_dir=self.template_dir,
            current_working_dir=self.current_working_dir,
        )

        # THEN
        assert "Foo" in result
        assert result["Foo"] == ParameterValue(type=ParameterValueType.STRING, value="FooValue")

    def test_checks_contraints(self) -> None:
        # Test that we see errors if a constraint is violated.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "two"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "maxLength": 1}],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN
        assert str(excinfo.value) == "Parameter 'Foo': value length 3 exceeds maximum 1"

    def test_checks_contraints_with_environments(self) -> None:
        # Test that we see errors if a constraint is violated.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {"Foo": "two", "Bar": "one"}
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[{"name": "Foo", "type": "STRING", "maxLength": 1}],
                steps=minimal_steps_v2023_09,
            )
        )
        env_template = decode_environment_template(
            template=dict(
                specificationVersion="environment-2023-09",
                environment=minimal_environment_2023_09,
                parameterDefinitions=[{"name": "Bar", "type": "STRING", "minLength": 5}],
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
                environment_templates=[env_template],
            )

        # THEN — all errors collected (env template params processed first)
        assert str(excinfo.value) == "\n".join(
            [
                "Parameter 'Bar': value length 3 is less than minimum 5",
                "Parameter 'Foo': value length 3 exceeds maximum 1",
            ]
        )

    def test_collects_multiple_errors(self) -> None:
        # Test that see all errors if we have multiple in the same run.

        # GIVEN
        job_parameter_values: JobParameterInputValues = {
            "Foo": "two",  # Too long of a value
            "Bar": "three",  # An extra parameter
            # missing buz
        }
        job_template = decode_job_template(
            template=dict(
                specificationVersion="jobtemplate-2023-09",
                name="test",
                parameterDefinitions=[
                    {"name": "Foo", "type": "STRING", "maxLength": 1},
                    {"name": "Buz", "type": "STRING"},
                ],
                steps=minimal_steps_v2023_09,
            )
        )

        # WHEN
        with pytest.raises(ValueError) as excinfo:
            preprocess_job_parameters(
                job_template=job_template,
                job_parameter_values=job_parameter_values,
                job_template_dir=self.template_dir,
                current_working_dir=self.current_working_dir,
            )

        # THEN — all errors collected
        assert str(excinfo.value) == "\n".join(
            [
                "Parameter 'Foo': value length 3 exceeds maximum 1",
                "Job parameter values provided for parameters that are not defined in the template: Bar",
                "Values missing for required job parameters: Buz",
            ]
        )


class TestCreateJob_2023_09:
    def test_success(self) -> None:
        # GIVEN
        job_template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT", "minValue": 10}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.INT, value="20")}

        # WHEN
        result = create_job(job_template=job_template, job_parameter_values=parameter_values)

        # THEN
        assert result.name == "Job"
        assert len(result.steps) == 1
        assert result.steps[0].name == "Step"
        assert "Foo" in result.parameters
        assert result.parameters["Foo"].value.item() == 20

    def test_with_preprocess_error_from_job_template(self) -> None:
        # GIVEN
        job_template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT", "minValue": 10}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.INT, value="5")}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(job_template=job_template, job_parameter_values=parameter_values)

        # THEN
        assert str(excinfo.value) == "Parameter 'Foo': value 5 is less than minimum 10"

    def test_with_preprocess_error_from_environment_template(self) -> None:
        # GIVEN
        job_template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "parameterDefinitions": [{"name": "Foo", "type": "INT"}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        env_template = decode_environment_template(
            template={
                "specificationVersion": "environment-2023-09",
                "parameterDefinitions": [{"name": "Foo", "type": "INT", "minValue": 10}],
                "environment": {
                    "name": "Env",
                    "script": {"actions": {"onEnter": {"command": "do something"}}},
                },
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.INT, value="5")}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
                environment_templates=[env_template],
            )

        # THEN
        assert str(excinfo.value) == "Parameter 'Foo': value 5 is less than minimum 10"

    def test_fails_to_instantiate(self) -> None:
        # GIVEN
        job_template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "{{Param.Foo}}",
                "parameterDefinitions": [{"name": "Foo", "type": "STRING"}],
                "steps": [
                    {"name": "Step", "script": {"actions": {"onRun": {"command": "do something"}}}}
                ],
            },
        )
        parameter_values = {"Foo": ParameterValue(type=ParameterValueType.STRING, value="a" * 256)}

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            # This'll have an error when instantiating the Job due to the Job's name being too long.
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
            )

        # THEN
        assert str(excinfo.value) == "Job name exceeds maximum length of 128 characters (got 256)"

    def test_uneven_parameter_space_association(self) -> None:
        # Test that when the arguments to an Association operator in a
        # parameter space combination expression have differing lengths then
        # we raise an appropriate exception.
        #
        # Note: This validation is run in the create job flow because we need
        # to have a fully instantiated the step parameter space's task parameter
        # definitions to know how large each parameter range is.

        # GIVEN
        job_template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Job",
                "steps": [
                    {
                        "name": "Step",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "A", "type": "INT", "range": "1-10"},
                                {"name": "B", "type": "INT", "range": [1, 2]},
                            ],
                            "combination": "(A,B)",
                        },
                        "script": {"actions": {"onRun": {"command": "do something"}}},
                    }
                ],
            },
        )
        parameter_values = dict[str, Any]()

        # WHEN
        with pytest.raises(DecodeValidationError) as excinfo:
            # This'll have an error when instantiating the Job due to the Job's name being too long.
            create_job(
                job_template=job_template,
                job_parameter_values=parameter_values,
            )

        # THEN
        assert (
            str(excinfo.value)
            == "Associative combination: all members must have the same number of values, got 10 and 2"
        )


class TestParametersDict:
    """``Job.parameters`` is the resolved parameter set: every parameter
    defined in the template (defaults plus explicit values) keyed by
    name, with each ``JobParameter.value`` resolved to the chosen
    ``ExprValue``. This matches the v0 reference's behaviour and is
    relied on by every downstream consumer that walks the resolved set
    (sessions, the worker agent, deadline-cli)."""

    @staticmethod
    def _two_param_template() -> dict[str, Any]:
        return {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Frame", "type": "INT", "default": 5},
                {"name": "Name", "type": "STRING", "default": "render"},
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": [
                                    "{{Param.Name}}",
                                    "{{Param.Frame}}",
                                ],
                            }
                        }
                    },
                }
            ],
        }

    def test_defaults_only_populated(self) -> None:
        """No values supplied — all defaults appear in
        ``Job.parameters``."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(job_template=t, job_parameter_values={})
        assert set(j.parameters.keys()) == {"Frame", "Name"}
        assert j.parameters["Frame"].param_type == "INT"
        assert j.parameters["Frame"].value.item() == 5
        assert j.parameters["Name"].param_type == "STRING"
        assert j.parameters["Name"].value.item() == "render"

    def test_explicit_values_override_defaults(self) -> None:
        """Explicit values override defaults; un-supplied parameters
        still show up via their defaults."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={"Frame": ParameterValue(type=JobParameterType.INT, value="7")},
        )
        assert set(j.parameters.keys()) == {"Frame", "Name"}
        assert j.parameters["Frame"].value.item() == 7
        assert j.parameters["Name"].value.item() == "render"

    def test_bare_scalar_input(self) -> None:
        """Bare-scalar input (``{"Frame": 7}``) is accepted and the
        un-supplied parameter falls back to its default."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={"Frame": 7},
        )
        assert j.parameters["Frame"].value.item() == 7
        assert j.parameters["Name"].value.item() == "render"

    def test_dict_shaped_input(self) -> None:
        """Dict-shaped input (``{"type": ..., "value": ...}``) is
        accepted; defaults still fill in the missing names."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={"Name": {"type": "STRING", "value": "foo"}},
        )
        assert j.parameters["Name"].value.item() == "foo"
        assert j.parameters["Frame"].value.item() == 5

    def test_all_explicit_no_defaults_used(self) -> None:
        """When every parameter is supplied explicitly, no default is
        consulted; ``Job.parameters`` reflects the supplied values."""
        t = decode_job_template(template=self._two_param_template())
        j = create_job(
            job_template=t,
            job_parameter_values={
                "Frame": ParameterValue(type=JobParameterType.INT, value="42"),
                "Name": ParameterValue(type=JobParameterType.STRING, value="bar"),
            },
        )
        assert j.parameters["Frame"].value.item() == 42
        assert j.parameters["Name"].value.item() == "bar"

    def test_required_param_no_default_no_value_raises(self) -> None:
        """A parameter with no default and no supplied value triggers
        the standard 'Values missing for required job parameters' error
        (this lives in ``preprocess_job_parameters``, which
        ``create_job`` now routes through internally)."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Required", "type": "INT"},  # no default
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{Param.Required}}"],
                            }
                        }
                    },
                }
            ],
        }
        t = decode_job_template(template=template)
        with pytest.raises(DecodeValidationError, match="missing"):
            create_job(job_template=t, job_parameter_values={})

    def test_constraint_check_runs_via_create_job(self) -> None:
        """Constraint checks (e.g. ``minValue``) run during
        ``create_job`` itself — callers don't need to call
        ``preprocess_job_parameters`` first."""
        template = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "parameterDefinitions": [
                {"name": "Frame", "type": "INT", "default": 5, "minValue": 1},
            ],
            "steps": [
                {
                    "name": "S",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "args": ["{{Param.Frame}}"],
                            }
                        }
                    },
                }
            ],
        }
        t = decode_job_template(template=template)
        # Below-min value rejected.
        with pytest.raises(DecodeValidationError):
            create_job(
                job_template=t,
                job_parameter_values={
                    "Frame": ParameterValue(type=JobParameterType.INT, value="0")
                },
            )
        # Default (5) passes constraints — Job.parameters gets the
        # default.
        j = create_job(job_template=t, job_parameter_values={})
        assert j.parameters["Frame"].value.item() == 5
