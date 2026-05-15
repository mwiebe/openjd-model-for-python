// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use pyo3::types::{PyBool, PyFloat, PyInt, PyList, PyString};

use openjd_expr::path_mapping::PathFormat;
use openjd_expr::types::ExprType;
use openjd_expr::value::ExprValue;

use crate::expr::expr_type::{extract_expr_type, PyExprType};
use crate::expr::path_format::PyPathFormat;
use crate::expr::range_expr::PyRangeExpr;

pub(crate) fn py_to_expr_value(obj: &Bound<'_, pyo3::PyAny>) -> PyResult<ExprValue> {
    if obj.is_none() {
        return Ok(ExprValue::Null);
    }
    if let Ok(b) = obj.cast::<PyBool>() {
        return Ok(ExprValue::Bool(b.is_true()));
    }
    if let Ok(i) = obj.cast::<PyInt>() {
        return Ok(ExprValue::Int(i.extract::<i64>()?));
    }
    if let Ok(f) = obj.cast::<PyFloat>() {
        let float = openjd_expr::value::Float64::new(f.extract::<f64>()?)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        return Ok(ExprValue::Float(float));
    }
    if let Ok(s) = obj.cast::<PyString>() {
        return Ok(ExprValue::String(s.to_cow()?.to_string()));
    }
    // Handle decimal.Decimal: extract float value + original string representation
    if obj.get_type().name()? == "Decimal" {
        let f: f64 = obj.call_method0("__float__")?.extract()?;
        let s: String = obj.call_method0("__str__")?.extract()?;
        let float = openjd_expr::value::Float64::with_str(f, s)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        return Ok(ExprValue::Float(float));
    }
    if let Ok(ev) = obj.extract::<PyExprValue>() {
        return Ok(ev.inner);
    }
    if let Ok(r) = obj.extract::<PyRangeExpr>() {
        return Ok(ExprValue::RangeExpr(r.inner));
    }
    if let Ok(t) = obj.extract::<PyExprType>() {
        return Ok(ExprValue::Unresolved(t.inner));
    }
    if let Ok(list) = obj.cast::<PyList>() {
        let elements: PyResult<Vec<ExprValue>> = list.iter().map(|item| py_to_expr_value(&item)).collect();
        let elements = elements?;
        let hint = elements.first().map(|e| e.expr_type()).unwrap_or(ExprType::NULLTYPE);
        return ExprValue::make_list(elements, hint)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()));
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "Cannot convert {} to ExprValue",
        obj.get_type().name()?
    )))
}

