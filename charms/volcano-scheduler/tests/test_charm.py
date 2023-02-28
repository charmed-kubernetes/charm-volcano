"""Unit tests."""

import unittest.mock as mock

from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charm import CharmVolcano


def test_container_not_ready(harness):
    # Get the plan now we've run PebbleReady
    harness.set_can_connect(CharmVolcano.CONTAINER, False)
    harness.charm.on.install.emit()
    assert harness.charm.unit.status == WaitingStatus("Container Not Ready")


def test_container_missing_exec(harness):
    # Get the plan now we've run PebbleReady
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=False):
        harness.charm.on.volcano_pebble_ready.emit(container)
    assert harness.charm.unit.status == BlockedStatus("Image missing executable: /vc-scheduler")


@mock.patch("charm.Scheduler")
@mock.patch("charm.Manifests")
def test_container_ready(mock_manifest, mock_scheduler, harness):
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=True):
        harness.charm.on.volcano_pebble_ready.emit(container)
    assert harness.charm.unit.status == ActiveStatus()

    mock_scheduler.assert_called_once_with()
    mock_manifest.assert_called_once_with(harness.charm)

    sched_inst = mock_scheduler.return_value
    manif_inst = mock_manifest.return_value

    sched_inst.apply.assert_called_once()
    manif_inst.apply.assert_called_once_with()
    sched_inst.restart.assert_called_once_with(container)
