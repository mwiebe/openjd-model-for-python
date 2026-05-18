// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::profile::ExprProfile;
use openjd_expr::FunctionLibrary;

use crate::expr::profile::PyExprProfile;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "FunctionLibrary", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyFunctionLibrary {
    pub(crate) inner: FunctionLibrary,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFunctionLibrary {
    /// Build a library for the default profile (current revision, no
    /// extensions, no host context). Equivalent to
    /// `FunctionLibrary.for_profile(ExprProfile.current())`.
    #[new]
    fn new() -> Self {
        let lib = FunctionLibrary::for_profile(&ExprProfile::current());
        PyFunctionLibrary { inner: (*lib).clone() }
    }

    /// Build (or fetch from the per-profile cache) the library
    /// matching the given profile. The Rust crate's profile cache
    /// keys on revision + extensions + host-kind, so callers that
    /// reuse the same profile reuse the same `Arc<FunctionLibrary>`.
    #[classmethod]
    fn for_profile(_cls: &Bound<'_, PyType>, profile: &PyExprProfile) -> Self {
        let lib = FunctionLibrary::for_profile(&profile.inner);
        PyFunctionLibrary { inner: (*lib).clone() }
    }

    /// True iff this library has any host-context functions
    /// registered (today: `apply_path_mapping`).
    #[getter]
    fn host_context_enabled(&self) -> bool {
        self.inner.host_context_enabled
    }

    fn __repr__(&self) -> &'static str {
        "FunctionLibrary()"
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyfunction(module = "openjd._openjd_rs"))]
#[pyfunction]
pub(crate) fn get_default_library() -> PyFunctionLibrary {
    let lib = FunctionLibrary::for_profile(&ExprProfile::current());
    PyFunctionLibrary { inner: (*lib).clone() }
}
