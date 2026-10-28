// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! ENV_PARAMS (RFC 0010, draft) job-side types and the job-creation entry
//! points that take attached Environment Templates.
//!
//! Wraps `openjd_model::job::{Document, EnvironmentRef,
//! EnvironmentParameterValues}`, `openjd_model::{CreatedJob,
//! StepDisabledEnvironments, create_job_with_environment_templates,
//! check_environment_templates}`.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple, PyType};
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_model::job::{Document, EnvironmentParameterValues, EnvironmentRef};
use openjd_model::template::EnvironmentTemplate;
use openjd_model::{AttachedEnvironmentTemplate, PathParameterOptions};

use super::create_job_fns::extract_input_values;
use super::errors::model_err_to_py;
use super::job::PyJob;
use super::profile::PyValidationContext;
use super::template::{PyEnvironmentTemplate, PyJobTemplate};
use crate::expr::PySerializedSymbolTable;

// ── Document ──

/// The document of a Job Environment: the Job Template, or the
/// Environment Template attached at ``index`` (with an optional ``label``
/// that names it in messages).
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "Document",
    frozen,
    eq,
    hash,
    from_py_object
)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub(crate) struct PyDocument {
    pub(crate) inner: Document,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyDocument {
    /// The Job Template.
    #[staticmethod]
    fn job_template() -> Self {
        Self {
            inner: Document::JobTemplate,
        }
    }

    /// The Environment Template attached at ``index``.
    #[staticmethod]
    #[pyo3(signature = (index, label=None))]
    fn environment_template(index: usize, label: Option<&str>) -> Self {
        Self {
            inner: Document::environment_template(index, label),
        }
    }

    #[getter]
    fn is_job_template(&self) -> bool {
        self.inner.is_job_template()
    }

    /// The attachment index, or ``None`` for the Job Template.
    #[getter]
    fn index(&self) -> Option<usize> {
        match &self.inner {
            Document::EnvironmentTemplate { index, .. } => Some(*index),
            _ => None,
        }
    }

    /// The attachment label, or ``None``.
    #[getter]
    fn label(&self) -> Option<&str> {
        match &self.inner {
            Document::EnvironmentTemplate { label, .. } => label.as_deref(),
            _ => None,
        }
    }

    fn __str__(&self) -> String {
        self.inner.to_string()
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            Document::EnvironmentTemplate { index, label } => match label {
                Some(l) => format!("Document.environment_template({index}, {l:?})"),
                None => format!("Document.environment_template({index})"),
            },
            _ => "Document.job_template()".to_string(),
        }
    }
}

// ── EnvironmentRef ──

