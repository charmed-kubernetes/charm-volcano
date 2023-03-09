"""Digest charm configuration from application and relations."""
from dataclasses import asdict, dataclass, field
from typing import Any, List, Mapping, TypedDict


class ConfigError(Exception):
    """Raised when charm has a configuration error."""


class SchedulerPlugin(TypedDict):
    """Model config for the Scheduler plugin."""

    name: str


class SchedulerPlugins(TypedDict):
    """Model config for the Scheduler plugin list."""

    plugins: List[SchedulerPlugin]


@dataclass
class SchedulerConfig:
    """Model config for the Scheduler."""

    actions: str
    tiers: List[SchedulerPlugins]

    @classmethod
    def load(cls, charm) -> "SchedulerConfig":
        """Load scheduler config from charm config and relations."""
        return DEFAULT_CONFIG

    def asdict(self) -> Mapping[str, Any]:
        """Return config as a mapping."""
        return asdict(self)


DEFAULT_CONFIG = SchedulerConfig(
    actions="enqueue, allocate, backfill",
    tiers=[
        SchedulerPlugins(
            plugins=[
                SchedulerPlugin(name="priority"),
                SchedulerPlugin(name="gang", enablePreemptable=False),
                SchedulerPlugin(name="conformance"),
            ]
        ),
        SchedulerPlugins(
            plugins=[
                SchedulerPlugin(name="overcommit"),
                SchedulerPlugin(name="drf", enablePreemptable=False),
                SchedulerPlugin(name="predicates"),
                SchedulerPlugin(name="proportion"),
                SchedulerPlugin(name="nodeorder"),
                SchedulerPlugin(name="binpack"),
            ]
        ),
    ],
)


@dataclass
class SchedulerArgs:
    """Model command line arguments for the scheduler."""

    enable_healthz: str = "true"
    enable_metrics: str = "false"
    loglevel: int = 3
    extra_args: dict = field(default_factory=dict)

    @classmethod
    def load(cls, charm) -> "SchedulerArgs":
        """Load scheduler args from charm config and relations."""
        return cls()
