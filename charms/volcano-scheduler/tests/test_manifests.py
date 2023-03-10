import unittest.mock as mock

import pytest
from lightkube.core.exceptions import ApiError
from lightkube.core.internal_resources import apiextensions
from lightkube.resources.apps_v1 import StatefulSet

from manifests import Manifests


@pytest.fixture
def manifests(harness):
    return Manifests(harness.charm)


def test_constructor(harness, manifests, lightkube_client):
    assert manifests.namespace == harness.charm.model.name
    assert manifests.application == harness.charm.model.app.name
    lightkube_client.list.assert_called_once_with(apiextensions.CustomResourceDefinition)


def test_resources(harness, manifests):
    itr = manifests._sorted_resources
    first, *mid, last = itr
    assert first.metadata.name == "commands.bus.volcano.sh"
    assert first.spec.group == "bus.volcano.sh"

    assert last.metadata.name == "queues.scheduling.volcano.sh"
    assert last.spec.group == "scheduling.volcano.sh"


def test_apply(lightkube_client, manifests):
    manifests.apply()
    calls = lightkube_client.apply.call_args_list
    assert len(calls) == 5
    (first,) = calls[0].args
    (last,) = calls[-1].args
    assert (first.kind, first.metadata.name) == (
        "CustomResourceDefinition",
        "commands.bus.volcano.sh",
    )
    assert (last.kind, last.metadata.name) == (
        "CustomResourceDefinition",
        "queues.scheduling.volcano.sh",
    )

    calls = lightkube_client.patch.call_args_list
    assert len(calls) == 1
    first = calls[0].kwargs
    assert tuple(first[_] for _ in ["res", "name", "namespace", "obj"]) == (
        StatefulSet,
        manifests.application,
        manifests.namespace,
        {"spec": {"template": {"spec": {"priorityClassName": "system-cluster-critical"}}}},
    )


def test_successful_delete_resources(manifests, caplog):
    manifests.delete_manifest(ignore_not_found=True)
    _, _, first = caplog.record_tuples[0]
    _, _, last = caplog.record_tuples[-1]
    assert first == "Deleted CustomResourceDefinition(commands.bus.volcano.sh, namespace=None)"
    assert last == "Deleted CustomResourceDefinition(queues.scheduling.volcano.sh, namespace=None)"


def test_unfound_delete_resources(lightkube_client, manifests, caplog):
    mock_response = mock.MagicMock()
    mock_response.json.return_value = dict(message="Mock Not Found")
    error = ApiError(response=mock_response)
    lightkube_client.delete.side_effect = error
    manifests.delete_manifest(ignore_not_found=True)
    for _, _, message in caplog.record_tuples:
        assert message == "Ignoring not found error: Mock Not Found"


def test_unauthorized_delete_resources(lightkube_client, manifests, caplog):
    mock_response = mock.MagicMock()
    mock_response.json.return_value = dict(message="Mock (unauthorized)")
    error = ApiError(response=mock_response)
    lightkube_client.delete.side_effect = error
    manifests.delete_manifest(ignore_unauthorized=True)
    for _, _, message in caplog.record_tuples:
        assert message == "Ignoring unauthorized error: Mock (unauthorized)"


def test_unexpected_delete_resources(lightkube_client, manifests, caplog):
    mock_response = mock.MagicMock()
    mock_response.json.return_value = dict(message="Mock Simple Failure")
    error = ApiError(response=mock_response)
    lightkube_client.delete.side_effect = error
    with pytest.raises(ApiError):
        manifests.delete_manifest(ignore_unauthorized=True)
    assert len(caplog.record_tuples) == 1
    _, _, exception = caplog.record_tuples[0]
    assert (
        exception
        == "ApiError encountered while attempting to delete resource: Mock Simple Failure"
    )


def test_no_message_delete_resources(lightkube_client, manifests, caplog):
    mock_response = mock.MagicMock()
    mock_response.json.return_value = dict()
    error = ApiError(response=mock_response)
    lightkube_client.delete.side_effect = error
    with pytest.raises(ApiError):
        manifests.delete_manifest(ignore_unauthorized=True)
    assert len(caplog.record_tuples) == 1
    _, _, exception = caplog.record_tuples[0]
    assert exception == "ApiError encountered while attempting to delete resource."
