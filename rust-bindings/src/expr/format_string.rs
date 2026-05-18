// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::format_string::{FormatString, FormatStringOptions};

use crate::expr::errors::expr_err_to_py;
use crate::expr::evaluate::library_for_call;
use crate::expr::expr_value::PyExprValue;
use crate::expr::function_library::PyFunctionLibrary;
use crate::expr::profile::PyExprProfile;
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

    #[pyo3(signature = (symtab, *, library=None, profile=None))]
    fn resolve_string(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        library: Option<&PyFunctionLibrary>,
        profile: Option<&PyExprProfile>,
    ) -> PyResult<String> {
        let st = extract_symtab(symtab)?;
        let lib = library_for_call(library, profile);
        let opts = FormatStringOptions::new().with_library(&lib);
        self.inner.resolve_string_with(&st, &opts).map_err(expr_err_to_py)
    }

    #[pyo3(signature = (symtab, *, library=None, profile=None))]
    fn resolve(
        &self,
        symtab: &Bound<'_, pyo3::PyAny>,
        library: Option<&PyFunctionLibrary>,
        profile: Option<&PyExprProfile>,
    ) -> PyResult<PyExprValue> {
        let st = extract_symtab(symtab)?;
        let lib = library_for_call(library, profile);
        let opts = FormatStringOptions::new().with_library(&lib);
        self.inner
            .resolve_with(&st, &opts)
            .map(|inner| PyExprValue { inner })
            .map_err(expr_err_to_py)
    }

    fn raw(&self) -> &str {
        self.inner.raw()
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
