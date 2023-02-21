"""Configure integration tests."""

from pathlib import Path

import pytest_asyncio
from lightkube import Client, KubeConfig


@pytest_asyncio.fixture(scope="module")
async def volcano_system():
    """Create a k8s client into the namespace volcano-system."""
    namespace = "volcano-system"
    config = KubeConfig.from_file(Path("~/.kube/config"))
    client = Client(
        config=config, namespace=namespace, field_manager=namespace, trust_env=False
    )
    yield client
