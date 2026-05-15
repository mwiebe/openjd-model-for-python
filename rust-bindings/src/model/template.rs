// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::{JobTemplate, EnvironmentTemplate};
use openjd_model::TemplateSpecificationVersion;

use super::types::PyTemplateSpecificationVersion;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model.v1", name = "JobTemplate", from_py_object)]
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

    #[getter]
    fn description(&self) -> Option<String> {
        self.inner.description.as_ref().map(|d| d.0.clone())
    }

    fn __repr__(&self) -> String {
        format!("JobTemplate(name={:?}, version={:?})", self.inner.name.raw(), self.inner.specification_version)
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model.v1", name = "EnvironmentTemplate", from_py_object)]
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

    #[getter]
    fn description(&self) -> Option<String> {
        self.inner.environment.description.as_ref().map(|d| d.0.clone())
    }

    fn __repr__(&self) -> String {
        format!("EnvironmentTemplate(name={:?}, version={:?})", self.inner.environment.name, self.inner.specification_version)
    }
}
