import unittest.mock as mock

import pytest
from ops.pebble import ExecError

from charm import CharmVolcano
from scheduler import Scheduler, SchedulerArgs, SchedulerConfig


@pytest.fixture
def scheduler():
    return Scheduler()


def test_binary(scheduler):
    assert str(scheduler.binary) == "/vc-scheduler"


def test_config_file(harness, scheduler):
    scheduler.config = SchedulerConfig.load(harness.charm)
    filepath, content = scheduler.config_file
    assert str(filepath) == "/volcano.scheduler/volcano-scheduler.yaml"
    assert content.startswith("actions: enqueue, allocate, backfill\n")
    assert content.endswith("  - name: binpack\n")


def test_command(harness, scheduler):
    args = SchedulerArgs("false", "true", 1, {"extra": "args"})
    config = SchedulerConfig(actions="test, me", tiers=[])

    scheduler.apply(harness.charm, config, args)
    cmd = "/vc-scheduler --logtostderr --scheduler-conf=/volcano.scheduler/volcano-scheduler.yaml --enable-healthz=false --enable-metrics=true -v=1 --extra='args' 2>&1"
    assert scheduler.command == cmd


def test_restart(harness, scheduler):
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
    scheduler.command = "mock_command"
    scheduler.restart(container)

    # Get the plan now we've run PebbleReady
    updated_plan = harness.get_container_pebble_plan(CharmVolcano.CONTAINER).to_dict()
    # Check we've got the plan we expected
    assert expected_plan == updated_plan


def test_version_success(harness, scheduler):
    exec_response = """\
API Version: v1alpha1
Version: v1.7.0
Git SHA: 1933d46bdc4434772518ebb74c4281671ddeffa1
Built At: 2023-01-04 09:08:59
Go Version: go1.19.1
Go OS/Arch: linux/amd64"""
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=True):
        with mock.patch.object(container, "exec") as mock_exec:
            mock_process = mock_exec.return_value
            mock_process.wait_output.return_value = (exec_response, None)
            version = scheduler.version(container)
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
def test_version_failure(harness, scheduler, failure):
    list_files, exec_error, exec_response = failure
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=list_files):
        with mock.patch.object(container, "exec") as mock_exec:
            mock_process = mock_exec.return_value
            mock_process.wait_output.side_effect = exec_error
            mock_process.wait_output.return_value = (exec_response, None)
            version = scheduler.version(container)
    assert version == "Unknown"