/// A Job Environment named by its document and name.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "EnvironmentRef",
    frozen,
    eq,
    hash,
    from_py_object
)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub(crate) struct PyEnvironmentRef {
    pub(crate) inner: EnvironmentRef,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentRef {
    #[new]
    #[pyo3(signature = (*, document, environment))]
    fn new(document: &PyDocument, environment: String) -> Self {
        Self {
            inner: EnvironmentRef {
                document: document.inner.clone(),
                environment,
            },
        }
    }

    #[getter]
    fn document(&self) -> PyDocument {
        PyDocument {
            inner: self.inner.document.clone(),
        }
    }

    #[getter]
    fn environment(&self) -> &str {
        &self.inner.environment
    }

    fn __repr__(&self) -> String {
        format!(
            "EnvironmentRef(document={}, environment={:?})",
            PyDocument {
                inner: self.inner.document.clone()
            }
            .__repr__(),
            self.inner.environment
        )
    }
}

// ── EnvironmentParameterValues ──

/// The effective ENV_PARAMS values one Step supplies to one Environment.
///
/// ``values`` holds one entry per parameter, keyed by the bare parameter
/// name and typed with the parameter's own expression type (``path``,
/// ``list[path]``, ``int``, ...). PATH values are not path-mapped; a
/// RANGE_EXPR value is in canonical form. Pass it to
/// ``Session.enter_environment(parameters=...)``.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "EnvironmentParameterValues",
    frozen,
    eq,
    from_py_object
)]
#[derive(Clone, PartialEq)]
pub(crate) struct PyEnvironmentParameterValues {
    pub(crate) inner: EnvironmentParameterValues,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentParameterValues {
    /// ``document`` defaults to the Job Template.
    #[new]
    #[pyo3(signature = (*, environment, values, document=None))]
    fn new(
        environment: String,
        values: &PySerializedSymbolTable,
        document: Option<&PyDocument>,
    ) -> Self {
        Self {
            inner: EnvironmentParameterValues {
                document: document.map(|d| d.inner.clone()).unwrap_or_default(),
                environment,
                values: values.inner.clone(),
            },
        }
    }

    #[getter]
    fn document(&self) -> PyDocument {
        PyDocument {
            inner: self.inner.document.clone(),
        }
    }

    #[getter]
    fn environment(&self) -> &str {
        &self.inner.environment
    }

    #[getter]
    fn values(&self) -> PySerializedSymbolTable {
        PySerializedSymbolTable {
            inner: self.inner.values.clone(),
        }
    }

    /// Template Schemas §3.2.2 equality of the values (FLOAT by value,
    /// RANGE_EXPR by the integers it denotes). Document and Environment
    /// name are not compared.
    fn values_equal(&self, other: &PyEnvironmentParameterValues) -> bool {
        self.inner.values_equal(&other.inner)
    }

    /// The JSON transport form, ``{"document": {...}, "environment": ...,
    /// "values": [...]}``.
    fn to_json_str(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to serialize EnvironmentParameterValues: {e}"
            ))
        })
    }

    /// Inverse of ``to_json_str``. Raises ``ValueError`` on malformed text.
    #[classmethod]
    fn from_json_str(_cls: &Bound<'_, PyType>, json: &str) -> PyResult<Self> {
        serde_json::from_str(json)
            .map(|inner| Self { inner })
            .map_err(|e| {
                pyo3::exceptions::PyValueError::new_err(format!(
                    "Failed to parse EnvironmentParameterValues JSON: {e}"
                ))
            })
    }

    fn __repr__(&self) -> String {
        format!(
            "EnvironmentParameterValues(environment={:?}, document={})",
            self.inner.environment, self.inner.document
        )
    }

    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyAny>, Py<PyTuple>)> {
        let json = self.to_json_str()?;
        let from_json = py.get_type::<Self>().getattr("from_json_str")?;
        let args = PyTuple::new(py, [json])?;
        Ok((from_json, args.unbind()))
    }
}

// ── StepDisabledEnvironments ──

/// The Environments an ``enableIf`` on the Environment disabled for one
/// Step, for display.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepDisabledEnvironments",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyStepDisabledEnvironments {
    pub(crate) inner: openjd_model::StepDisabledEnvironments,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepDisabledEnvironments {
    /// Combined Job Environments, attached first, by (document, name).
    #[getter]
    fn environments(&self) -> Vec<PyEnvironmentRef> {
        self.inner
            .environments
            .iter()
            .map(|e| PyEnvironmentRef { inner: e.clone() })
            .collect()
    }

    /// The Step's own ``stepEnvironments``, by name.
    #[getter]
    fn step_environments(&self) -> Vec<String> {
        self.inner.step_environments.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "StepDisabledEnvironments(environments={}, step_environments={:?})",
            self.inner.environments.len(),
            self.inner.step_environments
        )
    }
}

// ── CreatedJob ──

/// The result of ``create_job_with_environment_templates``.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "CreatedJob",
    frozen,
    from_py_object
)]
#[derive(Clone)]
pub(crate) struct PyCreatedJob {
    pub(crate) inner: openjd_model::CreatedJob,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyCreatedJob {
    /// The combined Job: attached Environments first, in attachment
    /// order, then the Job Template's ``jobEnvironments``.
    #[getter]
    fn job(&self) -> PyJob {
        PyJob {
            inner: self.inner.job.clone(),
        }
    }

    /// The document of each ``job.job_environments`` entry, index for
    /// index.
    #[getter]
    fn environment_documents(&self) -> Vec<PyDocument> {
        self.inner
            .environment_documents
            .iter()
            .map(|d| PyDocument { inner: d.clone() })
            .collect()
    }

    /// Submission warnings, each ``"<path>: <message>"``.
    #[getter]
    fn warnings(&self) -> Vec<String> {
        self.inner.warnings.iter().map(|w| w.to_string()).collect()
    }

    /// Per Step of ``job``, index for index.
    #[getter]
    fn disabled_environments(&self) -> Vec<PyStepDisabledEnvironments> {
        self.inner
            .disabled_environments
            .iter()
            .map(|d| PyStepDisabledEnvironments { inner: d.clone() })
            .collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "CreatedJob(job={:?}, environments={})",
            self.inner.job.name,
            self.inner.environment_documents.len()
        )
    }
}

// ── Attachments ──

