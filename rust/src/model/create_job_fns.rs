// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use pyo3::types::PyDict;

use openjd_model::types::{JobParameterValues, JobParameterValue, JobParameterType, JobParameterInputValues};
use openjd_model::EnvironmentTemplate;
use openjd_model::PathParameterOptions;

use crate::expr::expr_value::py_to_expr_value;

use super::errors::model_err_to_py;
use super::template::{PyJobTemplate, PyEnvironmentTemplate};
use super::job::{PyJob, PyEnvironment, PyStep};

fn extract_input_values(py_dict: &Bound<'_, PyDict>) -> PyResult<JobParameterInputValues> {
    let mut result = JobParameterInputValues::new();
    for (key, val) in py_dict.iter() {
        let name: String = key.extract()?;
        if let Ok(inner_dict) = val.cast::<PyDict>() {
            if let Some(v) = inner_dict.get_item("value")? {
                result.insert(name, py_to_expr_value(&v)?);
            }
        } else {
            result.insert(name, py_to_expr_value(&val)?);
        }
    }
    Ok(result)
}

fn coerce_value_to_type(value: openjd_expr::ExprValue, param_type: JobParameterType) -> openjd_expr::ExprValue {
    use openjd_expr::path_mapping::PathFormat;
    if let openjd_expr::ExprValue::String(ref s) = value {
        let target = match param_type {
            JobParameterType::Int => openjd_expr::ExprType::INT,
            JobParameterType::Float => openjd_expr::ExprType::FLOAT,
            JobParameterType::Bool => openjd_expr::ExprType::BOOL,
            JobParameterType::Path => openjd_expr::ExprType::PATH,
            _ => return value,
        };
        openjd_expr::ExprValue::from_str_coerce(s, &target, PathFormat::host())
            .unwrap_or(value)
    } else {
        value
    }
}

fn extract_parameter_values(py_dict: &Bound<'_, PyDict>) -> PyResult<JobParameterValues> {
    let mut result = JobParameterValues::new();
    for (key, val) in py_dict.iter() {
        let name: String = key.extract()?;
        // Try as a dict with "type" and "value" keys
        if let Ok(inner_dict) = val.cast::<PyDict>() {
            let type_str: String = inner_dict.get_item("type")?
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'type' key"))?
                .extract()?;
            let param_type = JobParameterType::from_spec_str(&type_str)
                .ok_or_else(|| pyo3::exceptions::PyValueError::new_err(format!("Unknown parameter type: {type_str}")))?;
            let value_obj = inner_dict.get_item("value")?
                .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("Missing 'value' key"))?;
            let value = coerce_value_to_type(py_to_expr_value(&value_obj)?, param_type);
            result.insert(name, JobParameterValue { param_type, value });
        }
        // Try as an object with .type and .value attributes (ParameterValue, JobParameterValue)
        else if let (Ok(type_attr), Ok(value_attr)) = (val.getattr("type"), val.getattr("value")) {
            let type_str: String = type_attr.call_method0("as_str")?.extract()?;
            let param_type = JobParameterType::from_spec_str(&type_str)
                .ok_or_else(|| pyo3::exceptions::PyValueError::new_err(format!("Unknown parameter type: {type_str}")))?;
            let value = coerce_value_to_type(py_to_expr_value(&value_attr)?, param_type);
            result.insert(name, JobParameterValue { param_type, value });
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "Each parameter value must be a dict with 'type'/'value' keys or an object with .type/.value attributes"
            ));
        }
    }
    Ok(result)
}

