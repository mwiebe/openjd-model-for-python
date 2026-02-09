# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""End-to-end tests that validate template files in test/openjd/data/templates/.

Each YAML file in the templates directory is automatically discovered and tested.
Templates can specify expected behavior via special comments or naming conventions.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from openjd.model import (
    create_job,
    decode_job_template,
    decode_environment_template,
)


TEMPLATES_DIR = Path(__file__).parent / "data" / "templates"


def get_template_files() -> list[Path]:
    """Discover all template files in the templates directory."""
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(TEMPLATES_DIR.glob("*.yaml")) + sorted(TEMPLATES_DIR.glob("*.yml"))


def get_extensions_from_template(template: dict[str, Any]) -> list[str]:
    """Extract extensions from a template dict."""
    return template.get("extensions", [])


class TestTemplateFiles:
    """End-to-end tests for template files."""

    @pytest.mark.parametrize(
        "template_path",
        get_template_files(),
        ids=[p.stem for p in get_template_files()],
    )
    def test_template_parses_successfully(self, template_path: Path) -> None:
        """Test that each template file parses, validates, and creates a job successfully."""
        with open(template_path) as f:
            template_dict = yaml.safe_load(f)

        spec_version = template_dict.get("specificationVersion", "")
        extensions = get_extensions_from_template(template_dict)

        if "jobtemplate" in spec_version:
            job_template = decode_job_template(
                template=template_dict, supported_extensions=extensions
            )
            # Also test create_job with default parameter values
            create_job(job_template=job_template, job_parameter_values={})
        elif "environment" in spec_version:
            decode_environment_template(template=template_dict, supported_extensions=extensions)
        else:
            pytest.fail(f"Unknown specificationVersion: {spec_version}")
