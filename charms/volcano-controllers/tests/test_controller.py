import unittest.mock as mock

import pytest
from ops.pebble import ExecError

from charm import CharmVolcano
from controller import Controller, ControllerArgs


@pytest.fixture
def controller():
    return Controller()


def test_binary(controller):
    assert str(controller.binary) == "/vc-controller-manager"


def test_command(harness, controller):
    args = ControllerArgs("false", 1, {"extra": "args"})

    controller.apply(harness.charm, args)
    cmd = "/vc-controller-manager --logtostderr --enable-healthz=false -v=1 --extra='args' 2>&1"
    assert controller.command == cmd


def test_restart(harness, controller):
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
    controller.command = "mock_command"
    controller.restart(container)

    # Get the plan now we've run PebbleReady
    updated_plan = harness.get_container_pebble_plan(CharmVolcano.CONTAINER).to_dict()
    # Check we've got the plan we expected
    assert expected_plan == updated_plan


def test_version_success(harness, controller):
    exec_response = """\
API Version: v1alpha1
Version: v1.7.0
Git SHA: 1933d46bdc4434772518ebb74c4281671ddeffa1
Built At: 2023-01-04 09:01:37
Go Version: go1.19.1
Go OS/Arch: linux/amd64"""
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=True):
        with mock.patch.object(container, "exec") as mock_exec:
            mock_process = mock_exec.return_value
            mock_process.wait_output.return_value = (exec_response, None)
            version = controller.version(container)
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
def test_version_failure(harness, controller, failure):
    list_files, exec_error, exec_response = failure
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=list_files):
        with mock.patch.object(container, "exec") as mock_exec:
            mock_process = mock_exec.return_value
            mock_process.wait_output.side_effect = exec_error
            mock_process.wait_output.return_value = (exec_response, None)
            version = controller.version(container)
    assert version == "Unknown"
