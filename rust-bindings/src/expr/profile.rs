// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

//! Python bindings for `openjd_expr::profile` — `ExprRevision`,
//! `ExprExtension`, `HostContext`, and `ExprProfile`.
//!
//! These are the canonical inputs to `FunctionLibrary.for_profile(...)`
//! and to every entry point that needs an evaluation context. They
//! replace the earlier ad-hoc `with_host_context()` /
//! `with_unresolved_host_context()` shortcuts and the per-call
//! `path_mapping_rules=` kwarg.
//!
//! The shape mirrors the Rust crate one-to-one so users porting code
//! between Python and Rust see the same names and the same builder
//! pattern.

use std::collections::HashSet;
use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyType;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

use openjd_expr::profile::{ExprExtension, ExprProfile, ExprRevision, HostContext};

use crate::expr::path_mapping::PyPathMappingRule;

// ── ExprRevision ───────────────────────────────────────────────────

/// Expression-language specification revision.
///
/// Mirrors `openjd_expr::ExprRevision`. Marked `#[non_exhaustive]`
/// in Rust so future revisions can be added without a SemVer break;
/// the Python enum has the same growth path — new variants will be
/// added here as the spec adds them.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass_enum(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ExprRevision", eq, eq_int, hash, frozen, from_py_object)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub(crate) enum PyExprRevision {
    V2026_02 = 0,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyExprRevision {
    /// The current revision. Tracks `ExprRevision::CURRENT` in the
    /// underlying Rust crate; will roll forward as new revisions ship.
    #[classattr]
    const CURRENT: PyExprRevision = PyExprRevision::V2026_02;

    fn __repr__(&self) -> &'static str {
        match self {
            PyExprRevision::V2026_02 => "ExprRevision.V2026_02",
        }
    }

    /// Spec-form revision string, e.g. `"2026-02"`.
    fn __str__(&self) -> &'static str {
        match self {
            PyExprRevision::V2026_02 => "2026-02",
        }
    }
}

impl From<PyExprRevision> for ExprRevision {
    fn from(r: PyExprRevision) -> Self {
        match r {
            PyExprRevision::V2026_02 => ExprRevision::V2026_02,
        }
    }
}

impl From<ExprRevision> for PyExprRevision {
    fn from(r: ExprRevision) -> Self {
        match r {
            ExprRevision::V2026_02 => PyExprRevision::V2026_02,
            // ExprRevision is #[non_exhaustive]; future variants need to
            // map here. Until then `match` is exhaustive on known variants.
            #[allow(unreachable_patterns)]
            _ => PyExprRevision::V2026_02,
        }
    }
}

// ── ExprExtension ──────────────────────────────────────────────────

/// Expression-language extensions.
///
/// `openjd_expr::ExprExtension` is empty-but-`#[non_exhaustive]`
/// today — no expression-level extensions exist yet. The Python
/// binding cannot represent an empty enum, so we use a thin wrapper
/// class whose only purpose is to carry zero or more named variants
/// once they exist. Today it has no constructors.
///
/// When the first `ExprExtension` variant lands in the Rust crate,
/// add a matching `#[classattr]` here (e.g. `Foo: PyExprExtension`)
/// and a corresponding arm in `From<PyExprExtension>` /
/// `From<ExprExtension>`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ExprExtension", eq, hash, frozen, from_py_object)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub(crate) struct PyExprExtension {
    // Zero-sized today. Discriminant field reserved for when the
    // upstream enum gains variants; until then the type has exactly
    // one possible value (which Python cannot construct).
    _variant: u8,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyExprExtension {
    /// All extension variants, in a stable order. Empty today.
    #[classattr]
    #[allow(non_snake_case)] // Python class-constant naming convention
    fn ALL() -> Vec<PyExprExtension> {
        ExprExtension::ALL
            .iter()
            .copied()
            .map(PyExprExtension::from)
            .collect()
    }

    fn __repr__(&self) -> &'static str {
        // Unreachable while ExprExtension has no variants. When variants
        // are added, dispatch on `self._variant` here.
        "ExprExtension(<unknown>)"
    }
}

