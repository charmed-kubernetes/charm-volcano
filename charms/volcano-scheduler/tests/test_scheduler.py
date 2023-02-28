import pytest

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
