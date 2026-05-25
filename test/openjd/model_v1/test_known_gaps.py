# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Failing tests demonstrating known parity gaps between the
``openjd.model._v1`` Rust-backed bindings and the pure-Python reference
implementation.

Every test here is expected to *fail* against the current bindings and is
marked ``xfail``. As gaps are resolved the corresponding tests are moved
to the appropriate home in this directory (e.g. pickle tests to
``test_pickle.py``, parser shape tests to ``test_parse.py``); this file
is being driven to zero.

There are no known gaps in ``openjd.model._v1`` at the moment. New
xfail-style regression tests for newly discovered gaps belong here
until they are resolved.

Cross-reference:
    reports/model-bindings-quality-evaluation-report.md
"""
