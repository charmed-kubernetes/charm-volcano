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

from config import ConfigError, ControllerArgs
from controller import Controller
from manifests import Manifests

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
        controller = Controller()

        try:
            app_args = ControllerArgs.load(self)
            controller.apply(self, app_args)
        except ConfigError as e:
            self.unit.status = BlockedStatus(str(e))
            return

        container = self.model.unit.get_container(self.CONTAINER)
        if not container or not container.can_connect():
            self.unit.status = WaitingStatus("Controller Not Ready")
            return

        if not controller.executable(container):
            self.unit.status = BlockedStatus(f"Image missing executable: {controller.binary}")
            return

        manifests = Manifests(self)
        if self.unit.is_leader():
            manifests.apply()

        try:
            controller.restart(container)
        except ConnectionError:
            self.unit.status = WaitingStatus("Failed to connect to controller")
            event.defer()
            return

        self.unit.status = MaintenanceStatus("Waiting for controller to start")

    def _set_version(self, _event=None):
        if not self.unit.is_leader():
            return

        container = self.model.unit.get_container(self.CONTAINER)
        if not container or not container.can_connect():
            return

        version = Controller().version(container)
        self.unit.set_workload_version(version)

    def _cleanup(self, _):
        cont = self.model.unit.get_container(self.CONTAINER)
        if cont and cont.can_connect() and cont.get_services(cont.name):
            cont.stop(cont.name)

        self.unit.status = WaitingStatus("Shutting down")


if __name__ == "__main__":  # pragma: nocover
    main(CharmVolcano)
