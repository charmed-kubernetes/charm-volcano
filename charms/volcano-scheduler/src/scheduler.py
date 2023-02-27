import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, TypedDict

import yaml

logger = logging.getLogger(__name__)
CONFIG_FILE = Path("/", "volcano.scheduler", "volcano-scheduler.yaml")


class SchedulerPlugin(TypedDict):
    name: str
    enablePreemptable: bool = True


class SchedulerPlugins(TypedDict):
    plugins: List[SchedulerPlugin]


class SchedulerConfig(TypedDict):
    actions: str
    tiers: List[SchedulerPlugins]

    @classmethod
    def load(cls, charm):
        return DEFAULT_CONFIG


@dataclass
class SchedulerArgs:
    enable_healthz: str = "true"
    enable_metrics: str = "false"
    loglevel: int = 3
    extra_args: dict = field(default_factory=dict)

    @classmethod
    def load(cls, charm):
        return cls()


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
class Scheduler:
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
            extra = " " + " ".join(sorted(f"--{key}='{value}'" for key, value in extra_args))

        self.command = (
            f"{self.binary} {logredirect} {conf} {healthz} {metrics} {loglevel}{extra} 2>&1"
        )
        return self

    def apply(self, charm, config, args):
        self._build_command(charm, args)
        self.config = config
        return self

    def authorize(self, container):
        container.add_layer(container.name, self.layer, combine=True)
        container.push(*self.config_file, make_dirs=True, **self.root_owned)

    @property
    def layer(self):
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
                }
            },
        }

    @property
    def binary(self):
        return Path("/", "vc-scheduler")

    @property
    def root_owned(self):
        return dict(permissions=0o600, user_id=0, group_id=0)

    @property
    def config_file(self) -> Tuple[str, str]:
        return str(CONFIG_FILE), yaml.safe_dump(self.config)
