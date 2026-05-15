// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use std::sync::atomic::{AtomicUsize, Ordering};

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::symbol_table::SymbolTable;

use crate::expr::errors::expr_err_to_py;
use crate::expr::expr_type::PyExprType;
use crate::expr::expr_value::PyExprValue;
use crate::expr::function_library::PyFunctionLibrary;
use crate::expr::path_format::PyPathFormat;
use crate::expr::path_mapping::PyPathMappingRule;
use crate::expr::symbol_table::extract_symtab;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ParsedExpression")]
pub(crate) struct PyParsedExpression {
    inner: openjd_expr::eval::ParsedExpression,
    last_peak_memory: AtomicUsize,
    last_operation_count: AtomicUsize,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyParsedExpression {
    fn __repr__(&self) -> String {
        format!("ParsedExpression(\"{}\")", self.inner.expression())
    }

    #[getter]
    fn accessed_symbols(&self) -> std::collections::HashSet<String> {
        self.inner.accessed_symbols().clone()
    }

    #[getter]
    fn called_functions(&self) -> std::collections::HashSet<String> {
        self.inner.called_functions().clone()
    }

    #[getter]
    fn local_bindings(&self) -> std::collections::HashSet<String> {
        self.inner.local_bindings().clone()
    }

    #[getter]
    fn expr(&self) -> &str {
        self.inner.expression()
    }

    #[pyo3(signature = (*, values=None, library=None, target_type=None, path_format=None, memory_limit=None, operation_limit=None, path_mapping_rules=None))]
    fn evaluate(
        &self,
        values: Option<&Bound<'_, pyo3::PyAny>>,
        library: Option<&PyFunctionLibrary>,
        target_type: Option<&PyExprType>,
        path_format: Option<PyPathFormat>,
        memory_limit: Option<usize>,
        operation_limit: Option<usize>,
        path_mapping_rules: Option<Vec<PyPathMappingRule>>,
    ) -> PyResult<PyExprValue> {
        let symtab;
        let symtab_refs: Vec<&SymbolTable> = if let Some(v) = values {
            symtab = extract_symtab(v)?;
            vec![&symtab]
        } else {
            vec![]
        };

        let lib;
        let mut builder = match library {
            Some(l) => {
                lib = l.inner.clone();
                self.inner.with_library(&lib)
            }
            None => {
                let arc = openjd_expr::FunctionLibrary::for_profile(
                    &openjd_expr::profile::ExprProfile::current()
                );
                lib = (*arc).clone();
                self.inner.with_library(&lib)
            }
        };

        if let Some(ml) = memory_limit {
            builder = builder.with_memory_limit(ml);
        }
        if let Some(ol) = operation_limit {
            builder = builder.with_operation_limit(ol);
        }
        if let Some(pf) = path_format {
            builder = builder.with_path_format(pf.into());
        }
        if let Some(tt) = target_type {
            builder = builder.with_target_type(&tt.inner);
        }

        let _ = path_mapping_rules; // TODO: path mapping rules on EvalBuilder

        let result = builder.evaluate_with_metrics(&symtab_refs).map_err(expr_err_to_py)?;
        self.last_peak_memory.store(result.peak_memory, Ordering::Relaxed);
        self.last_operation_count.store(result.operation_count, Ordering::Relaxed);
        Ok(PyExprValue { inner: result.value })
    }

    #[getter]
    fn peak_memory_usage(&self) -> PyResult<usize> {
        Ok(self.last_peak_memory.load(Ordering::Relaxed))
    }

    #[getter]
    fn operation_count(&self) -> PyResult<usize> {
        Ok(self.last_operation_count.load(Ordering::Relaxed))
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
pub(crate) fn parse_expression(expr: &str) -> PyResult<PyParsedExpression> {
    openjd_expr::eval::ParsedExpression::new(expr)
        .map(|inner| PyParsedExpression {
            inner,
            last_peak_memory: AtomicUsize::new(0),
            last_operation_count: AtomicUsize::new(0),
        })
        .map_err(expr_err_to_py)
}
