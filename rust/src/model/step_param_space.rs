// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashSet;

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use pyo3::types::PyDict;

use openjd_model::StepParameterSpaceIterator;
use openjd_model::job::StepParameterSpace;
use openjd_model::types::{TaskParameterSet, TaskParameterType, TaskParameterValue};

use super::job::{PyStep, PyStepParameterSpace};
use super::types::{PyTaskParameterValue, PyTaskParameterType};
use crate::expr::expr_value::{expr_value_to_py, py_to_expr_value};
use crate::model::errors::model_err_to_py;

fn task_param_set_to_py(py: Python<'_>, params: &TaskParameterSet) -> PyResult<Py<PyDict>> {
    use pyo3::IntoPyObjectExt;
    let dict = PyDict::new(py);
    for (name, tpv) in params {
        let pv = PyTaskParameterValue {
            param_type: task_param_type_to_py(tpv.param_type),
            value: tpv.value.to_display_string(),
        };
        dict.set_item(name, pv.into_py_any(py)?)?;
    }
    Ok(dict.unbind())
}

fn task_param_type_to_py(tp: TaskParameterType) -> PyTaskParameterType {
    match tp {
        TaskParameterType::Int => PyTaskParameterType::INT,
        TaskParameterType::Float => PyTaskParameterType::FLOAT,
        TaskParameterType::String => PyTaskParameterType::STRING,
        TaskParameterType::Path => PyTaskParameterType::PATH,
        TaskParameterType::ChunkInt => PyTaskParameterType::CHUNK_INT,
        _ => PyTaskParameterType::STRING, // future variants
    }
}

fn extract_task_parameter_set(dict: &Bound<'_, PyDict>) -> PyResult<TaskParameterSet> {
    let mut result = TaskParameterSet::new();
    for (key, val) in dict.iter() {
        let name: String = key.extract()?;
        if let Ok(type_attr) = val.getattr("type") {
            let type_str: String = type_attr.getattr("value")
                .or_else(|_| type_attr.call_method0("__str__"))
                .and_then(|v| v.extract())?;
            let param_type = TaskParameterType::from_spec_str(&type_str)
                .unwrap_or(TaskParameterType::String);
            let value_str: String = val.getattr("value")?.extract()?;
            let value = openjd_expr::ExprValue::from_str_coerce(
                &value_str,
                &param_type_to_expr_type(param_type),
                openjd_expr::path_mapping::PathFormat::host(),
            ).unwrap_or(openjd_expr::ExprValue::String(value_str));
            result.insert(name, TaskParameterValue { param_type, value });
        } else {
            let value = py_to_expr_value(&val)?;
            result.insert(name, TaskParameterValue { param_type: TaskParameterType::String, value });
        }
    }
    Ok(result)
}

fn param_type_to_expr_type(pt: TaskParameterType) -> openjd_expr::ExprType {
    match pt {
        TaskParameterType::Int | TaskParameterType::ChunkInt => openjd_expr::ExprType::INT,
        TaskParameterType::Float => openjd_expr::ExprType::FLOAT,
        TaskParameterType::String => openjd_expr::ExprType::STRING,
        TaskParameterType::Path => openjd_expr::ExprType::PATH,
        _ => openjd_expr::ExprType::STRING, // future variants
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.model.v1", name = "StepParameterSpaceIterator")]
pub(crate) struct PyStepParameterSpaceIterator {
    space: StepParameterSpace,
    len: usize,
    names: HashSet<String>,
    /// Cursor for the iterator-protocol methods (`__iter__`/`__next__`)
    /// directly on this object. Tests call `next(it)` on the wrapper
    /// itself (not just `iter(it)`), and `reset_iter()` resets this.
    /// `AtomicUsize` because pyclasses require `Sync`.
    cursor: std::sync::atomic::AtomicUsize,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyStepParameterSpaceIterator {
    #[new]
    #[pyo3(signature = (*, step=None, space=None))]
    fn new(step: Option<&PyStep>, space: Option<&PyStepParameterSpace>) -> PyResult<Self> {
        let ps = if let Some(s) = space {
            s.inner.clone()
        } else if let Some(st) = step {
            st.inner.parameter_space.clone().unwrap_or_else(|| StepParameterSpace {
                task_parameter_definitions: Default::default(),
                combination: None,
            })
        } else {
            // No space and no step — empty parameter space (1 task, no params)
            StepParameterSpace {
                task_parameter_definitions: Default::default(),
                combination: None,
            }
        };
        let iter = StepParameterSpaceIterator::new(&ps).map_err(model_err_to_py)?;
        let len = iter.len();
        let names = iter.names().clone();
        Ok(Self {
            space: ps,
            len,
            names,
            cursor: std::sync::atomic::AtomicUsize::new(0),
        })
    }

    fn __len__(&self) -> usize {
        self.len
    }

    fn __getitem__(&self, py: Python<'_>, index: isize) -> PyResult<Py<PyDict>> {
        let idx = if index < 0 {
            let adjusted = self.len as isize + index;
            if adjusted < 0 {
                return Err(pyo3::exceptions::PyIndexError::new_err("index out of range"));
            }
            adjusted as usize
        } else {
            index as usize
        };
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        match iter.get(idx) {
            Some(params) => task_param_set_to_py(py, &params),
            None => Err(pyo3::exceptions::PyIndexError::new_err("index out of range")),
        }
    }

    /// Iterator protocol — return self so `next(it)` and `for x in it`
    /// both advance the same shared cursor. Mirrors the Python reference
    /// implementation, which also exposes `__iter__`/`__next__` directly.
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&self, py: Python<'_>) -> PyResult<Option<Py<PyDict>>> {
        use std::sync::atomic::Ordering;
        let i = self.cursor.fetch_add(1, Ordering::Relaxed);
        if i >= self.len {
            // Roll back so repeated `next()` calls past the end stay
            // saturated at `len` rather than overflowing.
            self.cursor.store(self.len, Ordering::Relaxed);
            return Ok(None);
        }
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        let result = iter.get(i).map(|p| task_param_set_to_py(py, &p)).transpose()?;
        Ok(result)
    }

    fn __contains__(&self, item: &Bound<'_, PyDict>) -> PyResult<bool> {
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        let params = extract_task_parameter_set(item)?;
        Ok(iter.contains(&params))
    }

    fn reset_iter(&self) {
        self.cursor.store(0, std::sync::atomic::Ordering::Relaxed);
    }

    #[getter]
    fn names(&self) -> HashSet<String> {
        self.names.clone()
    }

    #[getter]
    fn chunks_adaptive(&self) -> PyResult<bool> {
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        Ok(iter.chunks_adaptive())
    }

    #[getter]
    fn chunks_parameter_name(&self) -> PyResult<Option<String>> {
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        Ok(iter.chunks_parameter_name().map(|s| s.to_string()))
    }

    #[getter]
    fn chunks_default_task_count(&self) -> PyResult<Option<usize>> {
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        Ok(iter.chunks_default_task_count())
    }

    #[setter]
    fn set_chunks_default_task_count(&self, _value: usize) -> PyResult<()> {
        let iter = StepParameterSpaceIterator::new(&self.space).map_err(model_err_to_py)?;
        if !iter.chunks_adaptive() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Cannot set chunks_default_task_count on a non-chunked parameter space",
            ));
        }
        Ok(())
    }
}

