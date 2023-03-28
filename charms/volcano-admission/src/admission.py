"""Establish handler for the sidecar container."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import yaml
from ops.model import Container
from ops.pebble import ExecError

from config import AdmissionArgs, AdmissionConfig

logger = logging.getLogger(__name__)
CONFIG_FILE = Path("/admission.local.config/volcano-admission.yaml")
TLS_CERT = Path("/admission.local.config/certificates/tls.crt")
TLS_PRIVATE_KEY = Path("/admission.local.config/certificates/tls.key")
TLS_CA_CERT = Path("/admission.local.config/certificates/ca.crt")

@dataclass
class Admission:
    """Update Pebble config based on charm config and relations."""

    config: AdmissionConfig = None
    command: str = ""

    def _build_command(self, charm, args: AdmissionArgs):
        enabled_admission = f"--enabled-admission={','.join(args.admissions)}"
        tls_cert_file = f"--tls-cert-file={TLS_CERT}"
        tls_private_key_file = f"--tls-private-key-file={TLS_PRIVATE_KEY}"
        ca_cert_file = f"--ca-cert-file={TLS_CA_CERT}"
        conf = f"--admission-conf={CONFIG_FILE}"
        webhook_namespace = f"--webhook-namespace={charm.model.name}"
        webhook_service_name = f"--webhook-service-name={charm.app.name}"
        logredirect = "--logtostderr"
        port = f"--port={args.admission_port}"
        loglevel = f"-v={args.loglevel}"

        extra_args = args.extra_args
        extra = ""
        if extra_args:
            extra = " " + " ".join(
                sorted(f"--{key}='{value}'" for key, value in extra_args.items())
            )

        self.command = (
            f"{self.binary} {enabled_admission} {tls_cert_file} {tls_private_key_file} {ca_cert_file} {conf} {webhook_namespace} {webhook_service_name} {logredirect} {port} {loglevel}{extra} 2>&1"
        )
        return self

    def apply(self, charm, config, args):
        """Update commandline for container."""
        self._build_command(charm, args)
        self.config = config
        return self

    def restart(self, container):
        """Update pebble layer for container."""
        root_rw = dict(permissions=0o644, user_id=0, group_id=0)
        container.add_layer(container.name, self._layer, combine=True)
        container.push(*self.config_file, make_dirs=True, **root_rw)
        container.push(*self.tls_cert_file, make_dirs=True, **root_rw)
        container.push(*self.tls_key_file, make_dirs=True, **root_rw)
        container.push(*self.ca_cert_file, make_dirs=True, **root_rw)
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
        """List expected binary in webhook-manager container."""
        return Path("/", "vc-webhook-manager")

    @property
    def config_file(self) -> Tuple[str, str]:
        """Generate admission conf file."""
        return str(CONFIG_FILE), yaml.safe_dump(self.config and self.config.asdict())

    @property
    def tls_cert_file(self) -> Tuple[str, str]:
        """Generate reflect cert file."""
        return str(TLS_CERT), ""

    @property
    def tls_key_file(self) -> Tuple[str, str]:
        """Generate private key file."""
        return str(TLS_PRIVATE_KEY), ""

    @property
    def ca_cert_file(self) -> Tuple[str, str]:
        """Generate ca cert file."""
        return str(TLS_CA_CERT), ""
