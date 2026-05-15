// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::format_string::{FormatString, FormatStringOptions};

use crate::expr::errors::expr_err_to_py;
use crate::expr::expr_value::PyExprValue;
use crate::expr::function_library::PyFunctionLibrary;
use crate::expr::path_mapping::PyPathMappingRule;
use crate::expr::symbol_table::extract_symtab;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "FormatString", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyFormatString {
    pub(crate) inner: FormatString,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFormatString {
    #[new]
    fn new(input: &str) -> PyResult<Self> {
        FormatString::new(input)
            .map(|inner| PyFormatString { inner })
            .map_err(expr_err_to_py)
    }

    fn raw(&self) -> &str {
        self.inner.raw()
    }

    #[pyo3(signature = (symtab, library=None, path_mapping_rules=None))]
    fn resolve_string(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        library: Option<&PyFunctionLibrary>,
        path_mapping_rules: Option<Vec<PyPathMappingRule>>,
    ) -> PyResult<String> {
        let _ = path_mapping_rules; // TODO: path mapping via FormatStringOptions
        let st = extract_symtab(symtab)?;
        let mut opts = FormatStringOptions::new();
        if let Some(l) = library {
            opts = opts.with_library(&l.inner);
        }
        self.inner.resolve_string_with(&st, &opts).map_err(expr_err_to_py)
    }

    #[pyo3(signature = (symtab, library=None, path_mapping_rules=None))]
    fn resolve(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        library: Option<&PyFunctionLibrary>,
        path_mapping_rules: Option<Vec<PyPathMappingRule>>,
    ) -> PyResult<PyExprValue> {
        let _ = path_mapping_rules; // TODO: path mapping via FormatStringOptions
        let st = extract_symtab(symtab)?;
        let mut opts = FormatStringOptions::new();
        if let Some(l) = library {
            opts = opts.with_library(&l.inner);
        }
        self.inner
            .resolve_with(&st, &opts)
            .map(|inner| PyExprValue { inner })
            .map_err(expr_err_to_py)
    }

    fn has_complex_expressions(&self) -> bool {
        self.inner.has_complex_expressions()
    }

    fn expression_names(&self) -> Vec<String> {
        self.inner.expression_names().into_iter().map(|s| s.to_string()).collect()
    }

    fn is_literal(&self) -> bool {
        self.inner.is_literal()
    }

    /// Copy symbol table entries referenced by this format string's expressions
    /// from `source` into `dest`. Only copies the actual values referenced,
    /// stopping at property/method access (e.g. for `Param.Name.upper()`,
    /// copies `Param.Name` but not `Param.Name.upper`).
    fn copy_used_symtab_values(
        &self,
        source: &crate::expr::PySymbolTable,
        dest: &Bound<'_, pyo3::PyAny>,
    ) -> PyResult<()> {
        let mut dest_st: crate::expr::PySymbolTable = dest.extract()?;
        self.inner.copy_used_symtab_values(&source.inner, &mut dest_st.inner);
        // Write back — PySymbolTable is Clone, so we need to replace the Python object's inner
        // Actually, since PySymbolTable uses extract (copies), mutations won't reflect back.
        // We need a different approach: extract source, build filtered, return new SymbolTable.
        // But the API is "mutate dest in place". Let's use cell_replace on the pyclass.
        use pyo3::types::PyAnyMethods;
        let cell: &Bound<'_, crate::expr::PySymbolTable> = dest.downcast()?;
        let mut guard = cell.borrow_mut();
        self.inner.copy_used_symtab_values(&source.inner, &mut guard.inner);
        Ok(())
    }

    fn __str__(&self) -> &str {
        self.inner.raw()
    }

    fn __repr__(&self) -> String {
        format!("FormatString(\"{}\")", self.inner.raw())
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
pub(crate) fn escape_format_string(value: &str) -> String {
    openjd_expr::format_string::escape_format_string(value)
}
