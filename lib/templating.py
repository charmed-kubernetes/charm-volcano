#!/usr/bin/env python3
# Copyright 2023 Adam Dyess
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Templating library.

Creates charm manifests from templates, config files, and context
"""


import re
from argparse import ArgumentParser
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Sequence, Union

import yaml
from jinja2 import Environment, FileSystemLoader

"""
Helper methods to adapt volcano charts `/installer/helm/chart/volcano`
from helm to rendered by jinja.
"""


@dataclass
class _FileBody:
    path: Path

    @property
    def AsConfig(self) -> str:  # noqa: N802
        """Returns file bodies as a YAML map."""
        return yaml.safe_dump(
            {self.path.name: self.path.read_text()},
            default_style="|",
        )


def _glob(basedir: Path, value: str) -> _FileBody:
    """Implement helm `Files.Glob`.

    Replacement Helm to Jinja:

    {{- (.Files.Glob .Values.basic.admission_config_file).AsConfig | nindent 2}}
    becomes
    {{ Files.glob(Values.basic.admission_config_file).AsConfig | indent(2) }}
    """
    return _FileBody(basedir / value)


def _base(value: str) -> str:
    """Implement helm `Base`.

    Replacement Helm to Jinja:

    {{base .Values.basic.admission_config_file}}
    becomes
    {{base(Values.basic.admission_config_file)}}
    """
    return Path(value).name


def _regex_match(value: str, regex: str) -> str:
    """Implement helm `regexMatch`.

    Replacement Helm to Jinja:

    {{- if .Values.custom.enabled_admissions | regexMatch "/pods/mutate" }}
    becomes
    {% if Values.custom.enabled_admissions | regexMatch("/pods/mutate") -%}
    """
    return re.findall(regex, value)


"""
-------------------------------------------------------------------------------
"""


def render_templates(
    basedir: Path, *templates: Path, context: Union[dict, None] = None
) -> Sequence[str]:
    """Render a set of charm templates returning as an sequence of str.

    @param Path basedir: base directory where Files.Glob can find config files
    @param Path templates: set of templates to render with the given context
    @param dict context: key-value pairs used to render the templates.
    """
    if context is None:
        context = {}

    env = Environment(loader=FileSystemLoader("/"))

    # Similar method to
    # https://helm.sh/docs/chart_template_guide/function_list/#regexmatch-mustregexmatch
    env.filters["regexMatch"] = _regex_match

    # Similar methods to
    # https://helm.sh/docs/chart_template_guide/accessing_files/#glob-patterns
    context["Files"] = dict(glob=partial(_glob, basedir))

    # Similar method to
    # https://helm.sh/docs/chart_template_guide/accessing_files/#path-helpers
    context["base"] = _base

    return (
        env.get_template(str(tmp_file.resolve())).render(context)
        for tmp_file in templates
    )


if __name__ == "__main__":
    """
    When run as standalone, print all the rendered templates to stdout
    """
    parser = ArgumentParser()
    parser.add_argument("templates", type=Path, nargs="*")
    parser.add_argument("--name", type=str, required=True)
    parser.add_argument("--namespace", type=str, required=True)
    parser.add_argument("--values", type=Path, default=Path("values.yaml"))
    parser.add_argument("--basedir", type=Path, default=Path())
    args = parser.parse_args()

    context = {
        "Values": yaml.safe_load((args.basedir / args.values).read_text()),
        "Release": {
            "Name": args.name,
            "Namespace": args.namespace,
        },
    }

    for each in render_templates(args.basedir, *args.templates, context=context):
        print(each)
        print("---")
