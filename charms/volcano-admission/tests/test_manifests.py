import unittest.mock as mock

import pytest
from lightkube.core.exceptions import ApiError
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import ModelError

from manifests import Manifests


@pytest.fixture()
def ksp(request):
    # Run tests using KubernetesServicePatch patching
    with mock.patch("manifests.KubernetesServicePatch") as ksp:
        ksp.return_value.is_patched.return_value = False
        yield ksp.return_value


@pytest.fixture()
def manifests(ksp, harness):
    yield Manifests(harness.charm)


def test_constructor(harness, manifests, lightkube_client):
    assert manifests.namespace == harness.charm.model.name
    assert manifests.application == harness.charm.model.app.name
    assert manifests.client == lightkube_client


def test_resources(harness, manifests):
    itr = manifests._sorted_resources
    first, *_, last = itr
    assert first.metadata.name == "volcano-admission-service-jobs-mutate"
    assert first.webhooks[0].rules[0].resources == ["jobs"]

    assert last.metadata.name == "volcano-admission-service-queues-validate"
    assert last.webhooks[0].rules[0].resources == ["queues"]


@pytest.mark.parametrize(
    "open_port", [True, False], ids=["open_port=enabled", "open_port=disabled"]
)
def test_apply(lightkube_client, manifests, ksp, open_port):
    def open_port_se(*_args):
        if not open_port:
            raise ModelError()

    with mock.patch.object(
        manifests._charm.unit, "open_port", side_effect=open_port_se
    ) as mock_open_port:
        manifests.apply()
    calls = lightkube_client.apply.call_args_list
    assert len(calls) == 7
    (first,) = calls[0].args
    (last,) = calls[-1].args
    assert (first.kind, first.metadata.name) == (
        "MutatingWebhookConfiguration",
        "volcano-admission-service-jobs-mutate",
    )
    assert (last.kind, last.metadata.name) == (
        "ValidatingWebhookConfiguration",
        "volcano-admission-service-queues-validate",
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

    mock_open_port.assert_called_once_with("tcp", 443)
    if not open_port:
        ksp._patch.assert_called_once_with()


def test_successful_delete_resources(manifests, caplog):
    manifests.delete_manifest(ignore_not_found=True)
    _, _, first = caplog.record_tuples[0]
    _, _, last = caplog.record_tuples[-1]
    assert (
        first
        == "Deleted MutatingWebhookConfiguration(volcano-admission-service-jobs-mutate, namespace=None)"
    )
    assert (
        last
        == "Deleted ValidatingWebhookConfiguration(volcano-admission-service-queues-validate, namespace=None)"
    )


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
