# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Per-Step Environment statuses through the Rust-backed ``openjd.model._v1``
(openjd-rs-ep f19a035e, spec eaa5d1d).

``CreatedJob.environment_statuses`` has one ``StepEnvironmentStatuses`` per
Step: every Environment the Step considered, in the Job's Environment order
(attached, then ``jobEnvironments``, then the Step's ``stepEnvironments``),
each with its document, scope (``EnvironmentScope``) and status
(``EnvironmentStatus``): ``ENTERED``, ``DECLINED`` (a ``BY_DEFAULT``
Environment a disabled ``environment:`` entry declines), ``DISABLED`` (its
``enableIf`` is false for the Step) or ``SUPERSEDED`` (an earlier member of its
``exclusiveGroup`` is entered; its ``enableIf`` is not evaluated). The Step's
enabled ``required: false`` entries that named no Environment are in
``not_found``.

Every test checks the same invariants against the older views of a created
Job (``_check_invariants``).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Optional

import pytest
import yaml  # type: ignore[import-untyped]

from openjd.model._v1 import (
    create_job,
    create_job_with_environment_templates,
    decode_environment_template,
    decode_job_template,
)
from openjd.model._v1.job import (
    CreatedJob,
    Document,
    EnvironmentRef,
    EnvironmentScope,
    EnvironmentStatus,
    OptionalEntryNotFound,
    StepEnvironmentStatus,
    StepEnvironmentStatuses,
)

_EXTS = ["ENV_PARAMS", "EXPR"]
_ALL_EXTS = ["TASK_CHUNKING", "REDACTED_ENV_VARS", "FEATURE_BUNDLE_1", "EXPR", "WRAP_ACTIONS"] + [
    "ENV_PARAMS"
]
_COPIES = Path(__file__).parent / "env_params_conformance"
_ECHO = {"actions": {"onRun": {"command": "echo"}}}
_JOB = Document.job_template()
_QUEUE = Document.environment_template(0, "queue")

ENTERED = EnvironmentStatus.ENTERED
DECLINED = EnvironmentStatus.DECLINED
DISABLED = EnvironmentStatus.DISABLED
SUPERSEDED = EnvironmentStatus.SUPERSEDED
ATTACHED = EnvironmentScope.ATTACHED
JOB = EnvironmentScope.JOB
STEP = EnvironmentScope.STEP


def _env(name: str, **fields: Any) -> dict[str, Any]:
    return {"name": name, "variables": {"V": name}, **fields}


def _job_template(
    envs: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    params: Optional[list[dict[str, Any]]] = None,
    extensions: Optional[list[str]] = _EXTS,
) -> Any:
    template: dict[str, Any] = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "J",
        "steps": steps,
    }
    if extensions is not None:
        template["extensions"] = extensions
    if envs:
        template["jobEnvironments"] = envs
    if params:
        template["parameterDefinitions"] = params
    return decode_job_template(template=template, supported_extensions=_EXTS)


def _env_template(name: str, **fields: Any) -> Any:
    return decode_environment_template(
        template={
            "specificationVersion": "environment-2023-09",
            "extensions": _EXTS,
            "environment": _env(name, **fields),
        },
        supported_extensions=_EXTS,
    )


def _rows(created: CreatedJob, step: int) -> list[tuple[str, Document, EnvironmentScope, Any]]:
    return [
        (e.name, e.document, e.scope, e.status)
        for e in created.environment_statuses[step].environments
    ]


