import importlib.util
import argparse
from pathlib import Path


def load_setup_secrets_module():
    module_path = Path("scripts/setup_secrets.py")
    spec = importlib.util.spec_from_file_location("setup_secrets", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_setup_secrets_reads_aws_credentials_profiles(tmp_path):
    setup_secrets = load_setup_secrets_module()
    credentials_file = tmp_path / "credentials"
    credentials_file.write_text(
        """
        [default]
        aws_access_key_id = default-key
        aws_secret_access_key = default-secret

        [profile workshop]
        aws_access_key_id = workshop-key
        aws_secret_access_key = workshop-secret
        aws_session_token = workshop-token
        """,
        encoding="utf-8",
    )

    assert setup_secrets.read_aws_credentials(
        credentials_file=credentials_file,
        profile="default",
    ) == {
        "AWS_ACCESS_KEY_ID": "default-key",
        "AWS_SECRET_ACCESS_KEY": "default-secret",
    }
    assert setup_secrets.read_aws_credentials(
        credentials_file=credentials_file,
        profile="workshop",
    ) == {
        "AWS_ACCESS_KEY_ID": "workshop-key",
        "AWS_SECRET_ACCESS_KEY": "workshop-secret",
        "AWS_SESSION_TOKEN": "workshop-token",
    }


def test_setup_secrets_parses_oauth_scopes():
    setup_secrets = load_setup_secrets_module()

    assert setup_secrets.parse_oauth_scopes("repo, workflow, delete_repo") == {
        "repo",
        "workflow",
        "delete_repo",
    }


def test_use_gh_token_takes_precedence_over_env(monkeypatch):
    setup_secrets = load_setup_secrets_module()

    def fake_run(command, *, capture=False, **kwargs):
        assert command == ["gh", "auth", "token"]
        return argparse.Namespace(stdout="gh-token\n")

    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    monkeypatch.setattr(setup_secrets, "run", fake_run)

    args = argparse.Namespace(
        github_token_stdin=False,
        github_token_env="GITHUB_TOKEN",
        use_gh_token=True,
    )

    assert setup_secrets.resolve_github_token(args) == "gh-token"
