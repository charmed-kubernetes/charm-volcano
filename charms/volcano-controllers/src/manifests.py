"""Apply extra manifests for enabling the scheduler and its config."""

import logging
from typing import List, Sequence

from lightkube import Client
from lightkube.generic_resource import load_in_cluster_generic_resources
from lightkube.resources.apps_v1 import StatefulSet

log = logging.getLogger(__name__)


class Manifests:
    """Render manifests from charm config and apply to the cluster."""

    def __init__(self, charm):
        self._charm = charm
        self.namespace = charm.model.name
        self.application = charm.app.name
        self.client = Client(namespace=self.namespace, field_manager=self.application)
        load_in_cluster_generic_resources(self.client)

    @property
    def _patches(self) -> Sequence[dict]:
        patches = []
        # - Adjust the charm's priorityClassname
        patch = {"spec": {"template": {"spec": {"priorityClassName": "system-cluster-critical"}}}}
        patches.append(
            dict(
                res=StatefulSet,
                name=self.application,
                namespace=self.namespace,
                obj=patch,
            )
        )
        return patches

    @property
    def _sorted_patches(self) -> List[dict]:
        return sorted(self._patches, key=lambda r: r["name"])

    def apply(self):
        """Apply all manifests managed by this charm."""
        for patch in self._sorted_patches:
            self.client.patch(**patch)