def _check_invariants(created: CreatedJob) -> None:
    """The statuses agree with ``Step.environments``, ``step_environments``,
    ``disabled_environments`` and ``environment_documents``."""
    job = created.job
    assert len(created.environment_statuses) == len(job.steps)
    assert len(created.disabled_environments) == len(job.steps)
    attached_docs = {d for d in created.environment_documents if not d.is_job_template}
    for step, statuses, disabled in zip(
        job.steps, created.environment_statuses, created.disabled_environments
    ):
        items = statuses.environments
        for e in items:
            assert (e.scope == ATTACHED) == (not e.document.is_job_template)
            if e.scope == ATTACHED:
                assert e.document in attached_docs
        job_items = [e for e in items if e.scope != STEP]
        step_items = [e for e in items if e.scope == STEP]
        # Scopes come in the Job's Environment order.
        scopes = [e.scope for e in items]
        assert scopes == sorted(scopes, key=lambda s: [ATTACHED, JOB, STEP].index(s))
        # Entered Job Environments are the ones the Step's Sessions enter.
        entered = [
            EnvironmentRef(document=e.document, environment=e.name)
            for e in job_items
            if e.status == ENTERED
        ]
        for e in job_items:
            assert step.enters_environment(e.name, e.document) == (e.status == ENTERED)
        if step.environments is not None:
            assert step.environments == entered
        # Entered Step Environments are the Step's step_environments.
        assert [s.name for s in step.step_environments or []] == [
            e.name for e in step_items if e.status == ENTERED
        ]
        # disabled_environments is the DISABLED and SUPERSEDED items.
        assert disabled.environments == [
            EnvironmentRef(document=e.document, environment=e.name)
            for e in job_items
            if e.status in (DISABLED, SUPERSEDED)
        ]
        assert disabled.step_environments == [
            e.name for e in step_items if e.status in (DISABLED, SUPERSEDED)
        ]


def _create(
    jt: Any, attached: Optional[list[Any]] = None, values: Optional[dict[str, Any]] = None
) -> CreatedJob:
    created = create_job_with_environment_templates(
        job_template=jt, job_parameter_values=values or {}, environment_templates=attached
    )
    _check_invariants(created)
    return created


def _not_found(created: CreatedJob, step: int) -> list[tuple[int, str]]:
    return [
        (n.dependency_index, n.environment) for n in created.environment_statuses[step].not_found
    ]


class TestEnums:
    @pytest.mark.parametrize(
        "member, name",
        [
            (EnvironmentStatus.ENTERED, "ENTERED"),
            (EnvironmentStatus.DECLINED, "DECLINED"),
            (EnvironmentStatus.DISABLED, "DISABLED"),
            (EnvironmentStatus.SUPERSEDED, "SUPERSEDED"),
            (EnvironmentScope.ATTACHED, "ATTACHED"),
            (EnvironmentScope.JOB, "JOB"),
            (EnvironmentScope.STEP, "STEP"),
        ],
    )
    def test_name_repr_pickle(self, member: Any, name: str) -> None:
        assert member.name == name
        assert repr(member) == f"{type(member).__name__}.{name}"
        restored = pickle.loads(pickle.dumps(member))
        assert restored == member and restored is member
        assert hash(restored) == hash(member)

    def test_members_are_distinct(self) -> None:
        statuses = [ENTERED, DECLINED, DISABLED, SUPERSEDED]
        scopes = [ATTACHED, JOB, STEP]
        assert len(set(statuses)) == 4
        assert len(set(scopes)) == 3
        assert ENTERED != DECLINED and DISABLED != SUPERSEDED and JOB != STEP

    def test_module(self) -> None:
        assert EnvironmentStatus.__module__ == "openjd.model._v1.job"
        assert EnvironmentScope.__module__ == "openjd.model._v1.job"


