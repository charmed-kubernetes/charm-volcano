"""Establish handler for the sidecar container."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import yaml
from ops.model import Container
from ops.pebble import ExecError

from config import AdmissionArgs, AdmissionConfig
from tls_client import CertificateError, TLSClient

logger = logging.getLogger(__name__)
CONFIG_FILE = Path("/admission.local.config/volcano-admission.yaml")


@dataclass
class Admission:
    """Update Pebble config based on charm config and relations."""

    tls: TLSClient = None
    config: AdmissionConfig = None
    command: str = ""

    @property
    def _certificate_args(self) -> List[str]:
        tls_cert_file = f"--tls-cert-file={self.tls.cert}"
        tls_private_key_file = f"--tls-private-key-file={self.tls.private_key}"
        ca_cert_file = f"--ca-cert-file={self.tls.ca_cert}"
        return [tls_cert_file, tls_private_key_file, ca_cert_file]

    def _build_command(self, charm, args: AdmissionArgs):
        enabled_admission = f"--enabled-admission={','.join(args.admissions)}"
        conf = f"--admission-conf={CONFIG_FILE}"
        webhook_namespace = f"--webhook-namespace={charm.model.name}"
        webhook_service_name = f"--webhook-service-name={charm.app.name}"
        logredirect = "--logtostderr"
        port = f"--port={args.admission_port}"
        loglevel = f"-v={args.loglevel}"
        certs = " ".join(self._certificate_args)

        extra_args = args.extra_args
        extra = ""
        if extra_args:
            extra = " " + " ".join(
                sorted(f"--{key}='{value}'" for key, value in extra_args.items())
            )

        self.command = f"{self.binary} {enabled_admission} {certs} {conf} {webhook_namespace} {webhook_service_name} {logredirect} {port} {loglevel}{extra} 2>&1"
        return self

    def apply(self, charm, tls, config, args):
        """Update commandline for container."""
        self.config = config
        self.tls = tls
        self._build_command(charm, args)
        return self

    def restart(self, container):
        """Update pebble layer for container."""
        root_rw = dict(permissions=0o644, user_id=0, group_id=0)
        container.add_layer(container.name, self._layer, combine=True)
        container.push(*self.config_file, make_dirs=True, **root_rw)
        if not self.tls.available:
            raise CertificateError()
        self.tls.prepare(container)
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
        process = container.exec([str(self.binary), "--version"] + self._certificate_args)
        try:
            version_str, _ = process.wait_output()
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
        """List expected binary in webhook-manager container."""
        return Path("/", "vc-webhook-manager")

    @property
    def config_file(self) -> Tuple[str, str]:
        """Generate admission conf file."""
        return str(CONFIG_FILE), yaml.safe_dump(self.config and self.config.asdict())
