#!/usr/bin/env python3
"""Integration Tests.

Copyright 2023 Adam Dyess
See LICENSE file for licensing details.
"""

import asyncio
import datetime
import logging
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import pytest
import yaml
from lightkube import codecs
from lightkube.resources.apps_v1 import Deployment
from pytest_operator.plugin import OpsTest

from lib.templating import render_templates

logger = logging.getLogger(__name__)


@dataclass
class Charm:
    """Represents source charms."""

    path: Path
    _charmfile: Path = None

    @property
    def metadata(self) -> dict:
        """Charm Metadata."""
        return yaml.safe_load((self.path / "metadata.yaml").read_text())

    @property
    def app_name(self) -> str:
        """Suggested charm name."""
        return self.metadata["name"]

    @property
    async def resources(self) -> dict:
        """Charm resources."""
        return {}

    async def resolve(self, ops_test: OpsTest) -> Path:
        """Build the charm with ops_test."""
        if self._charmfile is None:
            try:
                charm_name = f"{self.app_name}*.charm"
                potentials = chain(
                    *(path.glob(charm_name) for path in (Path(), self.path))
                )
                self._charmfile, *_ = filter(None, potentials)
            except ValueError:
                self._charmfile = await ops_test.build_charm(self.path)
        return self._charmfile.resolve()

    async def deploy(self, ops_test: OpsTest, **kwargs):
        """Deploy charm."""
        await ops_test.model.deploy(
            str(await self.resolve(ops_test)),
            resources=await self.resources,
            application_name=self.app_name,
            series="jammy",
            **kwargs,
        )


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charms from local source folder
    charms = [
        Charm(Path("charms") / f"volcano-{_}")
        for _ in ("admission", "controller-manager", "scheduler")
    ]

    # Deploy the charm and wait for active/idle status
    await asyncio.gather(
        *(charm.deploy(ops_test, trust=True) for charm in charms),
        ops_test.model.wait_for_idle(
            apps=[n.app_name for n in charms],
            status="active",
            raise_on_blocked=True,
            timeout=1000,
        ),
    )


def check_deployments_ready(volcano_system, unready, timeout=5 * 60):
    """Loop until deployments are ready or raise timeout."""
    starting = datetime.datetime.now()
    ending = starting + datetime.timedelta(seconds=timeout)
    while datetime.datetime.now() < ending:
        for dep in volcano_system.list(Deployment):
            if dep.status.readyReplicas == 1:
                unready.discard(dep.metadata.name)
        if not unready:
            return True

    raise TimeoutError()


async def test_load_uncharmed_manifests(ops_test, volcano_system):
    """Test all deployments are ready after installation."""
    workspace = Path(".")
    basedir = workspace / "tests" / "integration" / "data"
    charms = workspace / "charms"

    templates = [
        "volcano-admission/templates/admission.yaml",
        "volcano-scheduler/templates/crd/v1/batch.volcano.sh_jobs.yaml",
        "volcano-scheduler/templates/crd/v1/bus.volcano.sh_commands.yaml",
        "volcano-controller-manager/templates/controllers.yaml",
        "volcano-scheduler/templates/scheduler.yaml",
        "volcano-scheduler/templates/crd/v1/scheduling.volcano.sh_podgroups.yaml",
        "volcano-scheduler/templates/crd/v1/scheduling.volcano.sh_queues.yaml",
        "volcano-scheduler/templates/crd/v1/nodeinfo.volcano.sh_numatopologies.yaml",
        "volcano-admission/templates/webhooks.yaml",
    ]
    _ = [
        volcano_system.apply(r)
        for t in render_templates(
            basedir,
            *map(lambda _: charms / _, templates),
            values=basedir / "values.yaml",
            name="volcano",
            namespace="volcano-system",
        )
        for r in codecs.load_all_yaml(t)
    ]
    assert check_deployments_ready(
        volcano_system,
        {"volcano-admission", "volcano-scheduler", "volcano-controllers"},
    )
