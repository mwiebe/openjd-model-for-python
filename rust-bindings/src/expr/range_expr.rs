// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::range_expr::RangeExpr;

use crate::expr::errors::PyRangeExprError;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "RangeExpr", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyRangeExpr {
    pub(crate) inner: RangeExpr,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyRangeExpr {
    #[new]
    fn new(expr: &str) -> PyResult<Self> {
        expr.parse::<RangeExpr>()
            .map(|inner| PyRangeExpr { inner })
            .map_err(|e| PyRangeExprError::new_err(e.to_string()))
    }

    #[staticmethod]
    fn from_str(expr: &str) -> PyResult<Self> {
        expr.parse::<RangeExpr>()
            .map(|inner| PyRangeExpr { inner })
            .map_err(|e| PyRangeExprError::new_err(e.to_string()))
    }

    fn __len__(&self) -> usize {
        self.inner.len()
    }

    fn __eq__(&self, other: &PyRangeExpr) -> bool {
        self.inner == other.inner
    }

    fn __contains__(&self, value: i64) -> bool {
        self.inner.contains(value)
    }

    fn __getitem__(&self, index: isize) -> PyResult<i64> {
        let len = self.inner.len();
        let idx = if index < 0 { len as isize + index } else { index };
        if idx < 0 || idx as usize >= len {
            return Err(pyo3::exceptions::PyIndexError::new_err("index out of range"));
        }
        self.inner.get(idx as i64).ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("index out of range"))
    }

    fn __iter__(&self) -> PyRangeExprIter {
        PyRangeExprIter { values: self.inner.to_vec(), pos: 0 }
    }

    fn __str__(&self) -> String {
        self.inner.to_string()
    }

    fn __repr__(&self) -> String {
        format!("RangeExpr(\"{}\")", self.inner)
    }

    fn ranges(&self) -> Vec<(i64, i64, i64)> {
        self.inner.ranges().iter().map(|r| (r.start, r.end, r.step)).collect()
    }

    /// Pickle support — round-trips through the canonical string
    /// representation (e.g. `"1-10"`, `"1-10:2,20-30"`).
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, PyType>, (String,))> {
        Ok((py.get_type::<Self>(), (self.inner.to_string(),)))
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr")]
pub(crate) struct PyRangeExprIter {
    values: Vec<i64>,
    pos: usize,
}

#[pymethods]
impl PyRangeExprIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> { slf }

    fn __next__(&mut self) -> Option<i64> {
        if self.pos < self.values.len() {
            let v = self.values[self.pos];
            self.pos += 1;
            Some(v)
        } else {
            None
        }
    }
}
