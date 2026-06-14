from __future__ import annotations

import configparser
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse


CommandRunner = Callable[[Sequence[str], Path | None, str | None], None]

GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
AWS_SECRET_NAMES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)
EC2_SSH_SECRET_NAME = "EC2_SSH_PRIVATE_KEY"


class CreateError(RuntimeError):
    """Raised when a PsyNet GitHub repository cannot be created safely."""


@dataclass(frozen=True)
class RepositorySpec:
    """Normalized GitHub repository reference."""

    name: str
    owner: str | None = None

    @property
    def full_name(self) -> str:
        if self.owner:
            return f"{self.owner}/{self.name}"
        return self.name


@dataclass(frozen=True)
class CreateOptions:
    """Options used by the create command."""

    repository: str
    directory: Path | None = None
    owner: str | None = None
    description: str = ""
    private: bool = True
    default_branch: str = "main"
    remote: str = "origin"
    no_github: bool = False
    no_git: bool = False
    force: bool = False
    set_aws_secrets: bool = False
    aws_profile: str = "default"
    aws_credentials_file: Path | None = None
    generate_ec2_ssh_key: bool = True
    ec2_ssh_key_path: Path | None = None


@dataclass(frozen=True)
class CreateResult:
    """Information about a rendered PsyNet experiment repository."""

    repository: RepositorySpec
    directory: Path
    initialized_git: bool
    pushed_to_github: bool
    configured_secrets: tuple[str, ...] = ()
    ec2_ssh_private_key_path: Path | None = None


def create_experiment_repository(
    options: CreateOptions,
    *,
    runner: CommandRunner | None = None,
) -> CreateResult:
    """Create a starter PsyNet experiment repository and optionally push it.

    The command renders files before invoking any external commands. That keeps
    template creation testable and ensures failures from `git` or `gh` leave a
    complete local project for inspection.
    """

    repository = parse_repository(options.repository, owner=options.owner)
    target_dir = resolve_target_directory(repository, options.directory)
    command_runner = runner or run_command
    no_github = options.no_github or options.no_git
    if options.set_aws_secrets and no_github:
        raise CreateError("--set-aws-secrets requires GitHub repository creation.")

    render_template(
        target_dir,
        context={
            "repo_name": repository.name,
            "repo_full_name": repository.full_name,
            "project_title": humanize_repo_name(repository.name),
            "description": options.description
            or "A starter PsyNet experiment created with psynet-github.",
            "default_branch": options.default_branch,
        },
        force=options.force,
    )

    initialized_git = False
    pushed_to_github = False
    configured_secrets: tuple[str, ...] = ()
    ec2_ssh_private_key_path: Path | None = None

    if options.generate_ec2_ssh_key:
        ec2_ssh_private_key_path = resolve_ec2_ssh_key_path(
            target_dir,
            repository,
            options.ec2_ssh_key_path,
        )
        generate_ec2_ssh_key(ec2_ssh_private_key_path, repository, command_runner)

    if not options.no_git:
        initialize_git_repository(target_dir, options.default_branch, command_runner)
        initialized_git = True

    if not no_github:
        create_github_repository(
            repository,
            target_dir,
            options,
            command_runner,
        )
        pushed_to_github = True
        configured_secrets = configure_github_secrets(
            target_dir,
            github_secrets_for_options(options, ec2_ssh_private_key_path),
            command_runner,
        )

    return CreateResult(
        repository=repository,
        directory=target_dir,
        initialized_git=initialized_git,
        pushed_to_github=pushed_to_github,
        configured_secrets=configured_secrets,
        ec2_ssh_private_key_path=ec2_ssh_private_key_path,
    )


