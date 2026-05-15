// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;

pyo3::create_exception!(_openjd_rs, PyExpressionError, pyo3::exceptions::PyValueError);
pyo3::create_exception!(_openjd_rs, PyExpressionTypeError, PyExpressionError);
pyo3::create_exception!(_openjd_rs, PyRangeExprError, pyo3::exceptions::PyValueError);
pyo3::create_exception!(_openjd_rs, PyFormatStringValidationError, pyo3::exceptions::PyValueError);

pub(crate) fn expr_err_to_py(e: openjd_expr::error::ExpressionError) -> PyErr {
    PyExpressionError::new_err(e.to_string())
}
