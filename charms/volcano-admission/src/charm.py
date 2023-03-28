#!/usr/bin/env python3
# Copyright 2023 Adam Dyess
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.pebble import ConnectionError

from config import ConfigError, AdmissionArgs, AdmissionConfig
from manifests import Manifests
from admission import Admission

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class CharmVolcano(CharmBase):
    """Charm the service."""

    CONTAINER = "volcano"

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.upgrade_charm, self._install_or_upgrade)
        self.framework.observe(self.on.volcano_pebble_ready, self._install_or_upgrade)
        self.framework.observe(self.on.update_status, self._update_status)
        self.framework.observe(self.on.leader_elected, self._set_version)
        self.framework.observe(self.on.stop, self._cleanup)

    def _update_status(self, _event):
        container = self.model.unit.get_container(self.CONTAINER)
        if not container or not container.can_connect():
            self.unit.status = WaitingStatus("Admission Not Ready")
        else:
            self.unit.status = ActiveStatus()

    def _install_or_upgrade(self, event):
        admission = Admission()

        try:
            app_args = AdmissionArgs.load(self)
            app_config = AdmissionConfig.load(self)
            admission.apply(self, app_config, app_args)
        except ConfigError as e:
            self.unit.status = BlockedStatus(str(e))
            return

        container = self.model.unit.get_container(self.CONTAINER)
        if not container or not container.can_connect():
            self.unit.status = WaitingStatus("Admission Not Ready")
            return

        if not admission.executable(container):
            self.unit.status = BlockedStatus(f"Image missing executable: {admission.binary}")
            return

        manifests = Manifests(self)
        if self.unit.is_leader():
            manifests.apply()

        try:
            admission.restart(container)
        except ConnectionError:
            self.unit.status = WaitingStatus("Failed to connect to admission")
            event.defer()
            return

        self.unit.status = MaintenanceStatus("Waiting for admission to start")

    def _set_version(self, _event=None):
        if not self.unit.is_leader():
            return

        container = self.model.unit.get_container(self.CONTAINER)
        if not container or not container.can_connect():
            return

        version = Admission().version(container)
        self.unit.set_workload_version(version)

    def _cleanup(self, _):
        cont = self.model.unit.get_container(self.CONTAINER)
        if cont and cont.can_connect() and cont.get_services(cont.name):
            cont.stop(cont.name)

        self.unit.status = WaitingStatus("Shutting down")
        manifests = Manifests(self)
        if self.unit.is_leader():
            manifests.delete_manifest(ignore_unauthorized=True, ignore_not_found=True)

if __name__ == "__main__":  # pragma: nocover
    main(CharmVolcano)
