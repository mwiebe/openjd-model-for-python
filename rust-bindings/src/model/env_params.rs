// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! ENV_PARAMS (RFC 0010, draft) job-side types and the job-creation entry
//! points that take attached Environment Templates.
//!
//! Wraps `openjd_model::job::{Document, EnvironmentRef,
//! EnvironmentParameterValues}`, `openjd_model::{CreatedJob,
//! StepDisabledEnvironments, StepEnvironmentStatuses, StepEnvironmentStatus,
//! SupersedingEnvironment, EnvironmentStatus, EnvironmentScope, OptionalEntryNotFound,
//! create_job_with_environment_templates, check_environment_templates}`.

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

    /// Pickle support — round-trips through the static constructors.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyAny>, Py<PyTuple>)> {
        let cls = py.get_type::<Self>();
        match &self.inner {
            Document::EnvironmentTemplate { index, label } => {
                let args = (*index, label.clone()).into_pyobject(py)?;
                Ok((cls.getattr("environment_template")?, args.unbind()))
            }
            _ => Ok((cls.getattr("job_template")?, PyTuple::empty(py).unbind())),
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

    /// Pickle support — round-trips through ``__init__``.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyAny>, Py<PyTuple>)> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_kwargs")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("document", self.document())?;
        kwargs.set_item("environment", &self.inner.environment)?;
        let args = PyTuple::new(py, [py.get_type::<Self>().into_any(), kwargs.into_any()])?;
        Ok((helper, args.unbind()))
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

/// The Environments disabled for one Step, for display: those their own
/// ``enableIf`` disabled, and, for a Job Environment, those an earlier
/// Environment of its ``exclusiveGroup`` superseded (Template Schemas §4
/// item 7). It is the ``DISABLED`` and ``SUPERSEDED`` items of the Step's
/// ``StepEnvironmentStatuses``, which says which of the two applied. A
/// ``BY_DEFAULT`` Environment the Step declined with a disabled
/// ``environment:`` entry is not listed.
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

// ── DiscardedHostRequirement ──

/// The kind of a discarded ``hostRequirements`` entry (Template Schemas
/// §3.3): an ``amounts`` entry or an ``attributes`` entry.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "HostRequirementKind",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyHostRequirementKind {
    AMOUNT = 0,
    ATTRIBUTE = 1,
}