def parse_repository(value: str, *, owner: str | None = None) -> RepositorySpec:
    """Parse a repository name, owner/name slug, or GitHub URL."""

    normalized = value.strip()
    if not normalized:
        raise CreateError("Repository name cannot be empty.")

    parsed = urlparse(normalized)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.removesuffix(".git").strip("/")
        parts = path.split("/")
    else:
        parts = normalized.removesuffix(".git").strip("/").split("/")

    if len(parts) == 1:
        repo_owner = owner
        repo_name = parts[0]
    elif len(parts) == 2:
        if owner and owner != parts[0]:
            raise CreateError(
                f"Owner was provided as both {owner!r} and {parts[0]!r}."
            )
        repo_owner, repo_name = parts
    else:
        raise CreateError(
            "Repository must be a name, an owner/name slug, or a GitHub URL."
        )

    validate_github_component(repo_name, "repository name")
    if repo_owner is not None:
        validate_github_component(repo_owner, "owner")

    return RepositorySpec(name=repo_name, owner=repo_owner)


def validate_github_component(value: str, label: str) -> None:
    if not GITHUB_REPO_RE.match(value):
        raise CreateError(
            f"Invalid {label} {value!r}; use only letters, numbers, '.', '_', and '-'."
        )


def resolve_target_directory(repository: RepositorySpec, directory: Path | None) -> Path:
    if directory is not None:
        return directory.expanduser().resolve()
    return Path.cwd().joinpath(repository.name).resolve()


def render_template(
    target_dir: Path,
    *,
    context: Mapping[str, str],
    force: bool = False,
) -> None:
    """Render package-data templates into `target_dir`."""

    if target_dir.exists():
        if not target_dir.is_dir():
            raise CreateError(f"Target path exists and is not a directory: {target_dir}")
        if any(target_dir.iterdir()) and not force:
            raise CreateError(
                f"Target directory is not empty: {target_dir}. Use --force to write into it."
            )
    else:
        target_dir.mkdir(parents=True)

    templates_root = resources.files("psynet_github").joinpath("templates")
    for relative_parts, source_path in walk_resources(templates_root):
        destination_path = target_dir.joinpath(*decode_template_parts(relative_parts))
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        text = source_path.read_text(encoding="utf-8")
        destination_path.write_text(replace_tokens(text, context), encoding="utf-8")


def walk_resources(root) -> Iterable:
    for entry in root.iterdir():
        if entry.is_dir():
            for relative_parts, source_path in walk_resources(entry):
                yield (entry.name, *relative_parts), source_path
        else:
            yield (entry.name,), entry


def decode_template_parts(parts: Iterable[str]) -> list[str]:
    decoded = []
    for part in parts:
        if part.startswith("__dot__"):
            decoded.append(f".{part.removeprefix('__dot__')}")
        else:
            decoded.append(part)
    return decoded


def replace_tokens(text: str, context: Mapping[str, str]) -> str:
    for key, value in context.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def humanize_repo_name(name: str) -> str:
    words = re.split(r"[-_]+", name)
    return " ".join(word.capitalize() for word in words if word) or name


def default_ec2_ssh_key_name(repository: RepositorySpec) -> str:
    return f"{repository.name}-ec2"


def resolve_ec2_ssh_key_path(
    target_dir: Path,
    repository: RepositorySpec,
    configured_path: Path | None,
) -> Path:
    if configured_path is not None:
        path = configured_path.expanduser()
        if not path.is_absolute():
            path = target_dir / path
        return path.resolve()

    return target_dir.joinpath(
        ".deploy",
        "ssh",
        f"{default_ec2_ssh_key_name(repository)}.pem",
    ).resolve()


def generate_ec2_ssh_key(
    private_key_path: Path,
    repository: RepositorySpec,
    runner: CommandRunner,
) -> None:
    """Generate a unique RSA keypair for Dallinger EC2 SSH deployment."""

    public_key_path = public_key_path_for_private_key(private_key_path)
    if private_key_path.exists() or public_key_path.exists():
        raise CreateError(
            f"EC2 SSH key already exists at {private_key_path} or {public_key_path}."
        )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    runner(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "rsa",
            "-b",
            "4096",
            "-m",
            "PEM",
            "-N",
            "",
            "-C",
            f"psynet-github:{repository.full_name}",
            "-f",
            str(private_key_path),
        ],
        private_key_path.parent,
        None,
    )
    if private_key_path.exists():
        private_key_path.chmod(0o600)


