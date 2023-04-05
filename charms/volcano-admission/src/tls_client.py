"""Various ways for the admission webhook service to request a TLS cert package."""

import logging
from pathlib import Path
from typing import List

from ops.charm import CharmBase
from ops.interface_tls_certificates.requires import CertificatesRequires
from ops.pebble import Client as Container
from ops.pebble import ExecError

log = logging.getLogger(__name__)


class CertificateError(Exception):
    """Raised when charm has an issue placing the certificate."""


class TLSClient:
    """Base class for retrieving tls package files."""

    CERTS = Path("/admission.local.config/certificates")

    @property
    def cert(self) -> Path:
        """Path to tls certificate."""
        return self.CERTS / "server.crt"

    @property
    def private_key(self) -> Path:
        """Path to private key file."""
        return self.CERTS / "server.key"

    @property
    def ca_cert(self) -> Path:
        """Path to ca cert file."""
        return self.CERTS / "ca.crt"

    def prepare(self, container: Container) -> None:
        """Adjust the sidecar container to include the cert package."""
        ...  # pragma: no cover

    @property
    def available(self) -> bool:
        """Determine if the certificate package is ready."""
        ...  # pragma: no cover


class TLSSelfSigned(TLSClient):
    """Handles generating self-signed certs package within the sidecar."""

    def __init__(self, charm: CharmBase) -> None:
        self._binary = "/gen-admission-certs.sh"
        self._args: List[str] = [
            "--service",
            charm.app.name,
            "--namespace",
            charm.model.name,
        ]

    @property
    def _content(self) -> str:
        return Path("templates", self._binary[1:]).read_text()

    def prepare(self, container: Container):
        """Run generate script in sidecar."""
        log.info("Generating certs in sidecar.")
        container.push(
            self._binary,
            self._content,
            permissions=0o755,
            user_id=0,
            group_id=0,
        )
        process = container.exec([self._binary] + self._args)
        try:
            stdout, stderr = process.wait_output()
        except ExecError as e:
            log.exception(f"Failed to create certificates: {e.stdout}\n{e.stderr}")
            raise
        log.info(f"{stdout}\n-----------\n{stderr}")

    @property
    def available(self):
        """Always ready to generate self-signed certs."""
        return True


class TLSRelation(TLSClient):
    """Request certificate package via the tls-interface relation."""

    def __init__(self, charm: CharmBase, relation: CertificatesRequires):
        self._relation = relation
        self._charm = charm
        self._common_name = f"{self._charm.app.name}.{self._charm.model.name}"
        self._sans = [  # list of DNS names to reach this service
            self._charm.app.name,
            self._common_name,
            f"{self._common_name}.svc",
        ]

    def request(self):
        """Generate certs based on the app and model name."""
        self._relation.request_server_cert(
            self._common_name,
            self._sans,
        )

    def prepare(self, container: Container):
        """Copy server cert into the admission container."""
        log.info("Copying certs from relation into sidecar.")
        cert = self._relation.server_certs_map[self._common_name]
        root_rw = dict(make_dirs=True, permissions=0o644, user_id=0, group_id=0)
        container.push(self.ca_cert, self._relation.ca, **root_rw)
        container.push(self.cert, cert.cert, **root_rw)
        container.push(self.private_key, cert.key, **root_rw)

    @property
    def available(self):
        """Cert is available when it appears in the certs map."""
        return self._common_name in self._relation.server_certs_map
