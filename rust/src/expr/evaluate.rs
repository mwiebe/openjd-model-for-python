// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

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

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(signature = (expr, *, values=None, library=None, target_type=None, memory_limit=None, operation_limit=None, path_format=None, path_mapping_rules=None))]
pub(crate) fn evaluate_expression(
    expr: &str,
    values: Option<&Bound<'_, pyo3::PyAny>>,
    library: Option<&PyFunctionLibrary>,
    target_type: Option<&PyExprType>,
    memory_limit: Option<usize>,
    operation_limit: Option<usize>,
    path_format: Option<PyPathFormat>,
    path_mapping_rules: Option<Vec<PyPathMappingRule>>,
) -> PyResult<PyExprValue> {
    let expr_stripped = expr.trim();
    let parsed = openjd_expr::eval::ParsedExpression::new(expr_stripped).map_err(expr_err_to_py)?;

    let symtab;
    let symtab_refs: Vec<&SymbolTable> = if let Some(v) = values {
        symtab = extract_symtab(v)?;
        vec![&symtab]
    } else {
        vec![]
    };

    let lib;
    let lib_ref = match path_mapping_rules {
        Some(ref rules) if !rules.is_empty() => {
            let rust_rules: Vec<openjd_expr::path_mapping::PathMappingRule> =
                rules.iter().map(|r| r.inner.clone()).collect();
            let profile = openjd_expr::profile::ExprProfile::current()
                .with_host_context(openjd_expr::profile::HostContext::with_rules(rust_rules));
            let arc = openjd_expr::FunctionLibrary::for_profile(&profile);
            lib = (*arc).clone();
            &lib
        }
        _ => match library {
            Some(l) => { lib = l.inner.clone(); &lib }
            None => {
                let arc = openjd_expr::FunctionLibrary::for_profile(
                    &openjd_expr::profile::ExprProfile::current()
                );
                lib = (*arc).clone();
                &lib
            }
        }
    };

    let mut builder = parsed.with_library(lib_ref);
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

    let result = builder.evaluate(&symtab_refs).map_err(expr_err_to_py)?;

    Ok(PyExprValue { inner: result })
}
