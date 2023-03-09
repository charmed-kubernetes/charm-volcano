"""Establish handler for the sidecar container."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import yaml
from ops.model import Container
from ops.pebble import ExecError

from config import SchedulerArgs, SchedulerConfig

logger = logging.getLogger(__name__)
CONFIG_FILE = Path("/", "volcano.scheduler", "volcano-scheduler.yaml")


@dataclass
class Scheduler:
    """Update Pebble config based on charm config and relations."""

    config: SchedulerConfig = None
    command: str = ""

    def _build_command(self, charm, args: SchedulerArgs):
        logredirect = "--logtostderr"
        conf = f"--scheduler-conf={CONFIG_FILE}"
        healthz = f"--enable-healthz={args.enable_healthz}"
        metrics = f"--enable-metrics={args.enable_metrics}"
        loglevel = f"-v={args.loglevel}"

        extra_args = args.extra_args
        extra = ""
        if extra_args:
            extra = " " + " ".join(
                sorted(f"--{key}='{value}'" for key, value in extra_args.items())
            )

        self.command = (
            f"{self.binary} {logredirect} {conf} {healthz} {metrics} {loglevel}{extra} 2>&1"
        )
        return self

    def apply(self, charm, config, args):
        """Update commandline for container."""
        self._build_command(charm, args)
        self.config = config
        return self

    def restart(self, container):
        """Update pebble layer for container."""
        root_owned = dict(permissions=0o600, user_id=0, group_id=0)
        container.add_layer(container.name, self._layer, combine=True)
        container.push(*self.config_file, make_dirs=True, **root_owned)
        container.autostart()
        container.restart(container.name)

    def executable(self, container) -> bool:
        """Check if container has the appropriate executable."""
        path, file = self.binary.parent, self.binary.name
        files = container.list_files(path, pattern=file + "*")
        return bool(files)

    def version(self, container: Container) -> str:
        """Get version from the container."""
        if not self.executable(container):
            logger.warning("Cannot fetch version without executable")
            return "Unknown"
        process = container.exec([str(self.binary), "--version"])
        try:
            version_str, error = process.wait_output()
        except ExecError as e:
            logger.error(f"Failed to get version: {e}")
            return "Unknown"
        for line in version_str.splitlines():
            if line.startswith("Version:"):
                _, r = line.split(":", 1)
                return r.strip()
        logger.error(f"Failed to parse version: \n{version_str}")
        return "Unknown"

    @property
    def _layer(self):
        logger.info("starting volcano binary with command %s", self.command)
        return {
            "summary": "volcano service layer",
            "description": "pebble config layer for volcano service",
            "services": {
                "volcano": {
                    "override": "replace",
                    "summary": "volcano",
                    "command": self.command,
                    "startup": "enabled",
                },
            },
        }

    @property
    def binary(self):
        """List expected binary in scheduler container."""
        return Path("/", "vc-scheduler")

    @property
    def config_file(self) -> Tuple[str, str]:
        """Generate scheduler conf file."""
        return str(CONFIG_FILE), yaml.safe_dump(self.config and self.config.asdict())