def public_key_path_for_private_key(private_key_path: Path) -> Path:
    return private_key_path.with_name(f"{private_key_path.name}.pub")


def initialize_git_repository(
    target_dir: Path,
    default_branch: str,
    runner: CommandRunner,
) -> None:
    """Initialize a git repository and create the starter commit."""

    runner(["git", "init", "-b", default_branch], target_dir, None)
    runner(["git", "add", "."], target_dir, None)
    runner(["git", "commit", "-m", "Create starter PsyNet experiment"], target_dir, None)


def create_github_repository(
    repository: RepositorySpec,
    target_dir: Path,
    options: CreateOptions,
    runner: CommandRunner,
) -> None:
    """Create the GitHub repository using GitHub CLI and push the starter commit."""

    if shutil.which("gh") is None:
        raise CreateError(
            "GitHub CLI (`gh`) is required. Install it and authenticate with `gh auth login`."
        )

    command = [
        "gh",
        "repo",
        "create",
        repository.full_name,
        "--source",
        str(target_dir),
        "--remote",
        options.remote,
        "--push",
    ]
    command.append("--private" if options.private else "--public")
    if options.description:
        command.extend(["--description", options.description])

    runner(command, target_dir, None)


def github_secrets_for_options(
    options: CreateOptions,
    ec2_ssh_private_key_path: Path | None,
) -> dict[str, str]:
    secrets: dict[str, str] = {}

    if ec2_ssh_private_key_path is not None:
        if not ec2_ssh_private_key_path.is_file():
            raise CreateError(f"Missing generated EC2 SSH private key: {ec2_ssh_private_key_path}")
        secrets[EC2_SSH_SECRET_NAME] = ec2_ssh_private_key_path.read_text(encoding="utf-8")

    if options.set_aws_secrets:
        secrets.update(
            read_aws_credentials(
                profile=options.aws_profile,
                credentials_file=options.aws_credentials_file,
            )
        )

    return secrets


def configure_github_secrets(
    target_dir: Path,
    secrets: Mapping[str, str],
    runner: CommandRunner,
) -> tuple[str, ...]:
    """Copy secret values into GitHub Actions secrets for the generated repository."""

    if not secrets:
        return ()

    if shutil.which("gh") is None:
        raise CreateError(
            "GitHub CLI (`gh`) is required to configure repository secrets."
        )

    configured = []
    for name, value in secrets.items():
        if value:
            runner(
                ["gh", "secret", "set", name],
                target_dir,
                value,
            )
            configured.append(name)

    return tuple(configured)


def read_aws_credentials(
    *,
    profile: str = "default",
    credentials_file: Path | None = None,
) -> dict[str, str]:
    """Read AWS credentials from an INI-style AWS credentials file."""

    path = (credentials_file or Path("~/.aws/credentials")).expanduser()
    if not path.is_file():
        raise CreateError(f"AWS credentials file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path)

    section_name = resolve_aws_profile_section(parser, profile)
    if section_name is None:
        raise CreateError(f"AWS profile {profile!r} was not found in {path}.")

    section = parser[section_name]
    required_keys = ("aws_access_key_id", "aws_secret_access_key")
    missing = [key for key in required_keys if not section.get(key, "").strip()]
    if missing:
        missing_list = ", ".join(missing)
        raise CreateError(
            f"AWS profile {profile!r} is missing required value(s): {missing_list}."
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


def run_command(
    command: Sequence[str],
    cwd: Path | None = None,
    input_text: str | None = None,
) -> None:
    try:
        subprocess.run(
            command,
            cwd=cwd,
            check=True,
            input=input_text,
            text=input_text is not None,
        )
    except FileNotFoundError as exc:
        raise CreateError(f"Required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        rendered = " ".join(command)
        raise CreateError(f"Command failed with exit code {exc.returncode}: {rendered}") from exc
