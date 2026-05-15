# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.model.v1 import TemplateSpecificationVersion


class TestTemplateSpecificationVersion:
    def test_all_values_classified(self) -> None:
        # Every enum value is in exactly one of the version getter staticmethods.
        # GIVEN
        all_versions = set(v for v in TemplateSpecificationVersion)
        job_template_versions = set(v for v in TemplateSpecificationVersion.job_template_versions())
        env_template_versions = set(
            v for v in TemplateSpecificationVersion.environment_template_versions()
        )

        # THEN
        assert len(job_template_versions.intersection(env_template_versions)) == 0
        assert (job_template_versions | env_template_versions) == all_versions

    @pytest.mark.parametrize("version", TemplateSpecificationVersion.job_template_versions())
    def test_job_template_versions(self, version: TemplateSpecificationVersion) -> None:
        # Test that is_job_template() correctly identifies all versions that are job template versions.
        # THEN
        assert TemplateSpecificationVersion.is_job_template(version)

    @pytest.mark.parametrize(
        "version",
        sorted(
            list(
                set(v for v in TemplateSpecificationVersion)
                - set(TemplateSpecificationVersion.job_template_versions())
            )
        ),
    )
    def test_not_job_template_versions(self, version: TemplateSpecificationVersion) -> None:
        # Test that is_job_template() correctly identifies all versions that are job template versions.
        # THEN
        assert not TemplateSpecificationVersion.is_job_template(version)

    @pytest.mark.parametrize(
        "version", TemplateSpecificationVersion.environment_template_versions()
    )
    def test_environment_template_versions(self, version: TemplateSpecificationVersion) -> None:
        # Test that is_environment_template() correctly identifies all versions that are environment template versions.
        # THEN
        assert TemplateSpecificationVersion.is_environment_template(version)

    @pytest.mark.parametrize(
        "version",
        sorted(
            list(
                set(v for v in TemplateSpecificationVersion)
                - set(TemplateSpecificationVersion.environment_template_versions())
            )
        ),
    )
    def test_not_environment_template_versions(self, version: TemplateSpecificationVersion) -> None:
        # Test that is_environment_template() correctly identifies all versions that are environment template versions.
        # THEN
        assert not TemplateSpecificationVersion.is_environment_template(version)
