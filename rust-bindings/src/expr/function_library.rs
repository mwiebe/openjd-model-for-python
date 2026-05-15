// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::profile::{ExprProfile, HostContext};
use openjd_expr::FunctionLibrary;

use crate::expr::path_mapping::PyPathMappingRule;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "FunctionLibrary", from_py_object)]
#[derive(Clone)]
pub(crate) struct PyFunctionLibrary {
    pub(crate) inner: FunctionLibrary,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyFunctionLibrary {
    #[new]
    fn new() -> Self {
        let lib = FunctionLibrary::for_profile(&ExprProfile::current());
        PyFunctionLibrary { inner: (*lib).clone() }
    }

    #[getter]
    fn host_context_enabled(&self) -> bool {
        self.inner.host_context_enabled
    }

    #[pyo3(signature = (path_mapping_rules=None))]
    fn with_host_context(&self, path_mapping_rules: Option<Vec<PyPathMappingRule>>) -> Self {
        let rules: Vec<openjd_expr::path_mapping::PathMappingRule> = path_mapping_rules
            .unwrap_or_default()
            .into_iter()
            .map(|r| r.inner)
            .collect();
        let host_ctx = if rules.is_empty() {
            HostContext::WithRules(std::sync::Arc::new(Vec::new()))
        } else {
            HostContext::with_rules(rules)
        };
        let profile = ExprProfile::current().with_host_context(host_ctx);
        let lib = FunctionLibrary::for_profile(&profile);
        PyFunctionLibrary { inner: (*lib).clone() }
    }

    fn with_unresolved_host_context(&self) -> Self {
        let profile = ExprProfile::current().with_host_context(HostContext::Unresolved);
        let lib = FunctionLibrary::for_profile(&profile);
        PyFunctionLibrary { inner: (*lib).clone() }
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
