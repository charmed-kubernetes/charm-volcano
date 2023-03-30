"""Digest charm configuration from application and relations."""
from dataclasses import asdict, dataclass, field
from typing import Any, List, Mapping, Optional, TypedDict

from lightkube.models.core_v1 import Toleration


class ConfigError(Exception):
    """Raised when charm has a configuration error."""


class ResourceObject(TypedDict):
    """Model config for the Admission plugin."""

    key: str
    value: List[str]


class ResourceGroup(TypedDict):
    """Model config for the Resource Group list."""

    resourceGroup: str
    schedulerName: str
    labels: dict
    object: Optional[ResourceObject]
    tolerations: Optional[Toleration]


@dataclass
class AdmissionConfig:
    """Model config for the Admission."""

    resourceGroups: List[ResourceGroup]

    @classmethod
    def load(cls, charm) -> "AdmissionConfig":
        """Load scheduler config from charm config and relations."""
        return DEFAULT_CONFIG

    def asdict(self) -> Mapping[str, Any]:
        """Return config as a mapping."""
        return asdict(self)


DEFAULT_CONFIG = AdmissionConfig(resourceGroups=[])


@dataclass
class AdmissionArgs:
    """Model command line arguments for the admission."""

    admissions: List[str] = field(
        default_factory=lambda : [
            "/jobs/mutate",
            "/jobs/validate",
            "/podgroups/mutate",
            "/pods/validate",
            "/queues/mutate",
            "/queues/validate",
        ]
    )
    loglevel: int = 4
    extra_args: dict = field(default_factory=dict)
    admission_port: int = 8443

    @classmethod
    def load(cls, charm) -> "AdmissionArgs":
        """Load admission args from charm config and relations."""
        return cls()