impl From<PyExprExtension> for ExprExtension {
    fn from(_: PyExprExtension) -> Self {
        // Unreachable while ExprExtension has no variants. The Python
        // type cannot be constructed today, so this conversion is
        // unreachable in practice.
        unreachable!("ExprExtension has no variants in this crate version")
    }
}

impl From<ExprExtension> for PyExprExtension {
    fn from(_: ExprExtension) -> Self {
        // Unreachable while ExprExtension has no variants.
        unreachable!("ExprExtension has no variants in this crate version")
    }
}

// ── HostContext ────────────────────────────────────────────────────

/// Host-context state available to expression evaluation.
///
/// Three states, mirroring `openjd_expr::HostContext`:
///
/// - [`none()`](Self::none) — no host-context functions registered.
/// - [`unresolved()`](Self::unresolved) — host-context signatures
///   registered with stub implementations that return
///   `Unresolved(T)`. Use at template-validation time when real
///   host state is not yet available but signatures must be known
///   for type checking.
/// - [`with_rules(rules)`](Self::with_rules) — real implementations
///   with path-mapping rules registered. Use at runtime.
///
/// Constructed via class methods to keep the three states distinct
/// at the Python call site; there is no public `__init__` because
/// "default-constructed `HostContext`" is ambiguous (is it `None` or
/// a `WithRules` of an empty list?). The Rust crate makes the choice
/// explicit; the Python binding does the same.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "HostContext", frozen, from_py_object)]
#[derive(Clone)]
pub(crate) struct PyHostContext {
    pub(crate) inner: HostContext,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyHostContext {
    /// No host-context functions are registered. Default state.
    #[classmethod]
    fn none(_cls: &Bound<'_, PyType>) -> Self {
        Self { inner: HostContext::None }
    }

    /// Host-context function signatures registered with stub
    /// implementations that return `Unresolved(T)`. Use at
    /// template-validation time.
    #[classmethod]
    fn unresolved(_cls: &Bound<'_, PyType>) -> Self {
        Self { inner: HostContext::Unresolved }
    }

    /// Host-context functions registered with implementations that
    /// use the supplied path mapping rules. Use at runtime.
    ///
    /// `rules` may be empty — that still constructs a `WithRules`
    /// host context (`apply_path_mapping` is registered, returns
    /// the path unchanged). Passing zero rules is *not* the same as
    /// passing no host context at all.
    #[classmethod]
    fn with_rules(_cls: &Bound<'_, PyType>, rules: Vec<PyPathMappingRule>) -> Self {
        let rust_rules: Vec<openjd_expr::path_mapping::PathMappingRule> =
            rules.into_iter().map(|r| r.inner).collect();
        Self {
            inner: HostContext::WithRules(Arc::new(rust_rules)),
        }
    }

    /// Whether this host context registers any host-context
    /// functions (i.e. is *not* `None`).
    fn is_enabled(&self) -> bool {
        self.inner.is_enabled()
    }

    /// Whether this host context uses unresolved stub
    /// implementations.
    fn is_unresolved(&self) -> bool {
        self.inner.is_unresolved()
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            HostContext::None => "HostContext.none()".to_string(),
            HostContext::Unresolved => "HostContext.unresolved()".to_string(),
            HostContext::WithRules(rules) => {
                format!("HostContext.with_rules(<{} rule(s)>)", rules.len())
            }
        }
    }
}

// ── ExprProfile ────────────────────────────────────────────────────

/// A complete expression profile: revision, enabled extensions, and
/// host context.
///
/// Mirrors `openjd_expr::ExprProfile`. Pass to
/// [`FunctionLibrary.for_profile(profile)`](crate::expr::PyFunctionLibrary)
/// and to entry points like `evaluate_expression(..., profile=...)`,
/// `ParsedExpression.evaluate(..., profile=...)`,
/// `FormatString.resolve(..., profile=...)`,
/// `FormatString.resolve_string(..., profile=...)`.
#[cfg_attr(feature = "stub-gen", gen_stub_pyclass(module = "openjd._openjd_rs"))]
#[pyclass(module = "openjd.expr", name = "ExprProfile", frozen, from_py_object)]
#[derive(Clone)]
pub(crate) struct PyExprProfile {
    pub(crate) inner: ExprProfile,
}

