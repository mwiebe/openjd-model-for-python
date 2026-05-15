# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Backward compatibility shim — re-exports from openjd.model.v1."""

from openjd.model.v1 import (
    Action,
    EmbeddedFile as EmbeddedFileText,
    Environment,
    EnvironmentTemplate,
    EnvironmentScript,
    FormatString,
    Job,
    JobTemplate,
    Step,
    StepScript,
    StepActions,
    StepParameterSpace,
    StepParameterSpaceIterator,
    STANDARD_AMOUNT_CAPABILITIES,
    STANDARD_ATTRIBUTE_CAPABILITIES,
)

RangeExpressionTaskParameterDefinition = dict
RangeListTaskParameterDefinition = dict

# Aliases matching old Pydantic model names
CommandString = FormatString
ArgString = FormatString
DataString = FormatString
EmbeddedFiles = list


class EmbeddedFileTypes:
    TEXT = "TEXT"


class ExtensionName:
    TASK_CHUNKING = "TASK_CHUNKING"
    REDACTED_ENV_VARS = "REDACTED_ENV_VARS"
    EXPR = "EXPR"
    FEATURE_BUNDLE_1 = "FEATURE_BUNDLE_1"

    def __iter__(self):
        return iter([self.TASK_CHUNKING, self.REDACTED_ENV_VARS, self.EXPR, self.FEATURE_BUNDLE_1])
