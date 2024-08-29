# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import argparse
import json

from pathlib import Path

import yaml

from llama_toolchain.cli.subcommand import Subcommand
from llama_toolchain.common.config_dirs import BUILDS_BASE_DIR
from llama_toolchain.core.datatypes import *  # noqa: F403


class ApiConfigure(Subcommand):
    """Llama cli for configuring llama toolchain configs"""

    def __init__(self, subparsers: argparse._SubParsersAction):
        super().__init__()
        self.parser = subparsers.add_parser(
            "configure",
            prog="llama api configure",
            description="configure a llama stack API provider",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        self._add_arguments()
        self.parser.set_defaults(func=self._run_api_configure_cmd)

    def _add_arguments(self):
        from llama_toolchain.core.distribution import stack_apis
        from llama_toolchain.core.package import BuildType

        allowed_args = [a.name for a in stack_apis()]
        self.parser.add_argument(
            "api",
            choices=allowed_args,
            help="Stack API (one of: {})".format(", ".join(allowed_args)),
        )
        self.parser.add_argument(
            "--build-name",
            type=str,
            help="(Fully qualified) name of the API build to configure. Alternatively, specify the --provider and --name options.",
            required=False,
        )

        self.parser.add_argument(
            "--provider",
            type=str,
            help="The provider chosen for the API",
            required=False,
        )
        self.parser.add_argument(
            "--name",
            type=str,
            help="Name of the build target (image, conda env)",
            required=False,
        )
        self.parser.add_argument(
            "--type",
            type=str,
            default="conda_env",
            choices=[v.value for v in BuildType],
        )

    def _run_api_configure_cmd(self, args: argparse.Namespace) -> None:
        from llama_toolchain.core.package import BuildType

        if args.build_name:
            name = args.build_name
            if name.endswith(".yaml"):
                name = name.replace(".yaml", "")
        else:
            build_type = BuildType(args.type)
            name = f"{build_type.descriptor()}-{args.provider}-{args.name}"

        config_file = BUILDS_BASE_DIR / args.api / f"{name}.yaml"
        if not config_file.exists():
            self.parser.error(
                f"Could not find {config_file}. Please run `llama api build` first"
            )
            return

        configure_llama_provider(config_file)


def configure_llama_provider(config_file: Path) -> None:
    from llama_toolchain.common.serialize import EnumEncoder
    from llama_toolchain.core.configure import configure_api_providers

    with open(config_file, "r") as f:
        config = PackageConfig(**yaml.safe_load(f))

    config.providers = configure_api_providers(config.providers)

    with open(config_file, "w") as fp:
        to_write = json.loads(json.dumps(config.dict(), cls=EnumEncoder))
        fp.write(yaml.dump(to_write, sort_keys=False))

    print(f"YAML configuration has been written to {config_file}")
