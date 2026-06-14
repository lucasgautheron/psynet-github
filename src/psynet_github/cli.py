from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .create import CreateError, CreateOptions, create_experiment_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="psynet-github",
        description="Create GitHub repositories containing starter PsyNet experiments.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser(
        "create",
        help="Create and push a starter PsyNet experiment repository.",
    )
    create_parser.add_argument(
        "repository",
        help="Repository name, owner/name slug, or GitHub URL.",
    )
    create_parser.add_argument(
        "--owner",
        help="GitHub owner or organization. Not needed when repository is owner/name.",
    )
    create_parser.add_argument(
        "--description",
        default="",
        help="GitHub repository description and generated README summary.",
    )
    create_parser.add_argument(
        "--directory",
        type=Path,
        help="Local directory to create. Defaults to ./<repository-name>.",
    )
    create_parser.add_argument(
        "--public",
        action="store_true",
        help="Create a public repository. Repositories are private by default.",
    )
    create_parser.add_argument(
        "--default-branch",
        default="main",
        help="Initial branch name for the local repository. Defaults to main.",
    )
    create_parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote name to configure via gh. Defaults to origin.",
    )
    create_parser.add_argument(
        "--no-github",
        action="store_true",
        help="Only create the local starter repository; do not call gh or push.",
    )
    create_parser.add_argument(
        "--no-git",
        action="store_true",
        help="Only render files; do not initialize git. Implies --no-github.",
    )
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow writing template files into an existing non-empty directory.",
    )
    create_parser.set_defaults(func=run_create)
    return parser


def run_create(args: argparse.Namespace) -> int:
    no_github = args.no_github or args.no_git
    result = create_experiment_repository(
        CreateOptions(
            repository=args.repository,
            directory=args.directory,
            owner=args.owner,
            description=args.description,
            private=not args.public,
            default_branch=args.default_branch,
            remote=args.remote,
            no_github=no_github,
            no_git=args.no_git,
            force=args.force,
        )
    )

    print(f"Created PsyNet experiment template in {result.directory}")
    if result.initialized_git:
        print("Initialized git repository and committed the starter experiment.")
    if result.pushed_to_github:
        print(f"Created and pushed GitHub repository {result.repository.full_name}.")
    else:
        print("Skipped GitHub repository creation.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CreateError as exc:
        print(f"psynet-github: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
