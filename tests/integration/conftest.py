"""Configure integration tests."""

import asyncio
import contextlib
import json
import shlex
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from juju.tag import untag
from lightkube import Client, KubeConfig, codecs
from lightkube.generic_resource import load_in_cluster_generic_resources
from pytest_operator.plugin import OpsTest

from tests.integration.helpers import get_address


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


@pytest_asyncio.fixture(scope="module")
async def cos_lite(ops_test):
    """Deploy COS lite bundle."""
    config = {"controller-service-type": "loadbalancer"}
    cos_charms = [
        "alertmanager",
        "catalogue",
        "loki",
        "prometheus",
        "traefik",
        "grafana",
    ]
    model_name = "cos"
    credential_name = ops_test.cloud_name
    offers_overlay_path = Path("tests/integration/data/offers-overlay.yaml")
    await ops_test.track_model(
        model_name,
        model_name=model_name,
        credential_name=credential_name,
        config=config,
    )
    with ops_test.model_context(model_name) as model:
        overlays = [ops_test.Bundle("cos-lite", "edge"), offers_overlay_path]

        bundle, *overlays = await ops_test.async_render_bundles(*overlays)
        cmd = f"juju deploy -m {model.name} {bundle} --trust " + " ".join(
            f"--overlay={f}" for f in overlays
        )
        rc, stdout, stderr = await ops_test.run(*shlex.split(cmd))
        assert rc == 0, f"COS Lite failed to deploy: {(stderr or stdout).strip()}"

        await model.block_until(
            lambda: all(app in model.applications for app in cos_charms),
            timeout=60,
        )
        await model.wait_for_idle(
            status="active", timeout=60 * 30, raise_on_error=False
        )

        yield model


@pytest.fixture(scope="module")
async def traefik_ingress(ops_test, cos_lite):
    """Get the traefik ingress address."""
    with ops_test.model_context(cos_lite.name):
        address = await get_address(ops_test=ops_test, app_name="traefik")
        yield address


@pytest.fixture(scope="module")
async def dashboard_titles():
    """Get the Grafana dashboard titles from the charm source."""
    grafana_dir = Path("charms/volcano-scheduler/src/grafana_dashboards")
    grafana_files = [
        p for p in grafana_dir.iterdir() if p.is_file() and p.name.endswith(".json")
    ]
    titles = []
    for path in grafana_files:
        dashboard = json.loads(path.read_text())
        titles.append(dashboard["title"])
    return set(titles)


@pytest_asyncio.fixture(scope="module")
async def related_grafana(ops_test, cos_lite, volcano_system):
    """Integrate Grafana charm with the volcano-scheduler charm."""
    model_owner = untag("user-", cos_lite.info.owner_tag)
    controller_name = ops_test.controller_name

    with ops_test.model_context("main"):
        await ops_test.model.integrate(
            "volcano-scheduler:grafana-dashboard",
            f"{controller_name}:{model_owner}/{cos_lite.name}.grafana-dashboards",
        )
        with ops_test.model_context(cos_lite.name) as model:
            await model.wait_for_idle(status="active")
        await ops_test.model.wait_for_idle(status="active")

    yield


@pytest_asyncio.fixture(scope="module")
@pytest.mark.usefixtures("related_grafana")
async def grafana_password(ops_test, cos_lite):
    """Get the Grafana admin password."""
    with ops_test.model_context(cos_lite.name):
        action = (
            await ops_test.model.applications["grafana"]
            .units[0]
            .run_action("get-admin-password")
        )
        action = await action.wait()
    return action.results["admin-password"]


@pytest.fixture(scope="module")
async def expected_prometheus_metrics():
    """Get the expected Prometheus metrics from the charm source."""
    metrics_path = Path("tests/integration/data/volcano-metrics.json")
    with open(metrics_path, "r") as file:
        return set(json.load(file)["data"])


@pytest.fixture(scope="module")
async def kube_state_metrics(kubernetes):
    """Deploy kube-state-metrics for the Prometheus tests."""
    ksm_manifest = Path("tests/integration/data/kube-state-metrics.yaml")
    with open(ksm_manifest, "r") as file:
        objects = codecs.load_all_yaml(file)
        for obj in objects:
            kubernetes.create(obj)

        yield

        for obj in objects:
            kubernetes.delete(
                type(obj), obj.metadata.name, namespace=obj.metadata.namespace
            )


@pytest.fixture(scope="module")
async def related_prometheus(
    ops_test: OpsTest, cos_lite, volcano_system, kube_state_metrics
):
    """Integrate Prometheus charm with the volcano-scheduler charm."""
    model_owner = untag("user-", cos_lite.info.owner_tag)
    controller_name = ops_test.controller_name

    with ops_test.model_context("main"):
        await ops_test.model.integrate(
            "volcano-scheduler:metrics-endpoint",
            f"{controller_name}:{model_owner}/{cos_lite.name}.prometheus-scrape",
        )
        await ops_test.model.wait_for_idle(status="active")
        with ops_test.model_context(cos_lite.name) as model:
            await model.wait_for_idle(status="active")

    yield