#[cfg_attr(feature = "stub-gen", gen_stub_pymethods)]
#[pymethods]
impl PyExprProfile {
    /// Build a profile for the given revision with no extensions and
    /// no host context.
    ///
    /// Default arguments mirror `ExprProfile::current()` if `revision`
    /// is omitted: current revision, no extensions, no host context.
    #[new]
    #[pyo3(signature = (revision=None, *, extensions=None, host_context=None))]
    fn new(
        revision: Option<PyExprRevision>,
        extensions: Option<Vec<PyExprExtension>>,
        host_context: Option<PyHostContext>,
    ) -> Self {
        let rev: ExprRevision = revision
            .map(Into::into)
            .unwrap_or(ExprRevision::CURRENT);
        let mut profile = ExprProfile::new(rev);
        if let Some(exts) = extensions {
            let set: HashSet<ExprExtension> = exts.into_iter().map(Into::into).collect();
            profile = profile.with_extensions(set);
        }
        if let Some(host) = host_context {
            profile = profile.with_host_context(host.inner);
        }
        Self { inner: profile }
    }

    /// Shortcut for `ExprProfile()` with the current revision, no
    /// extensions, and no host context.
    #[classmethod]
    fn current(_cls: &Bound<'_, PyType>) -> Self {
        Self { inner: ExprProfile::current() }
    }

    /// Build a profile with the latest revision and every known
    /// expression extension enabled.
    ///
    /// **Intentionally unstable across crate versions.** As new
    /// extensions are added to `ExprExtension::ALL` and new revisions
    /// land at `ExprRevision::CURRENT`, the set of accepted syntax,
    /// functions, and types grows. For parse behavior that is stable
    /// across crate versions, construct an explicit profile via
    /// `ExprProfile(revision=...)` instead.
    #[classmethod]
    fn latest(_cls: &Bound<'_, PyType>) -> Self {
        Self { inner: ExprProfile::latest() }
    }

    /// Builder: return a new profile with the given extensions
    /// (replaces any existing set). Does not mutate `self`.
    fn with_extensions(&self, extensions: Vec<PyExprExtension>) -> Self {
        let set: HashSet<ExprExtension> = extensions.into_iter().map(Into::into).collect();
        Self { inner: self.inner.clone().with_extensions(set) }
    }

    /// Builder: return a new profile with the given host context.
    /// Does not mutate `self`.
    fn with_host_context(&self, host_context: PyHostContext) -> Self {
        Self {
            inner: self.inner.clone().with_host_context(host_context.inner),
        }
    }

    /// The specification revision this profile targets.
    #[getter]
    fn revision(&self) -> PyExprRevision {
        self.inner.revision().into()
    }

    /// The set of enabled extensions, as a frozenset-compatible list.
    #[getter]
    fn extensions(&self) -> Vec<PyExprExtension> {
        self.inner.extensions().iter().copied().map(Into::into).collect()
    }

    /// The host context.
    #[getter]
    fn host_context(&self) -> PyHostContext {
        PyHostContext { inner: self.inner.host_context().clone() }
    }

    /// Whether the given extension is enabled in this profile.
    fn has_extension(&self, ext: PyExprExtension) -> bool {
        self.inner.has_extension(ext.into())
    }

    fn __repr__(&self) -> String {
        let host = match self.inner.host_context() {
            HostContext::None => "none",
            HostContext::Unresolved => "unresolved",
            HostContext::WithRules(_) => "with_rules",
        };
        format!(
            "ExprProfile(revision={}, extensions=<{} ext(s)>, host_context=<{}>)",
            match self.inner.revision() {
                ExprRevision::V2026_02 => "V2026_02",
                #[allow(unreachable_patterns)]
                _ => "<unknown>",
            },
            self.inner.extensions().len(),
            host,
        )
    }
}

impl Default for PyExprProfile {
    fn default() -> Self {
        Self { inner: ExprProfile::current() }
    }
}
