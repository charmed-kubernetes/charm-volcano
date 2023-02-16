#!/usr/bin/env python3
"""Integration Tests.

Copyright 2023 Adam Dyess
See LICENSE file for licensing details.
"""

import asyncio
import logging
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

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
        return self._charmfile

    async def deploy(self, ops_test: OpsTest):
        """Deploy charm."""
        await ops_test.model.deploy(
            await self.resolve(ops_test),
            resources=await self.resources,
            application_name=self.app_name,
        )


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charms from local source folder
    charms = [
        Charm(Path("charms") / f"volcano-{_}") for _ in ("admission", "controller-manager", "scheduler")
    ]

    # Deploy the charm and wait for active/idle status
    await asyncio.gather(
        *(charm.deploy(ops_test) for charm in charms),
        ops_test.model.wait_for_idle(
            apps=[n.app_name for n in charms],
            status="active",
            raise_on_blocked=True,
            timeout=1000,
        ),
    )
