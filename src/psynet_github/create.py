from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse


CommandRunner = Callable[[Sequence[str], Path | None], None]

GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


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


@dataclass(frozen=True)
class CreateResult:
    """Information about a rendered PsyNet experiment repository."""

    repository: RepositorySpec
    directory: Path
    initialized_git: bool
    pushed_to_github: bool


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

    return CreateResult(
        repository=repository,
        directory=target_dir,
        initialized_git=initialized_git,
        pushed_to_github=pushed_to_github,
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


def initialize_git_repository(
    target_dir: Path,
    default_branch: str,
    runner: CommandRunner,
) -> None:
    """Initialize a git repository and create the starter commit."""

    runner(["git", "init", "-b", default_branch], target_dir)
    runner(["git", "add", "."], target_dir)
    runner(["git", "commit", "-m", "Create starter PsyNet experiment"], target_dir)


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

    runner(command, target_dir)


def run_command(command: Sequence[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise CreateError(f"Required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        rendered = " ".join(command)
        raise CreateError(f"Command failed with exit code {exc.returncode}: {rendered}") from exc