impl From<openjd_model::HostRequirementKind> for PyHostRequirementKind {
    fn from(v: openjd_model::HostRequirementKind) -> Self {
        match v {
            openjd_model::HostRequirementKind::Amount => Self::AMOUNT,
            openjd_model::HostRequirementKind::Attribute => Self::ATTRIBUTE,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyHostRequirementKind {
    /// Variant name as a string (``"AMOUNT"`` or ``"ATTRIBUTE"``).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::AMOUNT => "AMOUNT",
            Self::ATTRIBUTE => "ATTRIBUTE",
        }
    }

    fn __repr__(&self) -> String {
        format!("HostRequirementKind.{}", self.name())
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(
        Bound<'py, PyAny>,
        (Bound<'py, pyo3::types::PyType>, &'static str),
    )> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

/// A host requirement that resolved to nothing for a Step and was
/// discarded (``ENV_PARAMS``, Template Schemas §3.3): an amount whose
/// ``min`` and ``max`` both resolved to ``null``, or an attribute whose
/// ``anyOf`` and ``allOf``, each written as one expression, resolved to
/// ``null``. For display.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "DiscardedHostRequirement",
    frozen,
    eq,
    from_py_object
)]
#[derive(Clone, PartialEq)]
pub(crate) struct PyDiscardedHostRequirement {
    pub(crate) inner: openjd_model::DiscardedHostRequirement,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyDiscardedHostRequirement {
    /// The Environment whose ``hostRequirements`` held it, or ``None`` for
    /// the Step's own.
    #[getter]
    fn environment(&self) -> Option<PyEnvironmentRef> {
        self.inner
            .environment
            .as_ref()
            .map(|e| PyEnvironmentRef { inner: e.clone() })
    }

    /// Whether it was an amount or an attribute requirement.
    #[getter]
    fn kind(&self) -> PyHostRequirementKind {
        self.inner.kind.into()
    }

    /// Its resolved capability name.
    #[getter]
    fn name(&self) -> String {
        self.inner.name.clone()
    }

    fn __repr__(&self) -> String {
        let env = match &self.inner.environment {
            Some(e) => PyEnvironmentRef { inner: e.clone() }.__repr__(),
            None => "None".to_string(),
        };
        format!(
            "DiscardedHostRequirement(environment={env}, kind={}, name={:?})",
            PyHostRequirementKind::from(self.inner.kind).__repr__(),
            self.inner.name
        )
    }
}

// ── Environment statuses ──

/// Whether one Step's Sessions enter an Environment they considered, and if
/// not, which decision of Template Schemas §7.4.1 left it out.
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "EnvironmentStatus",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyEnvironmentStatus {
    /// The Step's Sessions enter it.
    ENTERED = 0,
    /// A ``BY_DEFAULT`` Environment that a disabled ``environment:`` entry
    /// of the Step declines (§3.2 item 3.2). Its ``enableIf`` is not
    /// evaluated for the Step. Never an attached Environment whose
    /// Environment Template does not list ``ENV_PARAMS``: it behaves as
    /// ``ALWAYS``, and a disabled entry has no effect on it (§4 item 4).
    DECLINED = 1,
    /// Its own ``enableIf`` (§4 item 6) is false for the Step.
    DISABLED = 2,
    /// An earlier Environment of its ``exclusiveGroup`` remains in the
    /// Step's set (§4 item 7). Its ``enableIf`` is not evaluated for the
    /// Step.
    SUPERSEDED = 3,
}

impl From<openjd_model::EnvironmentStatus> for PyEnvironmentStatus {
    fn from(v: openjd_model::EnvironmentStatus) -> Self {
        match v {
            openjd_model::EnvironmentStatus::Entered => Self::ENTERED,
            openjd_model::EnvironmentStatus::Declined => Self::DECLINED,
            openjd_model::EnvironmentStatus::Disabled => Self::DISABLED,
            openjd_model::EnvironmentStatus::Superseded => Self::SUPERSEDED,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentStatus {
    /// Variant name as a string (``"ENTERED"``, ``"DECLINED"``,
    /// ``"DISABLED"`` or ``"SUPERSEDED"``).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::ENTERED => "ENTERED",
            Self::DECLINED => "DECLINED",
            Self::DISABLED => "DISABLED",
            Self::SUPERSEDED => "SUPERSEDED",
        }
    }

    fn __repr__(&self) -> String {
        format!("EnvironmentStatus.{}", self.name())
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(
        Bound<'py, PyAny>,
        (Bound<'py, pyo3::types::PyType>, &'static str),
    )> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

/// Where an Environment of a Job comes from: the three parts of the Job's
/// Environment order (Template Schemas §1.1 item 7).
#[cfg_attr(
    feature = "stub-gen",
    gen_stub_pyclass_enum(module = "openjd._openjd_rs")
)]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "EnvironmentScope",
    eq,
    eq_int,
    frozen,
    hash,
    from_py_object
)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
#[allow(non_camel_case_types, clippy::upper_case_acronyms)]
pub(crate) enum PyEnvironmentScope {
    /// An attached Environment Template's ``environment``.
    ATTACHED = 0,
    /// A ``jobEnvironments`` entry of the Job Template.
    JOB = 1,
    /// A ``stepEnvironments`` entry of the Step.
    STEP = 2,
}

impl From<openjd_model::EnvironmentScope> for PyEnvironmentScope {
    fn from(v: openjd_model::EnvironmentScope) -> Self {
        match v {
            openjd_model::EnvironmentScope::Attached => Self::ATTACHED,
            openjd_model::EnvironmentScope::Job => Self::JOB,
            openjd_model::EnvironmentScope::Step => Self::STEP,
        }
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyEnvironmentScope {
    /// Variant name as a string (``"ATTACHED"``, ``"JOB"`` or ``"STEP"``).
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            Self::ATTACHED => "ATTACHED",
            Self::JOB => "JOB",
            Self::STEP => "STEP",
        }
    }

    fn __repr__(&self) -> String {
        format!("EnvironmentScope.{}", self.name())
    }