class TestJobEnvironments:
    """Job Templates with nothing attached (the ``create_job`` route)."""

    def test_each_status(self) -> None:
        jt = _job_template(
            [
                _env("Always", activation="ALWAYS"),
                _env("Declined"),
                _env("Disabled", enableIf=False),
                _env("First", exclusiveGroup="G"),
                # Superseded, not disabled: its enableIf is not evaluated.
                _env("Second", exclusiveGroup="G", enableIf=False),
                _env("Requested", activation="ON_REQUEST"),
                _env("Unrequested", activation="ON_REQUEST"),
            ],
            [
                {
                    "name": "S",
                    "dependencies": [
                        {"environment": "Declined", "enableIf": False},
                        {"environment": "Requested"},
                    ],
                    "stepEnvironments": [_env("Own"), _env("OwnOff", enableIf=False)],
                    "script": _ECHO,
                }
            ],
        )
        created = _create(jt)
        assert _rows(created, 0) == [
            ("Always", _JOB, JOB, ENTERED),
            ("Declined", _JOB, JOB, DECLINED),
            ("Disabled", _JOB, JOB, DISABLED),
            ("First", _JOB, JOB, ENTERED),
            ("Second", _JOB, JOB, SUPERSEDED),
            ("Requested", _JOB, JOB, ENTERED),
            ("Own", _JOB, STEP, ENTERED),
            ("OwnOff", _JOB, STEP, DISABLED),
        ]
        assert created.environment_statuses[0].not_found == []
        # create_job builds the same Job.
        job = create_job(job_template=jt, job_parameter_values={})
        assert job.steps[0].environments == created.job.steps[0].environments

    def test_statuses_are_per_step(self) -> None:
        jt = _job_template(
            [
                _env("Lic", enableIf="Param.Lic"),
                _env("A", exclusiveGroup="G", enableIf="Param.UseA"),
                _env("B", exclusiveGroup="G"),
            ],
            [
                {"name": "One", "script": _ECHO},
                {
                    "name": "Two",
                    "dependencies": [{"environment": "Lic", "enableIf": False}],
                    "script": _ECHO,
                },
            ],
            params=[
                {"name": "Lic", "type": "BOOL", "default": True},
                {"name": "UseA", "type": "BOOL", "default": False},
            ],
        )
        created = _create(jt)
        # UseA is false: A is disabled and B, the next member, is entered.
        assert _rows(created, 0) == [
            ("Lic", _JOB, JOB, ENTERED),
            ("A", _JOB, JOB, DISABLED),
            ("B", _JOB, JOB, ENTERED),
        ]
        assert _rows(created, 1) == [
            ("Lic", _JOB, JOB, DECLINED),
            ("A", _JOB, JOB, DISABLED),
            ("B", _JOB, JOB, ENTERED),
        ]
        created = _create(jt, values={"UseA": True})
        assert [r[3] for r in _rows(created, 0)] == [ENTERED, ENTERED, SUPERSEDED]

    def test_a_superseded_member_with_an_unresolved_enable_if(self) -> None:
        # B's enableIf reads a parameter no Step supplies; it is never
        # evaluated because A is entered (spec JB-154).
        jt = _job_template(
            [
                _env("A", exclusiveGroup="G"),
                _env(
                    "B",
                    exclusiveGroup="G",
                    envParameterDefinitions=[{"name": "On", "type": "BOOL"}],
                    enableIf="Env.Param.On",
                ),
            ],
            [{"name": "S", "script": _ECHO}],
        )
        assert _rows(_create(jt), 0) == [
            ("A", _JOB, JOB, ENTERED),
            ("B", _JOB, JOB, SUPERSEDED),
        ]

    def test_optional_entry_that_names_nothing(self) -> None:
        jt = _job_template(
            [_env("Lic")],
            [
                {
                    "name": "S",
                    "dependencies": [
                        {"environment": "Lic"},
                        {"environment": "Nope", "required": False},
                        # A disabled entry that names nothing has no effect.
                        {"environment": "Gone", "required": False, "enableIf": False},
                    ],
                    "script": _ECHO,
                }
            ],
        )
        created = _create(jt)
        assert _not_found(created, 0) == [(1, "Nope")]
        assert _rows(created, 0) == [("Lic", _JOB, JOB, ENTERED)]
        assert created.warnings == [
            "steps[0] -> dependencies[1] -> environment: names Environment 'Nope', which is not "
            "a jobEnvironments entry of the Job Template, and no Environment Template is "
            "attached. The entry has 'required: false', so it has no effect."
        ]

    def test_a_step_without_environments(self) -> None:
        jt = _job_template([], [{"name": "S", "script": _ECHO}])
        created = _create(jt)
        assert created.environment_statuses[0].environments == []
        assert created.environment_statuses[0].not_found == []


