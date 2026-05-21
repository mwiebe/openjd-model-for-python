// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::template::{JobTemplate, EnvironmentTemplate};
use openjd_model::TemplateSpecificationVersion;

use super::profile::PyModelProfile;
use super::types::PyTemplateSpecificationVersion;
use super::template_types::{PyEnvironment as PyTemplateEnvironment, PyStepTemplate};

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.template", name = "JobTemplate", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyJobTemplate {
    pub(crate) inner: JobTemplate,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyJobTemplate {
    #[getter]
    fn name(&self) -> String {
        self.inner.name.raw().to_string()
    }

    #[getter]
    fn specification_version(&self) -> PyTemplateSpecificationVersion {
        // Parse the string back to enum; safe because decode validated it
        self.inner.specification_version.parse::<TemplateSpecificationVersion>()
            .map(PyTemplateSpecificationVersion::from)
            .unwrap_or(PyTemplateSpecificationVersion::JOBTEMPLATE_2023_09)
    }

    /// camelCase alias for `specification_version`. Mirrors the
    /// `specificationVersion` field name in the JSON/YAML template.
    #[getter(specificationVersion)]
    fn specification_version_camel(&self) -> PyTemplateSpecificationVersion {
        self.specification_version()
    }

    #[getter]
    fn description(&self) -> Option<String> {
        self.inner.description.as_ref().map(|d| d.0.clone())
    }

    /// The [`ModelProfile`](crate::model::profile::PyModelProfile)
    /// described by this template: the revision from
    /// `specificationVersion` and the extensions set declared on
    /// the template's `extensions:` field.
    ///
    /// Mirrors `JobTemplate::profile()` in the underlying Rust crate.
    #[getter]
    fn profile(&self) -> PyModelProfile {
        PyModelProfile { inner: self.inner.profile() }
    }

    /// The list of `StepTemplate`s defined on this job template.
    /// Mirrors the `steps:` field in the YAML/JSON document.
    #[getter]
    fn steps(&self) -> Vec<PyStepTemplate> {
        self.inner
            .steps
            .iter()
            .map(|s| PyStepTemplate { inner: s.clone() })
            .collect()
    }

    /// The list of job-level `Environment` definitions, or ``None``
    /// if the template has no `jobEnvironments:` field. Mirrors the
    /// `jobEnvironments:` field in the YAML/JSON document.
    #[getter]
    fn job_environments(&self) -> Option<Vec<PyTemplateEnvironment>> {
        self.inner
            .job_environments
            .as_ref()
            .map(|envs| envs.iter().map(|e| PyTemplateEnvironment { inner: e.clone() }).collect())
    }

    /// camelCase alias for `job_environments`.
    #[getter]
    #[pyo3(name = "jobEnvironments")]
    fn job_environments_camel(&self) -> Option<Vec<PyTemplateEnvironment>> {
        self.job_environments()
    }

    fn __repr__(&self) -> String {
        format!("JobTemplate(name={:?}, version={:?})", self.inner.name.raw(), self.inner.specification_version)
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model._v1.template", name = "EnvironmentTemplate", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyEnvironmentTemplate {
    pub(crate) inner: EnvironmentTemplate,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentTemplate {
    #[getter]
    fn name(&self) -> String {
        self.inner.environment.name.clone()
    }

    #[getter]
    fn specification_version(&self) -> PyTemplateSpecificationVersion {
        self.inner.specification_version.parse::<TemplateSpecificationVersion>()
            .map(PyTemplateSpecificationVersion::from)
            .unwrap_or(PyTemplateSpecificationVersion::ENVIRONMENT_2023_09)
    }

    /// camelCase alias for `specification_version`. Mirrors the
    /// `specificationVersion` field name in the JSON/YAML template.
    #[getter(specificationVersion)]
    fn specification_version_camel(&self) -> PyTemplateSpecificationVersion {
        self.specification_version()
    }

    #[getter]
    fn description(&self) -> Option<String> {
        self.inner.environment.description.as_ref().map(|d| d.0.clone())
    }

    /// The `Environment` defined by this template — mirrors the
    /// `environment:` field in the YAML/JSON document.
    #[getter]
    fn environment(&self) -> PyTemplateEnvironment {
        PyTemplateEnvironment { inner: self.inner.environment.clone() }
    }

    fn __repr__(&self) -> String {
        format!("EnvironmentTemplate(name={:?}, version={:?})", self.inner.environment.name, self.inner.specification_version)
    }
}
