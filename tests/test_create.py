from pathlib import Path

import pytest

from psynet_github.create import (
    CreateError,
    CreateOptions,
    create_experiment_repository,
    parse_repository,
    read_aws_credentials,
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
            generate_ec2_ssh_key=False,
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
    assert ".deploy/" in (target_dir / ".gitignore").read_text(encoding="utf-8")
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
    assert "ssh_key_name=starter-ec2" in deploy_defaults
    assert "ssh_private_key_path=.deploy/ssh/starter-ec2.pem" in deploy_defaults

    deploy_workflow = (
        target_dir / ".github" / "workflows" / "deploy-hotair.yml"
    ).read_text(encoding="utf-8")
    assert "deploy_ref" in deploy_workflow
    assert "image: redis:7" in deploy_workflow
    assert "6379:6379" in deploy_workflow
    assert "Verify Redis is available" in deploy_workflow
    assert 'socket.create_connection(("127.0.0.1", 6379)' in deploy_workflow
    assert "dallinger ec2 provision" in deploy_workflow
    assert 'dallinger ec2 list instances --region "${{ inputs.region }}"' in deploy_workflow
    assert "dallinger ec2 list instances --all" not in deploy_workflow
    assert "Register Dallinger SSH server" in deploy_workflow
    assert "dallinger docker-ssh servers add" in deploy_workflow
    assert '--host "${{ inputs.dns_host }}"' in deploy_workflow
    assert "--user ubuntu" in deploy_workflow
    assert "psynet destroy ssh" in deploy_workflow
    assert "psynet debug ssh" in deploy_workflow
    assert "Configure hotair recruiter" in deploy_workflow
    assert "recruiter = hotair" in deploy_workflow
    assert "--recruiter" not in deploy_workflow
    assert "EC2_SSH_PRIVATE_KEY" in deploy_workflow


def test_create_initializes_git_when_github_is_skipped(tmp_path):
    target_dir = tmp_path / "starter"
    commands = []

    def runner(command, cwd, input_text=None):
        if command[:2] == ["git", "init"]:
            Path(cwd, ".git", "hooks").mkdir(parents=True)
        commands.append((list(command), Path(cwd), input_text))

    result = create_experiment_repository(
        CreateOptions(
            repository="starter",
            directory=target_dir,
            no_github=True,
            generate_ec2_ssh_key=False,
        ),
        runner=runner,
    )

    assert result.initialized_git is True
    assert result.pushed_to_github is False
    hook = target_dir / ".git" / "hooks" / "pre-commit"
    assert hook.exists()
    assert "PRIVATE KEY" in hook.read_text(encoding="utf-8")
    assert commands == [
        (["git", "init", "-b", "main"], target_dir, None),
        (["git", "add", "."], target_dir, None),
        (
            ["git", "commit", "-m", "Create starter PsyNet experiment"],
            target_dir,
            None,
        ),
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
                generate_ec2_ssh_key=False,
            )
        )


def test_read_aws_credentials_from_profile(tmp_path):
    credentials_file = tmp_path / "credentials"
    credentials_file.write_text(
        """
        [default]
        aws_access_key_id = default-key
        aws_secret_access_key = default-secret

        [workshop]
        aws_access_key_id = workshop-key
        aws_secret_access_key = workshop-secret
        aws_session_token = workshop-token
        """,
        encoding="utf-8",
    )

    assert read_aws_credentials(credentials_file=credentials_file) == {
        "AWS_ACCESS_KEY_ID": "default-key",
        "AWS_SECRET_ACCESS_KEY": "default-secret",
    }
    assert read_aws_credentials(
        profile="workshop",
        credentials_file=credentials_file,
    ) == {
        "AWS_ACCESS_KEY_ID": "workshop-key",
        "AWS_SECRET_ACCESS_KEY": "workshop-secret",
        "AWS_SESSION_TOKEN": "workshop-token",
    }