pub(crate) fn expr_value_to_py(py: Python<'_>, val: &ExprValue) -> Py<pyo3::PyAny> {
    use pyo3::IntoPyObjectExt;
    match val {
        ExprValue::Null => py.None(),
        ExprValue::Bool(b) => b.into_py_any(py).unwrap(),
        ExprValue::Int(i) => i.into_py_any(py).unwrap(),
        ExprValue::Float(f) => f.value().into_py_any(py).unwrap(),
        ExprValue::String(s) => s.into_py_any(py).unwrap(),
        ExprValue::Path { value, .. } => value.into_py_any(py).unwrap(),
        ExprValue::RangeExpr(r) => {
            PyRangeExpr { inner: r.clone() }.into_py_any(py).unwrap()
        }
        ExprValue::Unresolved(_) => py.None(),
        val if val.is_list() => {
            let elements = val.list_elements().unwrap_or_default();
            let items: Vec<Py<pyo3::PyAny>> = elements.iter().map(|e| expr_value_to_py(py, e)).collect();
            PyList::new(py, items).unwrap().into_any().unbind()
        }
        _ => py.None(),
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ExprValue", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyExprValue {
    pub(crate) inner: ExprValue,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyExprValue {
    #[new]
    #[pyo3(signature = (value, r#type=None, path_format=None))]
    fn new(
        value: &Bound<'_, pyo3::PyAny>,
        r#type: Option<&Bound<'_, pyo3::PyAny>>,
        path_format: Option<PyPathFormat>,
    ) -> PyResult<Self> {
        let target = match r#type {
            Some(type_obj) => Some(extract_expr_type(type_obj)?),
            None => None,
        };
        let pf = path_format.map(PathFormat::from).unwrap_or_else(PathFormat::host);

        // Build the inner value, using target type as hint for list construction
        let inner = if let Ok(list) = value.cast::<PyList>() {
            let elements: PyResult<Vec<ExprValue>> = list.iter().map(|item| py_to_expr_value(&item)).collect();
            let elements = elements?;
            let hint = if let Some(ref t) = target {
                t.params().first().cloned().unwrap_or(ExprType::STRING)
            } else {
                elements.first().map(|e| e.expr_type()).unwrap_or(ExprType::NULLTYPE)
            };
            ExprValue::make_list(elements, hint)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
        } else {
            py_to_expr_value(value)?
        };

        match target {
            None => Ok(PyExprValue { inner }),
            Some(target) => {
                let coerced = match &inner {
                    ExprValue::String(s) => ExprValue::from_str_coerce(&s, &target, pf),
                    _ => inner.coerce(&target, pf),
                };
                coerced.map(|v| PyExprValue { inner: v })
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
            }
        }
    }

    #[staticmethod]
    fn unresolved(ty: &Bound<'_, pyo3::PyAny>) -> PyResult<Self> {
        let expr_type = extract_expr_type(ty)?;
        Ok(PyExprValue { inner: ExprValue::Unresolved(expr_type) })
    }

    #[staticmethod]
    fn from_float(value: f64, original_str: String) -> PyResult<Self> {
        let float = openjd_expr::value::Float64::with_str(value, original_str)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(PyExprValue { inner: ExprValue::Float(float) })
    }

    #[getter]
    fn r#type(&self) -> PyExprType {
        PyExprType { inner: self.inner.expr_type() }
    }

    #[getter]
    fn is_null(&self) -> bool {
        matches!(self.inner, ExprValue::Null)
    }


    fn item(&self, py: Python<'_>) -> Py<pyo3::PyAny> {
        expr_value_to_py(py, &self.inner)
    }


    fn __len__(&self) -> PyResult<usize> {
        match &self.inner {
            ExprValue::RangeExpr(r) => Ok(r.len()),
            _ => self.inner.list_len().ok_or_else(|| pyo3::exceptions::PyTypeError::new_err("ExprValue is not a list or range_expr")),
        }
    }

    fn __getitem__(&self, index: isize) -> PyResult<PyExprValue> {
        let len = self.__len__()?;
        let idx = if index < 0 { len as isize + index } else { index };
        if idx < 0 || idx as usize >= len {
            return Err(pyo3::exceptions::PyIndexError::new_err("index out of range"));
        }
        match &self.inner {
            ExprValue::RangeExpr(r) => r.get(idx as i64)
                .map(|i| PyExprValue { inner: ExprValue::Int(i) })
                .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("index out of range")),
            _ => self.inner.list_elements()
                .and_then(|v| v.into_iter().nth(idx as usize))
                .map(|e| PyExprValue { inner: e })
                .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("index out of range")),
        }
    }

    fn __iter__(slf: Py<Self>, py: Python<'_>) -> PyResult<Py<PyExprValueIter>> {
        let inner = &slf.borrow(py).inner;
        let elements: Vec<PyExprValue> = match inner {
            ExprValue::RangeExpr(r) => r.iter().map(|i| PyExprValue { inner: ExprValue::Int(i) }).collect(),
            _ => inner.list_elements()
                .ok_or_else(|| pyo3::exceptions::PyTypeError::new_err("ExprValue is not a list or range_expr"))?
                .into_iter().map(|e| PyExprValue { inner: e }).collect(),
        };
        Py::new(py, PyExprValueIter { elements, pos: 0 })
    }

    fn __str__(&self) -> String {
        self.inner.to_display_string()
    }

    fn __repr__(&self) -> String {
        self.inner.repr_python()
    }

    fn __bool__(&self) -> bool {
        match &self.inner {
            ExprValue::Null => false,
            ExprValue::Bool(b) => *b,
            ExprValue::Int(i) => *i != 0,
            ExprValue::Float(f) => f.value() != 0.0,
            ExprValue::String(s) => !s.is_empty(),
            ExprValue::Path { value, .. } => !value.is_empty(),
            ExprValue::RangeExpr(r) => !r.is_empty(),
            _ if self.inner.is_list() => self.inner.list_len().unwrap_or(0) > 0,
            _ => false,
        }
    }

    fn __eq__(&self, other: &PyExprValue) -> bool {
        self.inner.equals(&other.inner)
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr")]
struct PyExprValueIter {
    elements: Vec<PyExprValue>,
    pos: usize,
}

#[pymethods]
impl PyExprValueIter {
    fn __iter__(slf: Py<Self>) -> Py<Self> { slf }

    fn __next__(&mut self) -> Option<PyExprValue> {
        if self.pos < self.elements.len() {
            let val = self.elements[self.pos].clone();
            self.pos += 1;
            Some(val)
        } else {
            None
        }
    }
}
