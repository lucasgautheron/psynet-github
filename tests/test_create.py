from pathlib import Path

import pytest

from psynet_github.create import (
    CreateError,
    CreateOptions,
    create_experiment_repository,
    parse_repository,
)


def test_parse_repository_accepts_owner_name_and_urls():
    assert parse_repository("example").full_name == "example"
    assert parse_repository("owner/example").full_name == "owner/example"
    assert (
        parse_repository("https://github.com/owner/example.git").full_name
        == "owner/example"
    )


def test_parse_repository_rejects_invalid_names():
    with pytest.raises(CreateError, match="Invalid repository name"):
        parse_repository("bad repo")

    with pytest.raises(CreateError, match="Owner was provided"):
        parse_repository("alice/example", owner="bob")


def test_create_renders_template_without_git_or_github(tmp_path):
    target_dir = tmp_path / "starter"

    result = create_experiment_repository(
        CreateOptions(
            repository="owner/starter",
            directory=target_dir,
            description="A generated PsyNet experiment.",
            no_git=True,
        )
    )

    assert result.directory == target_dir
    assert result.repository.full_name == "owner/starter"
    assert result.initialized_git is False
    assert result.pushed_to_github is False

    assert (target_dir / "experiment.py").read_text(encoding="utf-8").startswith(
        '"""Empty PsyNet experiment scaffold'
    )
    assert (target_dir / ".gitignore").exists()
    assert (target_dir / ".github" / "workflows" / "test.yml").exists()
    assert (target_dir / ".github" / "workflows" / "deploy-hotair.yml").exists()
    assert "PsyNetSkills" in (target_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "A generated PsyNet experiment." in (
        target_dir / "README.md"
    ).read_text(encoding="utf-8")

    deploy_defaults = (target_dir / "deploy.txt").read_text(encoding="utf-8")
    assert "region=us-east-1" in deploy_defaults
    assert "instance_type=m7i.xlarge" in deploy_defaults
    assert "memory_gb=32" in deploy_defaults
    assert "server_name=starter-debug" in deploy_defaults

    deploy_workflow = (
        target_dir / ".github" / "workflows" / "deploy-hotair.yml"
    ).read_text(encoding="utf-8")
    assert "deploy_ref" in deploy_workflow
    assert "dallinger ec2 provision" in deploy_workflow
    assert "psynet destroy ssh" in deploy_workflow
    assert "psynet debug ssh" in deploy_workflow
    assert "--recruiter hotair" in deploy_workflow


def test_create_initializes_git_when_github_is_skipped(tmp_path):
    target_dir = tmp_path / "starter"
    commands = []

    def runner(command, cwd):
        commands.append((list(command), Path(cwd)))

    result = create_experiment_repository(
        CreateOptions(
            repository="starter",
            directory=target_dir,
            no_github=True,
        ),
        runner=runner,
    )

    assert result.initialized_git is True
    assert result.pushed_to_github is False
    assert commands == [
        (["git", "init", "-b", "main"], target_dir),
        (["git", "add", "."], target_dir),
        (["git", "commit", "-m", "Create starter PsyNet experiment"], target_dir),
    ]


def test_create_fails_for_non_empty_directory_without_force(tmp_path):
    target_dir = tmp_path / "starter"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(CreateError, match="not empty"):
        create_experiment_repository(
            CreateOptions(
                repository="starter",
                directory=target_dir,
                no_git=True,
            )
        )
