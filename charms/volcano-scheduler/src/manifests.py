import logging
from functools import cached_property
from pathlib import Path

from lightkube import Client, codecs
from lightkube.generic_resource import load_in_cluster_generic_resources
from lightkube.core.exceptions import ApiError

log = logging.getLogger(__file__)
BASE = "v1" # assumes we're in a k8s cluster that has access to v1 CRDs

class Manifests:
    def __init__(self, charm):
        self.namespace = charm.model.name
        self.application = charm.model.app.name
        self.client = Client(namespace=self.namespace, field_manager=self.application)
        load_in_cluster_generic_resources(self.client)

    @cached_property
    def base(self):
        return BASE

    @property
    def crds(self):
        return Path("templates", "crd", self.base).glob("*.yaml")

    def apply_manifests(self):
        for crd in self.crds:
            text = crd.read_text()
            for obj in codecs.load_all_yaml(text):
                self.delete_resource(
                    type(obj),
                    obj.metadata.name,
                    namespace=obj.metadata.namespace,
                    ignore_not_found=True,
                )
                self.client.create(obj)

    def delete_manifest(self, namespace=None, ignore_not_found=False, ignore_unauthorized=False):
        for crd in self.crds:
            text = crd.read_text()
            for obj in codecs.load_all_yaml(text):
                self.delete_resource(
                    type(obj),
                    obj.metadata.name,
                    namespace=obj.namespace,
                    ignore_not_found=ignore_not_found,
                    ignore_unauthorized=ignore_unauthorized,
                )

    def delete_resource(
        self,
        resource_type,
        name,
        namespace=None,
        ignore_not_found=False,
        ignore_unauthorized=False,
    ):
        """Delete a resource."""
        try:
            self.client.delete(resource_type, name, namespace=namespace)
        except ApiError as err:
            if err.status.message is not None:
                err_lower = err.status.message.lower()
                if "not found" in err_lower and ignore_not_found:
                    log.warning(f"Ignoring not found error: {err.status.message}")
                elif "(unauthorized)" in err_lower and ignore_unauthorized:
                    # Ignore error from https://bugs.launchpad.net/juju/+bug/1941655
                    log.warning(f"Ignoring unauthorized error: {err.status.message}")
                else:
                    log.exception(
                        "ApiError encountered while attempting to delete resource: "
                        + err.status.message
                    )
                    raise
            else:
                log.exception("ApiError encountered while attempting to delete resource.")
                raise
