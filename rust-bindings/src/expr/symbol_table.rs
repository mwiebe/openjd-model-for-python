// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use pyo3::types::PyDict;

use openjd_expr::symbol_table::SymbolTable;

use crate::expr::expr_value::{py_to_expr_value, PyExprValue};

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "SymbolTable", from_py_object)]
#[derive(Clone)]
pub(crate) struct PySymbolTable {
    pub(crate) inner: SymbolTable,
}

pub(crate) fn dict_to_symtab(dict: &Bound<'_, PyDict>) -> PyResult<SymbolTable> {
    let mut st = SymbolTable::new();
    for (key, value) in dict.iter() {
        let k: String = key.extract()?;
        if let Ok(sub_dict) = value.cast::<PyDict>() {
            let sub = dict_to_symtab(&sub_dict)?;
            st.set_table(&k, sub);
        } else if let Ok(sub_st) = value.extract::<PySymbolTable>() {
            st.set_table(&k, sub_st.inner);
        } else {
            let v = py_to_expr_value(&value)?;
            st.set(&k, v).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        }
    }
    Ok(st)
}

pub(crate) fn extract_symtab(obj: &Bound<'_, pyo3::PyAny>) -> PyResult<SymbolTable> {
    if let Ok(pst) = obj.extract::<PySymbolTable>() {
        return Ok(pst.inner);
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        return dict_to_symtab(&dict);
    }
    Err(pyo3::exceptions::PyTypeError::new_err("Expected SymbolTable or dict"))
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PySymbolTable {
    #[new]
    #[pyo3(signature = (init=None, *, source=None))]
    fn new(init: Option<&Bound<'_, pyo3::PyAny>>, source: Option<&Bound<'_, pyo3::PyAny>>) -> PyResult<Self> {
        let arg = source.or(init);
        match arg {
            None => Ok(PySymbolTable { inner: SymbolTable::new() }),
            Some(obj) => extract_symtab(obj).map(|inner| PySymbolTable { inner }),
        }
    }

    fn __contains__(&self, key: &str) -> bool {
        self.inner.contains(key)
    }

    fn __getitem__(&self, py: Python<'_>, key: &str) -> PyResult<Py<pyo3::PyAny>> {
        use pyo3::IntoPyObjectExt;
        match self.inner.get(key) {
            Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) =>
                Ok(PyExprValue { inner: v.clone() }.into_py_any(py).unwrap()),
            Some(openjd_expr::symbol_table::SymbolTableEntry::Table(t)) =>
                Ok(PySymbolTable { inner: t.clone() }.into_py_any(py).unwrap()),
            None => Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        }
    }

    fn get(&self, py: Python<'_>, name: &str) -> PyResult<Option<Py<pyo3::PyAny>>> {
        use pyo3::IntoPyObjectExt;
        match self.inner.get(name) {
            Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) =>
                Ok(Some(PyExprValue { inner: v.clone() }.into_py_any(py).unwrap())),
            Some(openjd_expr::symbol_table::SymbolTableEntry::Table(t)) =>
                Ok(Some(PySymbolTable { inner: t.clone() }.into_py_any(py).unwrap())),
            None => Ok(None),
        }
    }

    fn __setitem__(&mut self, key: &str, value: &Bound<'_, pyo3::PyAny>) -> PyResult<()> {
        let v = if let Ok(ev) = value.extract::<PyExprValue>() {
            ev.inner
        } else {
            py_to_expr_value(value)?
        };
        self.inner.set(key, v).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn keys(&self) -> std::collections::HashSet<String> {
        self.inner.keys().map(|s| s.to_string()).collect()
    }

    #[getter]
    fn symbols(&self) -> std::collections::HashSet<String> {
        self.inner.all_paths("").into_iter().collect()
    }

    #[pyo3(signature = (*others))]
    fn union(&self, others: &Bound<'_, pyo3::types::PyTuple>) -> PyResult<Self> {
        let mut result = self.inner.clone();
        for item in others.iter() {
            let other = if let Ok(st) = item.extract::<PySymbolTable>() {
                st.inner
            } else if let Ok(dict) = item.cast::<PyDict>() {
                dict_to_symtab(&dict)?
            } else {
                return Err(pyo3::exceptions::PyTypeError::new_err(
                    "union() arguments must be SymbolTable or dict",
                ));
            };
            result.merge_from(&other);
        }
        Ok(PySymbolTable { inner: result })
    }

    /// Pickle support — round-trips through a flat
    /// `dict[str, ExprValue]` of all dotted leaf paths.
    fn __reduce__<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(Bound<'py, pyo3::types::PyType>, (Bound<'py, PyDict>,))> {
        use pyo3::IntoPyObjectExt;
        let dict = PyDict::new(py);
        for path in self.inner.all_paths("") {
            if let Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) =
                self.inner.get(&path)
            {
                dict.set_item(path, PyExprValue { inner: v.clone() }.into_py_any(py)?)?;
            }
        }
        Ok((py.get_type::<Self>(), (dict,)))
    }

    /// Mirror the pure-Python reference's ``SymbolTable({...})`` repr.
    /// The dict shows each top-level key mapped to either an
    /// ``ExprValue`` (leaf) or a nested ``SymbolTable`` (subtable),
    /// recursing through nested subtables for free via Python's repr.
    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        use pyo3::IntoPyObjectExt;
        let dict = PyDict::new(py);
        // Walk top-level keys in sorted order so the repr is
        // deterministic (`HashMap` iteration order is otherwise random).
        let mut keys: Vec<&str> = self.inner.keys().collect();
        keys.sort_unstable();
        for key in keys {
            match self.inner.get(key) {
                Some(openjd_expr::symbol_table::SymbolTableEntry::Value(v)) => {
                    dict.set_item(key, PyExprValue { inner: v.clone() }.into_py_any(py)?)?;
                }
                Some(openjd_expr::symbol_table::SymbolTableEntry::Table(t)) => {
                    dict.set_item(key, PySymbolTable { inner: t.clone() }.into_py_any(py)?)?;
                }
                None => {}
            }
        }
        Ok(format!("SymbolTable({})", dict.repr()?))
    }
}
