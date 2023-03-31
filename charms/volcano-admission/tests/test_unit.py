"""Unit tests."""

import unittest.mock as mock

import pytest
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import ConnectionError

from charm import CharmVolcano


def test_container_not_ready(harness):
    # Get the plan now we've run PebbleReady
    harness.set_can_connect(CharmVolcano.CONTAINER, False)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    harness.charm.on.volcano_pebble_ready.emit(container)
    assert harness.charm.unit.status == WaitingStatus("Admission Not Ready")


@mock.patch("charm.Admission")
def test_container_missing_exec(mock_admission, harness):
    # Get the plan now we've run PebbleRead
    admission_inst = mock_admission.return_value
    admission_inst.executable.return_value = False
    admission_inst.binary = "/expected-binary"
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    harness.charm.on.volcano_pebble_ready.emit(container)
    assert harness.charm.unit.status == BlockedStatus(
        f"Image missing executable: {admission_inst.binary}"
    )
    admission_inst.executable.assert_called_once_with(container)


@mock.patch("charm.Admission")
@mock.patch("charm.Manifests")
@pytest.mark.parametrize("conn_err", [None, ConnectionError()])
def test_container_ready(mock_manifest, mock_admission, harness, conn_err):
    manif_inst = mock_manifest.return_value
    admission_inst = mock_admission.return_value
    admission_inst.executable.return_value = True
    admission_inst.restart.side_effect = conn_err

    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    harness.charm.on.volcano_pebble_ready.emit(container)

    mock_admission.assert_called_once_with()
    mock_manifest.assert_called_once_with(harness.charm)

    admission_inst.executable.assert_called_once_with(container)
    admission_inst.apply.assert_called_once()
    manif_inst.apply.assert_called_once_with()
    admission_inst.restart.assert_called_once_with(container)

    if conn_err:
        assert harness.charm.unit.status == WaitingStatus("Failed to connect to admission")
    else:
        harness.charm.unit.status == MaintenanceStatus()


@mock.patch("charm.Admission")
def test_leader_set(mock_admission, harness):
    # Get the plan now we've run PebbleReady
    sched_inst = mock_admission.return_value
    sched_inst.version.return_value = "test-ver"
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    harness.charm.on.leader_elected.emit()
    assert harness.get_workload_version() == "test-ver"


def test_update_status_ready(harness):
    # Get the plan now we've run PebbleReady
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    harness.charm.on.update_status.emit()
    assert harness.charm.unit.status == ActiveStatus()
