"""Digest charm configuration from application and relations."""
from dataclasses import dataclass, field


class ConfigError(Exception):
    """Raised when charm has a configuration error."""


@dataclass
class ControllerArgs:
    """Model command line arguments for the controller."""

    enable_healthz: str = "true"
    loglevel: int = 4
    extra_args: dict = field(default_factory=dict)

    @classmethod
    def load(cls, charm) -> "ControllerArgs":
        """Load controller args from charm config and relations."""
        return cls()
