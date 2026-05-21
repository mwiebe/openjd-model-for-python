// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use openjd_model::ModelError;
use pyo3::prelude::*;

pyo3::create_exception!(_openjd_rs, PyDecodeValidationError, pyo3::exceptions::PyValueError);
pyo3::create_exception!(_openjd_rs, PyModelValidationError, pyo3::exceptions::PyValueError);
pyo3::create_exception!(_openjd_rs, PyUnsupportedSchema, pyo3::exceptions::PyValueError);

pub(crate) fn model_err_to_py(e: ModelError) -> PyErr {
    match e {
        ModelError::DecodeValidation(msg) => PyDecodeValidationError::new_err(msg),
        ModelError::ModelValidation(errors) => PyModelValidationError::new_err(errors.to_string()),
        ModelError::UnsupportedSchema(msg) => PyUnsupportedSchema::new_err(msg),
        ModelError::FormatStringError { message, .. } => PyModelValidationError::new_err(message),
        ModelError::Expression(expr_err) => PyModelValidationError::new_err(expr_err.to_string()),
        ModelError::Compatibility(msg) => PyModelValidationError::new_err(msg),
        _ => PyModelValidationError::new_err(e.to_string()),
    }
}
