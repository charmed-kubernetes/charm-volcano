"""Configure integration tests."""

import asyncio
import contextlib
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import pytest_asyncio
import yaml
from lightkube import Client, KubeConfig
from lightkube.generic_resource import load_in_cluster_generic_resources
from pytest_operator.plugin import OpsTest


@pytest_asyncio.fixture(scope="module")
async def kubernetes(request):
    """Create a k8s client."""
    config = KubeConfig.from_file(Path("~/.kube/config"))
    client = Client(config=config, field_manager=request.node.name, trust_env=False)
    load_in_cluster_generic_resources(client)
    yield client


class CharmDeployment:
    """Call arguments into model.deploy."""

    def __init__(self, *args, **kw):
        """Capture call args."""
        self.args = args
        self.kw = kw

    @property
    def app_name(self):
        """Find the "application_name" keyword argument."""
        return self.kw.get("application_name")


@dataclass
class Charm:
    """Represents source charms."""

    ops_test: OpsTest
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
    def resources(self) -> dict:
        """Charm resources."""
        resources = self.metadata.get("resources") or {}

        return {
            name: self._craft_resource(name, resource)
            for name, resource in resources.items()
        }

    def _craft_resource(self, name: str, resource: dict):
        if oci_image := resource.get("upstream-source"):
            return oci_image

    async def resolve(self) -> Path:
        """Build the charm with ops_test."""
        if self._charmfile is None:
            try:
                charm_name = f"{self.app_name}*.charm"
                potentials = chain(
                    *(path.glob(charm_name) for path in (Path(), self.path))
                )
                self._charmfile, *_ = filter(None, potentials)
            except ValueError:
                self._charmfile = await self.ops_test.build_charm(self.path)
        return self._charmfile.resolve()


@contextlib.asynccontextmanager
async def deploy_model(request, ops_test, model_name, *deploy_args: CharmDeployment):
    """Add a juju model, deploy apps into it, wait for them to be active."""
    config = {}
    if request.config.option.model_config:
        config = ops_test.read_model_config(request.config.option.model_config)
    credential_name = ops_test.cloud_name
    if model_name not in ops_test.models:
        await ops_test.track_model(
            model_name,
            model_name=model_name,
            credential_name=credential_name,
            config=config,
        )
    with ops_test.model_context(model_name) as the_model:
        await asyncio.gather(
            *(
                the_model.deploy(*charm.args, **charm.kw)
                for charm in deploy_args
                if charm.app_name not in the_model.applications
            ),
            the_model.wait_for_idle(
                apps=[n.app_name for n in deploy_args],
                status="active",
                raise_on_blocked=True,
                timeout=15 * 60,
            ),
        )
        yield the_model


@pytest_asyncio.fixture(scope="module")
async def volcano_system(request, ops_test):
    """Deploy local volcano charms."""
    model = "main"
    charm_names = ("admission", "controllers", "scheduler")
    charms = [Charm(ops_test, Path("charms") / f"volcano-{_}") for _ in charm_names]
    charm_files = await asyncio.gather(*[charm.resolve() for charm in charms])
    deployments = [
        CharmDeployment(
            str(path),
            resources=charm.resources,
            application_name=charm.app_name,
            series="jammy",
            trust=True,
        )
        for path, charm in zip(charm_files, charms)
    ]
    async with deploy_model(request, ops_test, model, *deployments) as the_model:
        yield the_model


@pytest_asyncio.fixture(scope="module")
async def kubeflow(request, ops_test):
    """Deploy minimal charmed-kubeflow."""
    model = "kubeflow"
    app = "training-operator"
    charm = CharmDeployment(app, application_name=app, channel="1.5/stable", trust=True)
    async with deploy_model(request, ops_test, model, charm) as the_model:
        yield the_model
