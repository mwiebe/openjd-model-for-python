#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Regenerate the _openjd_rs.pyi type stub from Rust source.
# Requires: pyo3-stub-gen annotations on all #[pyclass]/#[pyfunction]/#[pymethods]
#
# Note: pyo3-stub-gen 0.21 has a bug with abi3-py39 (references PyEncodingWarning
# which is behind #[cfg(Py_3_10)]). We use a patched local copy at /tmp/pyo3-stub-gen.
# If not present, the script will clone and patch it automatically.
set -e

cd "$(dirname "$0")/.."

# Ensure patched pyo3-stub-gen exists
if [ ! -d /tmp/pyo3-stub-gen ]; then
    git clone --depth 1 https://github.com/Jij-Inc/pyo3-stub-gen.git /tmp/pyo3-stub-gen
    sed -i 's/^impl_exception_stub_type!(PyEncodingWarning, "EncodingWarning");/#[cfg(Py_3_10)]\nimpl_exception_stub_type!(PyEncodingWarning, "EncodingWarning");/' \
        /tmp/pyo3-stub-gen/pyo3-stub-gen/src/exception.rs
fi

PYTHON_LIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")

# Build the stub_gen binary (without extension-module so it can link against libpython)
LIBRARY_PATH="$PYTHON_LIB" cargo build --manifest-path rust-bindings/Cargo.toml --bin stub_gen

# Create a temporary pyproject.toml symlink for pyo3-stub-gen
ln -sf ../pyproject.toml rust-bindings/pyproject.toml

# Run the generator
CARGO_MANIFEST_DIR=rust-bindings LD_LIBRARY_PATH="$PYTHON_LIB" ./target/debug/stub_gen

# Move to correct location
mv rust-bindings/src/openjd/_openjd_rs/__init__.pyi src/openjd/_openjd_rs.pyi
rm -rf rust-bindings/src/openjd
rm rust-bindings/pyproject.toml

# Post-process: fix Rust raw identifiers and remove internal types
sed -i 's/r#type/type/g' src/openjd/_openjd_rs.pyi
sed -i '/"PyExprValueIter"/d; /"PyRangeExprIter"/d; /"PyStepParamSpaceIter"/d' src/openjd/_openjd_rs.pyi

# Suppress F821 false positives. pyo3-stub-gen emits forward references
# in default-value expressions (e.g. `revision: SpecificationRevision =
# SpecificationRevision.V2023_09`) which ruff flags as undefined names
# even though they resolve at runtime. Add F821 to the existing noqa
# comment so the generated stub passes lint cleanly.
sed -i 's|^# ruff: noqa: E501, F401, F403, F405$|# ruff: noqa: E501, F401, F403, F405, F821|' src/openjd/_openjd_rs.pyi

echo "Generated src/openjd/_openjd_rs.pyi"
