// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3::prelude::*;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;
use openjd_expr::path_mapping::PathFormat;

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass_enum(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "PathFormat", eq, eq_int, from_py_object)]
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum PyPathFormat {
    POSIX = 0,
    WINDOWS = 1,
    URI = 2,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyPathFormat {
    #[getter]
    fn name(&self) -> &'static str {
        match self {
            PyPathFormat::POSIX => "POSIX",
            PyPathFormat::WINDOWS => "WINDOWS",
            PyPathFormat::URI => "URI",
        }
    }
}

impl From<PyPathFormat> for PathFormat {
    fn from(pf: PyPathFormat) -> Self {
        match pf {
            PyPathFormat::POSIX => PathFormat::Posix,
            PyPathFormat::WINDOWS => PathFormat::Windows,
            PyPathFormat::URI => PathFormat::Uri,
        }
    }
}

impl From<PathFormat> for PyPathFormat {
    fn from(pf: PathFormat) -> Self {
        match pf {
            PathFormat::Posix => PyPathFormat::POSIX,
            PathFormat::Windows => PyPathFormat::WINDOWS,
            PathFormat::Uri => PyPathFormat::URI,
        }
    }
}
