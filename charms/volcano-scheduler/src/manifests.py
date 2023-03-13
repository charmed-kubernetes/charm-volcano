"""Apply extra manifests for enabling the scheduler and its config."""

import logging
from pathlib import Path
from typing import List, Sequence

from charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from jinja2 import Environment, FileSystemLoader
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from lightkube.core.resource import Resource
from lightkube.generic_resource import load_in_cluster_generic_resources
from lightkube.models.core_v1 import ServicePort
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import ModelError

log = logging.getLogger(__name__)
CRD_BASE = "v1"  # assumes we're in a k8s cluster that has access to v1 CRDs


class Manifests:
    """Render manifests from charm config and apply to the cluster."""

    def __init__(self, charm):
        self._charm = charm
        self.namespace = charm.model.name
        self.application = charm.app.name
        self.client = Client(namespace=self.namespace, field_manager=self.application)
        load_in_cluster_generic_resources(self.client)

        self.service_port = ServicePort(8080, name=self.application, protocol="TCP")
        self.service_patcher = KubernetesServicePatch(charm, [self.service_port])

    @property
    def _resources(self) -> Sequence[Resource]:
        templates = Path("templates")
        templates = (templates / "scheduler.yaml", *(templates / "crd" / CRD_BASE).glob("*.yaml"))
        context = {
            "Values": self._config,
            "Release": {"Name": "volcano", "Namespace": self.namespace},
        }
        env = Environment(loader=FileSystemLoader("/"))
        for _ in templates:
            rendered = env.get_template(str(_.resolve())).render(context)
            for obj in codecs.load_all_yaml(rendered):
                yield obj

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
    def _sorted_resources(self) -> List[Resource]:
        return sorted(self._resources, key=lambda r: r.metadata.name)

    @property
    def _sorted_patches(self) -> List[dict]:
        return sorted(self._patches, key=lambda r: r["name"])

    @property
    def _config(self) -> dict:
        return dict(
            basic=dict(image_tag_version="v1.7.0", image_pull_secret="", admission_port=8443),
            custom=dict(
                metrics_enable=False,
                admission_enable=True,
                controller_enable=True,
                scheduler_enable=True,
                enabled_admissions="/jobs/mutate,/jobs/validate,/podgroups/mutate,/pods/validate,/pods/mutate,/queues/mutate,/queues/validate",
            ),
            juju=dict(admission=True, controller=True, scheduler=True),
        )

    def _delete_resource(
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
        else:
            rtype = resource_type._api_info.resource.kind
            log.info(f"Deleted {rtype}({name}, namespace={namespace})")

    def apply(self):
        """Apply all manifests managed by this charm."""
        for obj in self._sorted_resources:
            self.client.apply(obj)
        for patch in self._sorted_patches:
            self.client.patch(**patch)
        self._patch_service()

    def _patch_service(self):
        # Try to patch the service with juju 3.1 open_port
        # if this fails, try to use the K8S_Service_Patcher lib
        if not self.service_patcher.is_patched():
            try:
                args = self.service_port.protocol.lower(), self.service_port.port
                self._charm.unit.open_port(*args)
            except ModelError:
                self.service_patcher._patch()

    def delete_manifest(self, ignore_not_found=False, ignore_unauthorized=False):
        """Delete all manifests managed by this charm."""
        for obj in self._sorted_resources:
            self._delete_resource(
                type(obj),
                obj.metadata.name,
                namespace=obj.metadata.namespace,
                ignore_not_found=ignore_not_found,
                ignore_unauthorized=ignore_unauthorized,
            )