/// ``environment_templates`` items: an ``EnvironmentTemplate`` or an
/// ``(EnvironmentTemplate, label)`` pair.
fn extract_attachments(
    environment_templates: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(EnvironmentTemplate, Option<String>)>> {
    let Some(seq) = environment_templates else {
        return Ok(Vec::new());
    };
    let mut out = Vec::new();
    for item in seq.try_iter()? {
        let item = item?;
        if let Ok(t) = item.extract::<PyEnvironmentTemplate>() {
            out.push((t.inner, None));
        } else if let Ok((t, label)) = item.extract::<(PyEnvironmentTemplate, Option<String>)>() {
            out.push((t.inner, label));
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "environment_templates items must be EnvironmentTemplate or \
                 (EnvironmentTemplate, label) tuples",
            ));
        }
    }
    Ok(out)
}

fn attached_refs(
    owned: &[(EnvironmentTemplate, Option<String>)],
) -> Vec<AttachedEnvironmentTemplate<'_>> {
    owned
        .iter()
        .map(|(t, label)| {
            let a = AttachedEnvironmentTemplate::new(t);
            match label {
                Some(l) => a.with_label(l),
                None => a,
            }
        })
        .collect()
}

/// Create a Job with the Environment Templates attached to the submission
/// (ENV_PARAMS, Template Schemas §3.2.1–§3.2.2, §7.4).
///
/// ``environment_templates`` items are ``EnvironmentTemplate`` or
/// ``(EnvironmentTemplate, label)``; attachment order is the order Sessions
/// enter them, before the Job Template's ``jobEnvironments``. Job
/// Parameter values go through ``preprocess_job_parameters`` against the
/// merged definitions first, as for ``create_job``. Each Step of the
/// result carries ``environments`` and ``environment_parameters``.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "create_job_with_environment_templates")]
#[pyo3(signature = (*, job_template, job_parameter_values, environment_templates=None, validation_context=None))]
pub(crate) fn py_create_job_with_environment_templates(
    job_template: &PyJobTemplate,
    job_parameter_values: &Bound<'_, PyDict>,
    environment_templates: Option<&Bound<'_, PyAny>>,
    validation_context: Option<&PyValidationContext>,
) -> PyResult<PyCreatedJob> {
    let owned = extract_attachments(environment_templates)?;
    let env_templates: Vec<EnvironmentTemplate> = owned.iter().map(|(t, _)| t.clone()).collect();
    let input_values = extract_input_values(job_parameter_values)?;
    // Same sentinel path options as ``create_job``: no template dir or CWD
    // is known here.
    let path_opts = PathParameterOptions {
        job_template_dir: "",
        current_working_dir: "",
        path_format: openjd_expr::path_mapping::PathFormat::host(),
        allow_template_dir_walk_up: true,
        allow_uri_path_values: false,
    };
    let params = openjd_model::preprocess_job_parameters(
        &job_template.inner,
        &input_values,
        &env_templates,
        &path_opts,
    )
    .map_err(model_err_to_py)?;
    let ctx = match validation_context {
        Some(vc) => vc.inner.clone(),
        None => job_template.inner.default_validation_context(),
    };
    let attached = attached_refs(&owned);
    let created = openjd_model::create_job_with_environment_templates(
        &job_template.inner,
        &attached,
        &params,
        &ctx,
    )
    .map_err(model_err_to_py)?;
    Ok(PyCreatedJob { inner: created })
}

/// The submission-stage checks of ``create_job_with_environment_templates``
/// that need no Job Parameter values. Returns the warnings, each
/// ``"<path>: <message>"``; raises ``ModelValidationError`` on an error.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyfunction(module = "openjd._openjd_rs")
)]
#[pyfunction(name = "check_environment_templates")]
#[pyo3(signature = (*, job_template, environment_templates, validation_context=None))]
pub(crate) fn py_check_environment_templates(
    job_template: &PyJobTemplate,
    environment_templates: &Bound<'_, PyAny>,
    validation_context: Option<&PyValidationContext>,
) -> PyResult<Vec<String>> {
    let owned = extract_attachments(Some(environment_templates))?;
    let ctx = match validation_context {
        Some(vc) => vc.inner.clone(),
        None => job_template.inner.default_validation_context(),
    };
    let attached = attached_refs(&owned);
    let warnings = openjd_model::check_environment_templates(&job_template.inner, &attached, &ctx)
        .map_err(model_err_to_py)?;
    Ok(warnings.iter().map(|w| w.to_string()).collect())
}
