#!/usr/bin/env python3
"""Integration Tests.

Copyright 2023 Adam Dyess
See LICENSE file for licensing details.
"""

import asyncio
import datetime
import logging
import re
from pathlib import Path
from typing import Sequence

import pytest
from lightkube import codecs
from lightkube.generic_resource import load_in_cluster_generic_resources
from lightkube.resources.apps_v1 import StatefulSet
from lightkube.resources.core_v1 import Pod
from pytest_operator.plugin import OpsTest

from tests.integration.grafana import Grafana
from tests.integration.prometheus import Prometheus

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
@pytest.mark.usefixtures("volcano_system")
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """


def check_if_ready(kubernetes, resource_type, unready, timeout=5 * 60, **kw):
    """Loop until resources are ready or raise timeout."""
    starting = datetime.datetime.now()
    ending = starting + datetime.timedelta(seconds=timeout)
    while datetime.datetime.now() < ending:
        for dep in kubernetes.list(resource_type, **kw):
            if dep.status.readyReplicas == 1:
                unready.discard(dep.metadata.name)
        if not unready:
            return True

    raise TimeoutError()


@pytest.mark.usefixtures("volcano_system")
async def test_load_uncharmed_manifests(ops_test: OpsTest, kubernetes):
    """Test all deployments are ready after installation."""
    assert check_if_ready(
        kubernetes,
        StatefulSet,
        {"volcano-admission", "volcano-controllers", "volcano-scheduler"},
        namespace=ops_test.models["main"].model_name,
    )


@pytest.mark.usefixtures("volcano_system")
@pytest.mark.usefixtures("kubeflow")
async def test_scheduler(ops_test: OpsTest, kubernetes):
    """Test the volcano scheduler can accept new queues, a new VCJob, and a TFJob."""
    basedir = Path(".") / "tests" / "integration" / "data" / "volcano"
    load_in_cluster_generic_resources(kubernetes)
    sched_status_re = re.compile(
        r"There are <(\d+)> Jobs, <(\d+)> Queues and <\d+> Nodes"
    )

    def _parse_scheduler_logs(lines) -> Sequence[int]:
        for line in reversed(list(lines)):
            if m := sched_status_re.search(line):
                return map(int, m.groups())
        return 0, 0

    def _from_file(path):
        return codecs.load_all_yaml(path.read_text())

    objects = (
        _from_file(basedir / "queue.yaml")
        + _from_file(basedir / "tfjob.yaml")
        + _from_file(basedir / "vcjob.yaml")
    )

    test_start = datetime.datetime.now()
    try:
        for obj in objects:
            kubernetes.create(obj)
        await asyncio.sleep(10)
        ns = ops_test.models["main"].model_name
        (scheduler,) = kubernetes.list(
            Pod, namespace=ns, labels={"app.kubernetes.io/name": "volcano-scheduler"}
        )
        (container,) = [
            c.name for c in scheduler.spec.containers if "volcano" in c.name
        ]
        log_time = datetime.datetime.now()
        jobs, queues = _parse_scheduler_logs(
            kubernetes.log(
                scheduler.metadata.name,
                namespace=ns,
                container=container,
                since=(log_time - test_start).seconds,
            )
        )
        assert jobs == 2, f"Expected to find 2 Jobs, instead found {jobs}"
        assert queues == 2, f"Expected to find 2 Queues, instead found {queues}"
    finally:
        for obj in objects:
            kubernetes.delete(
                type(obj), obj.metadata.name, namespace=obj.metadata.namespace
            )


@pytest.mark.timeout(60 * 30)
@pytest.mark.usefixtures("volcano_system", "related_grafana")
async def test_grafana(ops_test, traefik_ingress, grafana_password, dashboard_titles):
    """Test Grafana is ready and has the expected dashboards."""
    grafana = Grafana(ops_test, host=traefik_ingress, password=grafana_password)
    while not await grafana.is_ready():
        await asyncio.sleep(1)
    dashboards = await grafana.dashboards_all()
    actual_dashboards = set()
    for dashboard in dashboards:
        actual_dashboards.add(dashboard["title"])
    assert dashboard_titles.issubset(
        actual_dashboards
    ), f"Missing dashboards: {dashboard_titles.difference(actual_dashboards)}"


@pytest.mark.timeout(60 * 30)
@pytest.mark.usefixtures("volcano_system", "related_prometheus")
async def test_prometheus(ops_test, traefik_ingress, expected_prometheus_metrics):
    """Test Prometheus is ready and has the expected metrics."""
    prometheus = Prometheus(host=traefik_ingress)
    while not await prometheus.is_ready():
        await asyncio.sleep(5)

    # Wait for metrics to be available
    await asyncio.sleep(120)
    metrics = await prometheus.get_metrics()
    common_metrics = expected_prometheus_metrics.intersection(set(metrics))
    assert (
        common_metrics
    ), f"KSM missing: {expected_prometheus_metrics.difference(set(metrics))}"
