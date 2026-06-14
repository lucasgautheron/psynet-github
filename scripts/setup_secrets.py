#!/usr/bin/env python3
"""Configure GitHub secrets for psynet-github integration deployment tests.

Run this from a local clone after authenticating the GitHub CLI:

    python scripts/setup_secrets.py --repo OWNER/psynet-github --use-gh-token

The GitHub token stored as PSYNET_GITHUB_TEST_TOKEN must be able to create and
delete disposable repositories and configure repository secrets in those
repositories.
"""

from __future__ import annotations

import argparse
import configparser
import getpass
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    args = parse_args()
    repo = args.repo or discover_current_repo()
    aws_credentials = read_aws_credentials(
        credentials_file=args.aws_credentials_file,
        profile=args.aws_profile,
    )
    github_token = resolve_github_token(args)

    set_secret(repo, "PSYNET_GITHUB_TEST_TOKEN", github_token)
    set_secret(repo, "AWS_ACCESS_KEY_ID", aws_credentials["AWS_ACCESS_KEY_ID"])
    set_secret(repo, "AWS_SECRET_ACCESS_KEY", aws_credentials["AWS_SECRET_ACCESS_KEY"])
    if aws_credentials.get("AWS_SESSION_TOKEN"):
        set_secret(repo, "AWS_SESSION_TOKEN", aws_credentials["AWS_SESSION_TOKEN"])
    else:
        delete_secret(repo, "AWS_SESSION_TOKEN")

    if args.test_owner:
        set_variable(repo, "PSYNET_GITHUB_TEST_OWNER", args.test_owner)
    if args.dns_domain:
        set_variable(repo, "PSYNET_GITHUB_TEST_DNS_DOMAIN", args.dns_domain)

    print(f"Configured integration-test secrets for {repo}.")
    if args.dns_domain:
        print(f"Configured PSYNET_GITHUB_TEST_DNS_DOMAIN={args.dns_domain}.")
    else:
        print(
            "No DNS domain variable was configured. Provide dns_host or dns_domain "
            "when dispatching the integration workflow."
        )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure psynet-github integration-test GitHub secrets."
    )
    parser.add_argument(
        "--repo",
        help="GitHub repository to configure, e.g. OWNER/psynet-github. Defaults to the current gh repo.",
    )
    parser.add_argument(
        "--aws-profile",
        default="default",
        help="AWS profile to read from the credentials file. Defaults to default.",
    )
    parser.add_argument(
        "--aws-credentials-file",
        type=Path,
        default=Path("~/.aws/credentials"),
        help="AWS credentials file. Defaults to ~/.aws/credentials.",
    )
    parser.add_argument(
        "--github-token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing the GitHub token to store as PSYNET_GITHUB_TEST_TOKEN.",
    )
    parser.add_argument(
        "--use-gh-token",
        action="store_true",
        help="Use `gh auth token` as PSYNET_GITHUB_TEST_TOKEN if --github-token-env is unset.",
    )
    parser.add_argument(
        "--github-token-stdin",
        action="store_true",
        help="Read PSYNET_GITHUB_TEST_TOKEN from stdin.",
    )
    parser.add_argument(
        "--test-owner",
        help="Optional GitHub owner/org for disposable repositories. Stored as a repository variable.",
    )
    parser.add_argument(
        "--dns-domain",
        help="Optional DNS domain for generated deployments. Stored as a repository variable.",
    )
    return parser.parse_args()


def discover_current_repo() -> str:
    result = run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture=True,
    )
    repo = result.stdout.strip()
    if not repo:
        raise SystemExit("Could not determine current GitHub repository; pass --repo.")
    return repo


def read_aws_credentials(
    *,
    credentials_file: Path,
    profile: str,
) -> dict[str, str]:
    path = credentials_file.expanduser()
    if not path.is_file():
        raise SystemExit(f"AWS credentials file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path)
    section_name = resolve_aws_profile_section(parser, profile)
    if section_name is None:
        raise SystemExit(f"AWS profile {profile!r} was not found in {path}.")

    section = parser[section_name]
    missing = [
        key
        for key in ("aws_access_key_id", "aws_secret_access_key")
        if not section.get(key, "").strip()
    ]
    if missing:
        raise SystemExit(
            f"AWS profile {profile!r} is missing required value(s): {', '.join(missing)}."
        )

    credentials = {
        "AWS_ACCESS_KEY_ID": section["aws_access_key_id"].strip(),
        "AWS_SECRET_ACCESS_KEY": section["aws_secret_access_key"].strip(),
    }
    session_token = section.get("aws_session_token", "").strip()
    if session_token:
        credentials["AWS_SESSION_TOKEN"] = session_token
    return credentials


def resolve_aws_profile_section(
    parser: configparser.ConfigParser,
    profile: str,
) -> str | None:
    candidates = [profile]
    if profile != "default":
        candidates.append(f"profile {profile}")

    for candidate in candidates:
        if parser.has_section(candidate):
            return candidate
    return None


def resolve_github_token(args: argparse.Namespace) -> str:
    if args.github_token_stdin:
        token = sys.stdin.read().strip()
    else:
        token = os.environ.get(args.github_token_env, "").strip()
        if not token and args.use_gh_token:
            token = run(["gh", "auth", "token"], capture=True).stdout.strip()
        if not token:
            token = getpass.getpass(
                "GitHub token for disposable repo creation/deletion and secret setup: "
            ).strip()

    if not token:
        raise SystemExit("A GitHub token is required.")
    return token


def set_secret(repo: str, name: str, value: str) -> None:
    run(["gh", "secret", "set", name, "--repo", repo], input_text=value)
    print(f"Set secret {name}.")


def set_variable(repo: str, name: str, value: str) -> None:
    run(["gh", "variable", "set", name, "--repo", repo, "--body", value])
    print(f"Set variable {name}.")


def delete_secret(repo: str, name: str) -> None:
    result = run(
        ["gh", "secret", "delete", name, "--repo", repo, "--yes"],
        check=False,
        capture=True,
    )
    if result.returncode == 0:
        print(f"Deleted stale secret {name}.")


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            input=input_text,
            text=True,
            check=check,
            capture_output=capture,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"Required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


if __name__ == "__main__":
    raise SystemExit(main())