    /// Pickle support — round-trips through the variant name.
    #[allow(clippy::type_complexity)] // pickle reducer tuple shape is by design
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(
        Bound<'py, PyAny>,
        (Bound<'py, pyo3::types::PyType>, &'static str),
    )> {
        let helper = py
            .import("openjd._openjd_rs")?
            .getattr("_reconstruct_enum")?;
        Ok((helper, (py.get_type::<Self>(), self.name())))
    }
}

/// One Environment a Step's Sessions considered, and whether they enter it.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepEnvironmentStatus",
    frozen,
    eq,
    hash,
    from_py_object
)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub(crate) struct PyStepEnvironmentStatus {
    pub(crate) inner: openjd_model::StepEnvironmentStatus,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepEnvironmentStatus {
    /// The Environment's ``name``.
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    /// The document that declares it: an Environment Template for an
    /// attached one, else the Job Template.
    #[getter]
    fn document(&self) -> PyDocument {
        PyDocument {
            inner: self.inner.document.clone(),
        }
    }

    /// Its part of the Job's Environment order. ``ATTACHED`` exactly when
    /// ``document`` is an Environment Template.
    #[getter]
    fn scope(&self) -> PyEnvironmentScope {
        self.inner.scope.into()
    }

    /// Whether the Step's Sessions enter it, or why not.
    #[getter]
    fn status(&self) -> PyEnvironmentStatus {
        self.inner.status.into()
    }

    /// The Environment's ``exclusiveGroup``, whatever its ``status``;
    /// ``None`` for one without, which includes every Step Environment.
    #[getter]
    fn exclusive_group(&self) -> Option<&str> {
        self.inner.exclusive_group.as_deref()
    }

    /// For a ``SUPERSEDED`` one, the member of its ``exclusiveGroup`` the
    /// Step's Sessions enter: the earliest in the Job's Environment order
    /// that remains in the Step's set. ``None`` for every other ``status``.
    #[getter]
    fn superseded_by(&self) -> Option<PySupersedingEnvironment> {
        self.inner
            .superseded_by
            .as_ref()
            .map(|w| PySupersedingEnvironment { inner: w.clone() })
    }

    fn __repr__(&self) -> String {
        format!(
            "StepEnvironmentStatus(name={:?}, document={}, scope={}, status={}, \
             exclusive_group={}, superseded_by={})",
            self.inner.name,
            PyDocument {
                inner: self.inner.document.clone()
            }
            .__repr__(),
            PyEnvironmentScope::from(self.inner.scope).__repr__(),
            PyEnvironmentStatus::from(self.inner.status).__repr__(),
            self.inner
                .exclusive_group
                .as_ref()
                .map_or_else(|| "None".to_string(), |g| format!("{g:?}")),
            self.inner.superseded_by.as_ref().map_or_else(
                || "None".to_string(),
                |w| PySupersedingEnvironment { inner: w.clone() }.__repr__()
            ),
        )
    }
}

/// The Environment that superseded another for a Step
/// (``StepEnvironmentStatus.superseded_by``): an attached or Job
/// Environment. ``name`` and ``document`` identify it among the Job's
/// Environments, also when an attached Environment and a Job Environment
/// share a name; ``scope`` follows from ``document`` and is given so the
/// winner's own status item can be matched on the same three fields.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "SupersedingEnvironment",
    frozen,
    eq,
    hash,
    from_py_object
)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub(crate) struct PySupersedingEnvironment {
    pub(crate) inner: openjd_model::SupersedingEnvironment,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySupersedingEnvironment {
    /// The Environment's ``name``.
    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    /// The document that declares it, as in
    /// ``StepEnvironmentStatus.document``.
    #[getter]
    fn document(&self) -> PyDocument {
        PyDocument {
            inner: self.inner.document.clone(),
        }
    }

    /// Its part of the Job's Environment order: ``ATTACHED`` or ``JOB``.
    #[getter]
    fn scope(&self) -> PyEnvironmentScope {
        self.inner.scope.into()
    }

    fn __repr__(&self) -> String {
        format!(
            "SupersedingEnvironment(name={:?}, document={}, scope={})",
            self.inner.name,
            PyDocument {
                inner: self.inner.document.clone()
            }
            .__repr__(),
            PyEnvironmentScope::from(self.inner.scope).__repr__(),
        )
    }
}

/// An enabled ``environment:`` entry with ``required: false`` that resolved
/// to no Environment (Template Schemas §3.2.1 item 2), so it has no effect.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "OptionalEntryNotFound",
    frozen,
    eq,
    hash,
    from_py_object
)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub(crate) struct PyOptionalEntryNotFound {
    pub(crate) inner: openjd_model::OptionalEntryNotFound,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyOptionalEntryNotFound {
    /// The entry's 0-based position in the Step's ``dependencies`` list.
    #[getter]
    fn dependency_index(&self) -> usize {
        self.inner.dependency_index
    }

    /// The Environment name the entry gives.
    #[getter]
    fn environment(&self) -> &str {
        &self.inner.environment
    }

    fn __repr__(&self) -> String {
        format!(
            "OptionalEntryNotFound(dependency_index={}, environment={:?})",
            self.inner.dependency_index, self.inner.environment
        )
    }
}

/// Every Environment one Step considered, with whether its Sessions enter
/// it, and its optional entries that named nothing.
///
/// A Step considers every ``ALWAYS`` and ``BY_DEFAULT`` Environment, every
/// ``ON_REQUEST`` one an enabled ``environment:`` entry of the Step
/// requests, and each of its Step Environments. An ``ON_REQUEST``
/// Environment the Step does not request is not listed. An attached
/// Environment whose Environment Template does not list ``ENV_PARAMS``
/// behaves as ``ALWAYS``, so it is always ``ENTERED``.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(
    module = "openjd.model._v1.job",
    name = "StepEnvironmentStatuses",
    frozen,
    eq,
    from_py_object
)]
#[derive(Clone, PartialEq)]
pub(crate) struct PyStepEnvironmentStatuses {
    pub(crate) inner: openjd_model::StepEnvironmentStatuses,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepEnvironmentStatuses {
    /// The considered Environments in the Job's Environment order: attached
    /// ones in attachment order, then the Job Template's
    /// ``jobEnvironments``, then the Step's ``stepEnvironments``. The
    /// ``ENTERED`` ones, in this order, are the Environments the Step's
    /// Sessions enter.
    #[getter]
    fn environments(&self) -> Vec<PyStepEnvironmentStatus> {
        self.inner
            .environments
            .iter()
            .map(|e| PyStepEnvironmentStatus { inner: e.clone() })
            .collect()
    }

    /// The Step's enabled ``required: false`` entries that named no
    /// Environment, in ``dependencies`` order. Each also produced a
    /// ``CreatedJob.warnings`` entry.
    #[getter]
    fn not_found(&self) -> Vec<PyOptionalEntryNotFound> {
        self.inner
            .not_found
            .iter()
            .map(|n| PyOptionalEntryNotFound { inner: n.clone() })
            .collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "StepEnvironmentStatuses(environments={}, not_found={})",
            self.inner.environments.len(),
            self.inner.not_found.len()
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

    /// Per Step of ``job``, index for index, the Environments disabled for
    /// that Step: by their ``enableIf``, or superseded within their
    /// ``exclusiveGroup``. ``environment_statuses`` says which.
    #[getter]
    fn disabled_environments(&self) -> Vec<PyStepDisabledEnvironments> {
        self.inner
            .disabled_environments
            .iter()
            .map(|d| PyStepDisabledEnvironments { inner: d.clone() })
            .collect()
    }

    /// Per Step of ``job``, index for index, every Environment the Step
    /// considered, in the Job's Environment order, with whether its Sessions
    /// enter it or which decision left it out, and the Step's
    /// ``required: false`` entries that named no Environment.
    #[getter]
    fn environment_statuses(&self) -> Vec<PyStepEnvironmentStatuses> {
        self.inner
            .environment_statuses
            .iter()
            .map(|s| PyStepEnvironmentStatuses { inner: s.clone() })
            .collect()
    }

    /// Per Step of ``job``, index for index, the host requirements that
    /// resolved to nothing for that Step and were discarded (``ENV_PARAMS``,
    /// Template Schemas §3.3): the Step's own first, then each entered
    /// Environment's, in Job order, each in written order with amounts
    /// first. Empty for a Step with none.
    #[getter]
    fn discarded_host_requirements(&self) -> Vec<Vec<PyDiscardedHostRequirement>> {
        self.inner
            .discarded_host_requirements
            .iter()
            .map(|step| {
                step.iter()
                    .map(|d| PyDiscardedHostRequirement { inner: d.clone() })
                    .collect()
            })
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