class TestAttachedEnvironments:
    """The ``create_job_with_environment_templates`` route with attachments."""

    def test_group_spanning_an_attachment_and_a_job_environment(self) -> None:
        # The attached Conda comes first in the Job's Environment order, so
        # it supersedes the Job Template's Docker, whose required Image no
        # Step supplies.
        jt = _job_template(
            [
                _env(
                    "Docker",
                    exclusiveGroup="Soft",
                    envParameterDefinitions=[{"name": "Image", "type": "STRING"}],
                ),
            ],
            [{"name": "S", "script": _ECHO}],
        )
        conda = _env_template("Conda", exclusiveGroup="Soft")
        created = _create(jt, [(conda, "queue")])
        assert _rows(created, 0) == [
            ("Conda", _QUEUE, ATTACHED, ENTERED),
            ("Docker", _JOB, JOB, SUPERSEDED),
        ]

    def test_a_disabled_attachment_lets_the_job_environment_in(self) -> None:
        jt = _job_template(
            [
                _env(
                    "Docker",
                    exclusiveGroup="Soft",
                    envParameterDefinitions=[{"name": "Image", "type": "STRING"}],
                )
            ],
            [
                {
                    "name": "UseConda",
                    "dependencies": [{"environment": "Docker", "parameters": {"Image": "i"}}],
                    "script": _ECHO,
                },
                {
                    "name": "UseDocker",
                    "dependencies": [
                        {"environment": "Conda", "parameters": {"On": False}},
                        {"environment": "Docker", "parameters": {"Image": "i"}},
                    ],
                    "script": _ECHO,
                },
            ],
        )
        conda = _env_template(
            "Conda",
            exclusiveGroup="Soft",
            envParameterDefinitions=[{"name": "On", "type": "BOOL", "default": True}],
            enableIf="Env.Param.On",
        )
        created = _create(jt, [(conda, "queue")])
        assert _rows(created, 0) == [
            ("Conda", _QUEUE, ATTACHED, ENTERED),
            ("Docker", _JOB, JOB, SUPERSEDED),
        ]
        assert _rows(created, 1) == [
            ("Conda", _QUEUE, ATTACHED, DISABLED),
            ("Docker", _JOB, JOB, ENTERED),
        ]

    def test_each_activation_of_an_attachment(self) -> None:
        jt = _job_template(
            [_env("Job")],
            [
                {
                    "name": "S",
                    "dependencies": [
                        {"environment": "ByDefault", "enableIf": False},
                        {"environment": "Requested"},
                        {"environment": "Missing", "required": False},
                    ],
                    "script": _ECHO,
                },
                {"name": "T", "script": _ECHO},
            ],
        )
        attached = [
            (_env_template("Always", activation="ALWAYS"), "a"),
            (_env_template("ByDefault"), "b"),
            (_env_template("Requested", activation="ON_REQUEST"), "c"),
            _env_template("Off", enableIf=False),
        ]
        created = _create(jt, attached)
        a, b, c = (Document.environment_template(i, label) for i, label in enumerate("abc"))
        off = Document.environment_template(3)
        assert _rows(created, 0) == [
            ("Always", a, ATTACHED, ENTERED),
            ("ByDefault", b, ATTACHED, DECLINED),
            ("Requested", c, ATTACHED, ENTERED),
            ("Off", off, ATTACHED, DISABLED),
            ("Job", _JOB, JOB, ENTERED),
        ]
        # T requests nothing: the ON_REQUEST attachment is not listed.
        assert _rows(created, 1) == [
            ("Always", a, ATTACHED, ENTERED),
            ("ByDefault", b, ATTACHED, ENTERED),
            ("Off", off, ATTACHED, DISABLED),
            ("Job", _JOB, JOB, ENTERED),
        ]
        assert _not_found(created, 0) == [(2, "Missing")]
        assert created.environment_statuses[1].not_found == []

    @pytest.mark.parametrize(
        "name",
        [
            "4--exclusive-group-superseded-not-held-to-constraint-7.test.yaml",
            "4--exclusive-group-superseded-enable-if-not-evaluated.test.yaml",
        ],
    )
    def test_conformance_copies_attached(self, name: str) -> None:
        test = yaml.safe_load((_COPIES / name).read_text())
        jt = decode_job_template(template=test["template"], supported_extensions=_ALL_EXTS)
        envs = [
            decode_environment_template(template=e, supported_extensions=_ALL_EXTS)
            for e in test.get("environments", [])
        ]
        created = _create(jt, envs, dict(test.get("parameters", {})))
        rows = _rows(created, 0)
        assert rows[:2] == [
            ("Conda", Document.environment_template(0), ATTACHED, ENTERED),
            ("Docker", Document.environment_template(1), ATTACHED, SUPERSEDED),
        ]


