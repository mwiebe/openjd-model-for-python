// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::profile::ExprProfile;
use openjd_expr::symbol_table::SymbolTable;

use crate::expr::errors::expr_err_to_py;
use crate::expr::expr_type::PyExprType;
use crate::expr::expr_value::PyExprValue;
use crate::expr::function_library::PyFunctionLibrary;
use crate::expr::path_format::PyPathFormat;
use crate::expr::profile::PyExprProfile;
use crate::expr::symbol_table::extract_symtab;

/// Resolve which `FunctionLibrary` to use for a single evaluation.
///
/// Selection rules — these mirror what `EvalBuilder` would do
/// internally if it took an `ExprProfile`:
///
/// 1. If the caller supplied a `library`, use it as-is.
/// 2. Otherwise, if the caller supplied a `profile`, fetch
///    `FunctionLibrary::for_profile(profile)` from the cache.
/// 3. Otherwise, fall back to `ExprProfile::current()` (default).
///
/// `library` and `profile` are mutually independent: `library`
/// always wins when both are given, on the principle that an
/// explicit library is the most specific input. The wrapper module's
/// docstring documents this precedence.
pub(crate) fn library_for_call(
    library: Option<&PyFunctionLibrary>,
    profile: Option<&PyExprProfile>,
) -> openjd_expr::FunctionLibrary {
    if let Some(l) = library {
        return l.inner.clone();
    }
    let p = profile
        .map(|p| p.inner.clone())
        .unwrap_or_else(ExprProfile::current);
    let arc = openjd_expr::FunctionLibrary::for_profile(&p);
    (*arc).clone()
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
#[pyo3(signature = (expr, *, values=None, library=None, profile=None, target_type=None, memory_limit=None, operation_limit=None, path_format=None))]
#[allow(clippy::too_many_arguments)] // signature mirrors the documented evaluate_expression Python API
pub(crate) fn evaluate_expression(
    expr: &str,
    values: Option<&Bound<'_, pyo3::PyAny>>,
    library: Option<&PyFunctionLibrary>,
    profile: Option<&PyExprProfile>,
    target_type: Option<&PyExprType>,
    memory_limit: Option<usize>,
    operation_limit: Option<usize>,
    path_format: Option<PyPathFormat>,
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

    let lib = library_for_call(library, profile);

    let mut builder = parsed.with_library(&lib);
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
