# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for escape_format_string."""

import pytest

from openjd.model import create_job, decode_job_template, escape_format_string


class TestEscapeFormatString:
    """Tests for the escape_format_string utility function."""

    @pytest.mark.parametrize(
        "value",
        [
            "hello world",
            "no braces here",
            "single { brace",
            "single } brace",
            "",
        ],
        ids=["plain", "no-braces", "single-open", "single-close", "empty"],
    )
    def test_passthrough(self, value: str) -> None:
        """Strings without {{ or }} are returned unchanged."""
        assert escape_format_string(value) == value

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("has {{ open", 'has {{ "{{" }} open'),
            ("has }} close", 'has {{ "}" + "}" }} close'),
            ("both {{ and }}", 'both {{ "{{" }} and {{ "}" + "}" }}'),
            ("{{}}", '{{ "{{" }}{{ "}" + "}" }}'),
            ("{{{{", '{{ "{{" }}{{ "{{" }}'),
            ("a}}b}}c", 'a{{ "}" + "}" }}b{{ "}" + "}" }}c'),
        ],
        ids=["open", "close", "both", "adjacent", "double-open", "multiple-close"],
    )
    def test_escaping(self, value: str, expected: str) -> None:
        """Delimiter sequences are escaped correctly."""
        assert escape_format_string(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "simple name",
            "has {{ braces }}",
            "{{start",
            "end}}",
            "mid{{}}dle",
            "job-with-{{ expr }}-in-name",
        ],
        ids=["simple", "braces", "start", "end", "middle", "expr-like"],
    )
    def test_roundtrip(self, value: str) -> None:
        """Escaped value resolves back to the original when used in a template name."""
        escaped = escape_format_string(value)
        t = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "extensions": ["EXPR"],
                "name": escaped,
                "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            },
            supported_extensions=["EXPR"],
        )
        j = create_job(job_template=t, job_parameter_values={})
        assert j.name == value