fn extract_env_templates(env_templates: Option<Vec<PyEnvironmentTemplate>>) -> Vec<EnvironmentTemplate> {
    env_templates.map(|v| v.into_iter().map(|e| e.inner).collect()).unwrap_or_default()
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction(name = "create_job")]
#[pyo3(signature = (*, job_template, job_parameter_values, environment_templates=None))]
pub(crate) fn py_create_job(
    job_template: &PyJobTemplate,
    job_parameter_values: &Bound<'_, PyDict>,
    environment_templates: Option<Vec<PyEnvironmentTemplate>>,
) -> PyResult<PyJob> {
    let env_templates = extract_env_templates(environment_templates);
    let params = extract_parameter_values(job_parameter_values)?;

    // Validate constraints from job + env templates before calling create_job
    let merged = openjd_model::merge_job_parameter_definitions(
        &job_template.inner, &env_templates
    ).map_err(model_err_to_py)?;
    for param in &merged {
        if let Some(jpv) = params.get(&param.name) {
            param.check_constraints(&jpv.value).map_err(model_err_to_py)?;
        }
    }

    let ctx = job_template.inner.default_validation_context();
    let job = openjd_model::create_job(&job_template.inner, &params, &ctx)
        .map_err(model_err_to_py)?;
    Ok(PyJob { inner: job })
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction(name = "preprocess_job_parameters")]
#[pyo3(signature = (*, job_template, job_parameter_values, environment_templates=None, job_template_dir, current_working_dir, allow_job_template_dir_walk_up=false))]
pub(crate) fn py_preprocess_job_parameters(
    py: Python<'_>,
    job_template: &PyJobTemplate,
    job_parameter_values: &Bound<'_, PyDict>,
    environment_templates: Option<Vec<PyEnvironmentTemplate>>,
    job_template_dir: std::path::PathBuf,
    current_working_dir: std::path::PathBuf,
    allow_job_template_dir_walk_up: bool,
) -> PyResult<Py<PyDict>> {
    let input_values = extract_input_values(job_parameter_values)?;
    let env_templates = extract_env_templates(environment_templates);
    let tdir_str = job_template_dir.to_str().unwrap_or("");
    let cwd_str = current_working_dir.to_str().unwrap_or("");
    let tdir = if tdir_str == "." { "" } else { tdir_str };
    let cwd = if cwd_str == "." { "" } else { cwd_str };
    let path_opts = PathParameterOptions {
        job_template_dir: tdir,
        current_working_dir: cwd,
        path_format: openjd_expr::path_mapping::PathFormat::host(),
        allow_template_dir_walk_up: allow_job_template_dir_walk_up,
        allow_uri_path_values: false,
    };
    let result = openjd_model::preprocess_job_parameters(
        &job_template.inner,
        &input_values,
        &env_templates,
        &path_opts,
    ).map_err(model_err_to_py)?;

    use pyo3::IntoPyObjectExt;
    let out = PyDict::new(py);
    for (name, jpv) in &result {
        let pv = super::types::PyJobParameterValue {
            param_type: jpv.param_type.into(),
            value: jpv.value.to_display_string(),
        };
        out.set_item(name, pv.into_py_any(py)?)?;
    }
    Ok(out.unbind())
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction(name = "merge_job_parameter_definitions")]
#[pyo3(signature = (*, job_template, environment_templates=None))]
pub(crate) fn py_merge_job_parameter_definitions(
    py: Python<'_>,
    job_template: &PyJobTemplate,
    environment_templates: Option<Vec<PyEnvironmentTemplate>>,
) -> PyResult<Vec<Py<PyDict>>> {
    let env_templates = extract_env_templates(environment_templates);
    let merged = openjd_model::merge_job_parameter_definitions(&job_template.inner, &env_templates)
        .map_err(model_err_to_py)?;

    let mut out = Vec::new();
    for m in &merged {
        let d = PyDict::new(py);
        d.set_item("name", &m.name)?;
        d.set_item("type", m.param_type.as_spec_str())?;
        if let Some(ref default) = m.default {
            d.set_item("default", default)?;
        }
        if let Some(ref ot) = m.object_type {
            d.set_item("objectType", ot.to_string())?;
        }
        if let Some(ref df) = m.data_flow {
            d.set_item("dataFlow", df.to_string())?;
        }
        d.set_item("source", &m.source)?;
        out.push(d.unbind());
    }
    Ok(out)
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(name = "evaluate_let_bindings")]
#[pyo3(signature = (bindings, symtab, library=None))]
pub(crate) fn py_evaluate_let_bindings(
    bindings: Vec<String>,
    symtab: &crate::expr::PySymbolTable,
    library: Option<&crate::expr::PyFunctionLibrary>,
) -> PyResult<crate::expr::PySymbolTable> {
    let default_lib;
    let lib = library.map(|l| l.inner.clone());
    let lib_ref = match &lib {
        Some(l) => l,
        None => {
            let arc = openjd_expr::FunctionLibrary::for_profile(
                &openjd_expr::profile::ExprProfile::current()
            );
            default_lib = (*arc).clone();
            &default_lib
        }
    };
    let result = openjd_model::evaluate_let_bindings(
        &bindings,
        &symtab.inner,
        Some(lib_ref),
        openjd_expr::path_mapping::PathFormat::host(),
    ).map_err(super::errors::model_err_to_py)?;
    Ok(crate::expr::PySymbolTable { inner: result })
}

/// Deserialize a job-side `Step` from a Python dict. This matches the
/// payload shape that the Deadline Cloud service's `GetStepDetails` /
/// `BatchGetJobEntity` API returns in the `template` field: it is a
/// serialized `openjd_model::job::Step`, not a template-side StepTemplate.
///
/// Consumers like the Deadline Cloud worker agent use this to reconstruct
/// a `Step` object from the wire payload so they can pass its
/// parameter_space to the step-parameter-space iterator and its script
/// to `Session.run_task`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction(name = "deserialize_step")]
pub(crate) fn py_deserialize_step(step_dict: &Bound<'_, PyDict>) -> PyResult<PyStep> {
    use openjd_model::job;
    let json_str: String = {
        let json_mod = step_dict.py().import("json")?;
        json_mod.call_method1("dumps", (step_dict,))?.extract()?
    };
    let step: job::Step = serde_json::from_str(&json_str)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(
            format!("failed to deserialize Step: {e}")
        ))?;
    Ok(PyStep { inner: step })
}

/// Convert a template `EnvironmentTemplate` into a job-side `Environment` with
/// the same contents. Analogous to how `create_job` instantiates a `JobTemplate`
/// into a `Job`, but for a standalone environment (no job parameters involved
/// in environment-only templates).
///
/// Consumers like the Deadline Cloud worker agent need this to turn the
/// `EnvironmentDetails` boto payload into an `Environment` they can pass to
/// `Session.enter_environment`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction(name = "create_environment")]
pub(crate) fn py_create_environment(env_template: &PyEnvironmentTemplate) -> PyEnvironment {
    let env = openjd_model::convert_environment(&env_template.inner.environment);
    PyEnvironment { inner: env }
}
