"""Unit tests."""

import unittest.mock as mock

import pytest
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.testing import Harness

from charm import CharmVolcano


@pytest.fixture(scope="function")
def harness(request):
    """Test setup."""
    harness = Harness(CharmVolcano)
    harness.set_leader(is_leader=True)
    harness.set_model_name(request.node.originalname)
    harness.begin()
    yield harness
    harness.cleanup()


def test_on_install(harness):
    # Get the plan now we've run PebbleReady
    harness.set_can_connect(CharmVolcano.CONTAINER, False)
    harness.charm.on.install.emit()
    assert harness.charm.unit.status == WaitingStatus("Container Not Ready")


def test_on_pebble_ready(harness):
    harness.set_can_connect(CharmVolcano.CONTAINER, True)
    container = harness.model.unit.get_container(CharmVolcano.CONTAINER)
    with mock.patch.object(container, "list_files", return_value=True):
        harness.charm.on.volcano_pebble_ready.emit(container)

    expected_plan = {
        "services": {
            "volcano": {
                "command": (
                    "/vc-scheduler --logtostderr "
                    "--scheduler-conf=/volcano.scheduler/volcano-scheduler.yaml "
                    "--enable-healthz=true "
                    "--enable-metrics=false -v=3 2>&1"
                ),
                "override": "replace",
                "startup": "enabled",
                "summary": "volcano"
            }
        }
    }

    # Get the plan now we've run PebbleReady
    updated_plan = harness.get_container_pebble_plan(CharmVolcano.CONTAINER).to_dict()
    # Check we've got the plan we expected
    assert expected_plan == updated_plan

    assert harness.charm.unit.status == ActiveStatus()
