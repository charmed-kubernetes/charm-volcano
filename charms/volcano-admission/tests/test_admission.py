import unittest.mock as mock

import pytest
from ops.pebble import ExecError

from admission import Admission, AdmissionArgs, AdmissionConfig
from charm import CharmVolcano
from tls_client import TLSClient


@pytest.fixture
def admission():
    return Admission()


@pytest.fixture
def tls() -> TLSClient:
    tls = mock.MagicMock(spec=TLSClient)
    tls.cert = "test.crt"
    tls.private_key = "test.key"
    tls.ca_cert = "test.ca.crt"
    return tls


def test_binary(admission):
    assert str(admission.binary) == "/vc-webhook-manager"


def test_command(harness, tls, admission):
    args = AdmissionArgs([], 1, {"extra": "args"})
    config = AdmissionConfig([])

    admission.apply(harness.charm, tls, config, args)
    cmd = (
        "/vc-webhook-manager --enabled-admission= "
        "--tls-cert-file=test.crt "
        "--tls-private-key-file=test.key "
        "--ca-cert-file=test.ca.crt "
        "--admission-conf=/admission.local.config/volcano-admission.yaml "
        "--webhook-namespace=test_command "
        "--webhook-service-name=volcano-admission "
        "--logtostderr --port=443 -v=1 --extra='args' 2>&1"
    )
    assert admission.command == cmd


def test_restart(harness, tls, admission):
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    expected_plan = {
        "services": {
            "volcano": {
                "override": "replace",
                "summary": "volcano",
                "command": "mock_command",
                "startup": "enabled",
            }
        }
    }
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    admission.command = "mock_command"
    admission.tls = tls
    admission.restart(container)

    # Get the plan now we've run PebbleReady
    updated_plan = harness.get_container_pebble_plan(CharmVolcano.CONTAINER).to_dict()
    # Check we've got the plan we expected
    assert expected_plan == updated_plan


def test_version_success(harness, tls, admission):
    exec_response = """\
API Version: v1alpha1
Version: v1.7.0
Git SHA: 1933d46bdc4434772518ebb74c4281671ddeffa1
Built At: 2023-01-04 09:18:35
Go Version: go1.19.1
Go OS/Arch: linux/amd64"""
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=True):
        with mock.patch.object(container, "exec") as mock_exec:
            mock_process = mock_exec.return_value
            mock_process.wait_output.return_value = (exec_response, None)
            admission.tls = tls
            version = admission.version(container)
    (args,), _ = mock_exec.call_args
    for arg in ["--version", "--tls-cert", "--tls-private", "--ca-cert"]:
        assert any(_.startswith(arg) for _ in args)
    assert version == "v1.7.0"


class MockExecError(ExecError):
    def __init__(self, *_args, **_kw):
        pass

    def __str__(self):
        """Mock out __str__ method."""
        return "mock_exec_error"


@pytest.mark.parametrize(
    "failure", [(False, None, ""), (True, MockExecError(), ""), (True, None, "bad-version")]
)
def test_version_failure(harness, admission, tls, failure):
    list_files, exec_error, exec_response = failure
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=list_files):
        with mock.patch.object(container, "exec") as mock_exec:
            mock_process = mock_exec.return_value
            mock_process.wait_output.side_effect = exec_error
            mock_process.wait_output.return_value = (exec_response, None)
            admission.tls = tls
            version = admission.version(container)
    assert version == "Unknown"
