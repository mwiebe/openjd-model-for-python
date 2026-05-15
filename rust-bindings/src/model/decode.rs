// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use pyo3::types::PyDict;

use openjd_model::parse::DocumentType;
use openjd_model::CallerLimits;

use super::errors::model_err_to_py;
use super::types::PyDocumentType;
use super::template::{PyJobTemplate, PyEnvironmentTemplate};

/// Parse a raw string into serde_json::Value based on document type.
fn parse_string(document: &str, format: PyDocumentType) -> PyResult<serde_json::Value> {
    let doc_type: DocumentType = format.into();
    openjd_model::parse::document_string_to_object(document, doc_type, &CallerLimits::default())
        .map_err(model_err_to_py)
}

/// Convert a Python dict to serde_json::Value via JSON round-trip.
fn dict_to_json_value(template: &Bound<'_, PyDict>) -> PyResult<serde_json::Value> {
    let json_str: String = {
        let json_mod = template.py().import("json")?;
        json_mod.call_method1("dumps", (template,))?.extract()?
    };
    serde_json::from_str(&json_str)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// Borrow `Option<Vec<String>>` as `Option<&[&str]>` for the Rust API.
fn as_supported_slice(v: &Option<Vec<String>>) -> Option<Vec<&str>> {
    v.as_ref().map(|exts| exts.iter().map(String::as_str).collect())
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(signature = (document, format=PyDocumentType::YAML, supported_extensions=None))]
pub(crate) fn decode_job_template_str(
    document: &str,
    format: PyDocumentType,
    supported_extensions: Option<Vec<String>>,
) -> PyResult<PyJobTemplate> {
    let value = parse_string(document, format)?;
    let exts = as_supported_slice(&supported_extensions);
    let jt = openjd_model::decode_job_template(value, exts.as_deref(), &CallerLimits::default())
        .map_err(model_err_to_py)?;
    Ok(PyJobTemplate { inner: jt })
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(signature = (template, supported_extensions=None))]
pub(crate) fn decode_job_template_dict(
    template: &Bound<'_, PyDict>,
    supported_extensions: Option<Vec<String>>,
) -> PyResult<PyJobTemplate> {
    let value = dict_to_json_value(template)?;
    let exts = as_supported_slice(&supported_extensions);
    let jt = openjd_model::decode_job_template(value, exts.as_deref(), &CallerLimits::default())
        .map_err(model_err_to_py)?;
    Ok(PyJobTemplate { inner: jt })
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(signature = (document, format=PyDocumentType::YAML, supported_extensions=None))]
pub(crate) fn decode_environment_template_str(
    document: &str,
    format: PyDocumentType,
    supported_extensions: Option<Vec<String>>,
) -> PyResult<PyEnvironmentTemplate> {
    let value = parse_string(document, format)?;
    let exts = as_supported_slice(&supported_extensions);
    let et = openjd_model::decode_environment_template(value, exts.as_deref())
        .map_err(model_err_to_py)?;
    Ok(PyEnvironmentTemplate { inner: et })
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(signature = (template, supported_extensions=None))]
pub(crate) fn decode_environment_template_dict(
    template: &Bound<'_, PyDict>,
    supported_extensions: Option<Vec<String>>,
) -> PyResult<PyEnvironmentTemplate> {
    let value = dict_to_json_value(template)?;
    let exts = as_supported_slice(&supported_extensions);
    let et = openjd_model::decode_environment_template(value, exts.as_deref())
        .map_err(model_err_to_py)?;
    Ok(PyEnvironmentTemplate { inner: et })
}