class TestWithoutEnvParams:
    def test_every_environment_is_entered(self) -> None:
        jt = _job_template(
            [_env("A"), _env("B")],
            [{"name": "S", "stepEnvironments": [_env("Own")], "script": _ECHO}],
            extensions=None,
        )
        created = _create(jt)
        assert _rows(created, 0) == [
            ("A", _JOB, JOB, ENTERED),
            ("B", _JOB, JOB, ENTERED),
            ("Own", _JOB, STEP, ENTERED),
        ]

    def test_an_attached_env_params_template_can_still_be_left_out(self) -> None:
        jt = _job_template([_env("Job")], [{"name": "S", "script": _ECHO}], extensions=None)
        first = _env_template("First", exclusiveGroup="G")
        second = _env_template("Second", exclusiveGroup="G")
        off = _env_template("Off", enableIf=False)
        created = _create(jt, [first, second, off])
        assert [r[3] for r in _rows(created, 0)] == [ENTERED, SUPERSEDED, DISABLED, ENTERED]


class TestItemTypes:
    def _created(self) -> CreatedJob:
        jt = _job_template(
            [_env("A"), _env("B", enableIf=False)],
            [
                {
                    "name": "S",
                    "dependencies": [{"environment": "Nope", "required": False}],
                    "script": _ECHO,
                }
            ],
        )
        return _create(jt)

    def test_status_attributes_and_repr(self) -> None:
        item = self._created().environment_statuses[0].environments[1]
        assert isinstance(item, StepEnvironmentStatus)
        assert item.name == "B"
        assert item.document == _JOB
        assert item.scope == JOB
        assert item.status == DISABLED
        assert repr(item) == (
            'StepEnvironmentStatus(name="B", document=Document.job_template(), '
            "scope=EnvironmentScope.JOB, status=EnvironmentStatus.DISABLED)"
        )

    def test_not_found_attributes_and_repr(self) -> None:
        (item,) = self._created().environment_statuses[0].not_found
        assert isinstance(item, OptionalEntryNotFound)
        assert item.dependency_index == 0
        assert item.environment == "Nope"
        assert repr(item) == 'OptionalEntryNotFound(dependency_index=0, environment="Nope")'

    def test_statuses_repr(self) -> None:
        statuses = self._created().environment_statuses[0]
        assert isinstance(statuses, StepEnvironmentStatuses)
        assert repr(statuses) == "StepEnvironmentStatuses(environments=2, not_found=1)"

    def test_equality_and_hash(self) -> None:
        one, two = self._created(), self._created()
        assert one.environment_statuses == two.environment_statuses
        a, b = one.environment_statuses[0].environments
        assert a == two.environment_statuses[0].environments[0]
        assert hash(a) == hash(two.environment_statuses[0].environments[0])
        assert a != b
        assert len({a, b, *two.environment_statuses[0].environments}) == 2
        n1 = one.environment_statuses[0].not_found[0]
        n2 = two.environment_statuses[0].not_found[0]
        assert n1 == n2 and hash(n1) == hash(n2)
        other = _job_template(
            [],
            [
                {
                    "name": "S",
                    "dependencies": [{"environment": "Other", "required": False}],
                    "script": _ECHO,
                }
            ],
        )
        assert n1 != _create(other).environment_statuses[0].not_found[0]
        with pytest.raises(TypeError):
            hash(one.environment_statuses[0])

    def test_statuses_differ_when_any_item_does(self) -> None:
        jt = _job_template([_env("A"), _env("B")], [{"name": "S", "script": _ECHO}])
        assert _create(jt).environment_statuses[0] != self._created().environment_statuses[0]

    def test_frozen_and_not_constructible(self) -> None:
        item = self._created().environment_statuses[0].environments[0]
        with pytest.raises(AttributeError):
            item.name = "X"  # type: ignore[misc]
        for cls in (StepEnvironmentStatus, StepEnvironmentStatuses, OptionalEntryNotFound):
            with pytest.raises(TypeError):
                cls()