def test_create_sets_aws_secrets_from_credentials_file(tmp_path, monkeypatch):
    target_dir = tmp_path / "starter"
    credentials_file = tmp_path / "credentials"
    credentials_file.write_text(
        """
        [default]
        aws_access_key_id = key
        aws_secret_access_key = secret
        aws_session_token = token
        """,
        encoding="utf-8",
    )
    commands = []

    def runner(command, cwd, input_text=None):
        if command[:2] == ["git", "init"]:
            Path(cwd, ".git", "hooks").mkdir(parents=True)
        commands.append((list(command), Path(cwd) if cwd else None, input_text))

    monkeypatch.setattr(
        "psynet_github.create.shutil.which",
        lambda command: f"/usr/bin/{command}",
    )

    result = create_experiment_repository(
        CreateOptions(
            repository="starter",
            directory=target_dir,
            set_aws_secrets=True,
            aws_credentials_file=credentials_file,
            generate_ec2_ssh_key=False,
        ),
        runner=runner,
    )

    assert result.configured_secrets == (
        "DALLINGER_DASHBOARD_USER",
        "DALLINGER_DASHBOARD_PASSWORD",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    )
    assert commands[-3:] == [
        (["gh", "secret", "set", "AWS_ACCESS_KEY_ID"], target_dir, "key"),
        (["gh", "secret", "set", "AWS_SECRET_ACCESS_KEY"], target_dir, "secret"),
        (["gh", "secret", "set", "AWS_SESSION_TOKEN"], target_dir, "token"),
    ]
    assert commands[4:6] == [
        (["gh", "secret", "set", "DALLINGER_DASHBOARD_USER"], target_dir, "admin"),
        (["gh", "secret", "set", "DALLINGER_DASHBOARD_PASSWORD"], target_dir, "admin"),
    ]
    assert commands[3][0][:3] == ["gh", "repo", "create"]


def test_set_aws_secrets_requires_github_creation(tmp_path):
    with pytest.raises(CreateError, match="requires GitHub repository creation"):
        create_experiment_repository(
            CreateOptions(
                repository="starter",
                directory=tmp_path / "starter",
                no_github=True,
                set_aws_secrets=True,
                generate_ec2_ssh_key=False,
            )
        )


def test_create_generates_ec2_ssh_key_and_sets_github_secret(tmp_path, monkeypatch):
    target_dir = tmp_path / "starter"
    commands = []

    def runner(command, cwd, input_text=None):
        if command[:2] == ["git", "init"]:
            Path(cwd, ".git", "hooks").mkdir(parents=True)
        commands.append((list(command), Path(cwd) if cwd else None, input_text))
        if command[0] == "ssh-keygen":
            private_key_path = Path(command[command.index("-f") + 1])
            private_key_path.write_text("PRIVATE KEY\n", encoding="utf-8")
            private_key_path.with_name(f"{private_key_path.name}.pub").write_text(
                "PUBLIC KEY\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(
        "psynet_github.create.shutil.which",
        lambda command: f"/usr/bin/{command}",
    )

    result = create_experiment_repository(
        CreateOptions(
            repository="starter",
            directory=target_dir,
        ),
        runner=runner,
    )

    private_key_path = target_dir / ".deploy" / "ssh" / "starter-ec2.pem"
    assert result.ec2_ssh_private_key_path == private_key_path
    assert result.configured_secrets == (
        "DALLINGER_DASHBOARD_USER",
        "DALLINGER_DASHBOARD_PASSWORD",
        "EC2_SSH_PRIVATE_KEY",
    )
    assert (target_dir / ".git" / "hooks" / "pre-commit").exists()
    assert private_key_path.read_text(encoding="utf-8") == "PRIVATE KEY\n"
    assert (target_dir / ".deploy" / "ssh" / "starter-ec2.pem.pub").exists()

    assert commands[0][0][:2] == ["ssh-keygen", "-q"]
    assert commands[1][0] == ["git", "init", "-b", "main"]
    assert commands[4][0][:3] == ["gh", "repo", "create"]
    assert commands[-3:] == [
        (["gh", "secret", "set", "DALLINGER_DASHBOARD_USER"], target_dir, "admin"),
        (["gh", "secret", "set", "DALLINGER_DASHBOARD_PASSWORD"], target_dir, "admin"),
        (
            ["gh", "secret", "set", "EC2_SSH_PRIVATE_KEY"],
            target_dir,
            "PRIVATE KEY\n",
        ),
    ]
