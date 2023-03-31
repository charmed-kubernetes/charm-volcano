import unittest.mock as mock

import pytest
from lightkube.core.exceptions import ApiError
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import ModelError

from manifests import Manifests


@pytest.fixture()
def manifests(harness):
    yield Manifests(harness.charm)


def test_constructor(harness, manifests, lightkube_client):
    assert manifests.namespace == harness.charm.model.name
    assert manifests.application == harness.charm.model.app.name
    assert manifests.client == lightkube_client


def test_patches(harness, manifests):
    itr = manifests._sorted_patches
    only_patch, = itr
    assert only_patch["res"] == StatefulSet
    assert only_patch["name"] == manifests.application
    assert only_patch["namespace"] == manifests.namespace
    assert only_patch["obj"]["spec"]["template"]["spec"]["priorityClassName"] == "system-cluster-critical"


def test_apply(lightkube_client, manifests):
    manifests.apply()
    calls = lightkube_client.patch.call_args_list
    assert len(calls) == 1
    first = calls[0].kwargs
    assert tuple(first[_] for _ in ["res", "name", "namespace", "obj"]) == (
        StatefulSet,
        manifests.application,
        manifests.namespace,
        {"spec": {"template": {"spec": {"priorityClassName": "system-cluster-critical"}}}},
    )

