# psynet-github

`psynet-github` creates GitHub repositories containing starter PsyNet
experiments.

## Installation

From this checkout:

```bash
pip install -e .
```

For local development:

```bash
pip install -e ".[dev]"
```

## Usage

Create a private repository under your authenticated GitHub account:

```bash
psynet-github create my-psynet-experiment
```

Create a repository for a specific owner or organization:

```bash
psynet-github create pmcharrison/my-psynet-experiment
```

Create a public repository:

```bash
psynet-github create my-psynet-experiment --public
```

Render the template locally without creating a GitHub repository:

```bash
psynet-github create my-psynet-experiment --no-github
```

Create the repository and copy AWS credentials from `~/.aws/credentials` into
GitHub Actions secrets:

```bash
psynet-github create my-psynet-experiment \
  --set-aws-secrets \
  --aws-profile default
```

The GitHub-creating path requires an authenticated
[GitHub CLI](https://cli.github.com/) installation. The command renders a
minimal PsyNet experiment, initializes git, commits the scaffold, creates the
GitHub repository with `gh repo create`, and pushes the starter commit.
It also generates a unique OpenSSH Ed25519 EC2 SSH key under the generated
repository's git-ignored `.deploy/ssh/` directory and copies the private key
into the `EC2_SSH_PRIVATE_KEY` GitHub Actions secret.
The deployment dashboard credentials are also configured as GitHub Actions
secrets, defaulting to `admin` / `admin`.
Generated repositories also receive a local `.git/hooks/pre-commit` hook that
rejects staged files containing private-key PEM/OpenSSH markers.

`--set-aws-secrets` is opt-in because it copies local AWS credentials into the
new repository's GitHub Actions secrets. It reads `aws_access_key_id`,
`aws_secret_access_key`, and optional `aws_session_token` from the selected AWS
profile and stores them as `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and
`AWS_SESSION_TOKEN`.

Use `--ec2-ssh-key-path` to choose a different private-key destination, or
`--no-ec2-ssh-key` to skip EC2 key generation and secret configuration.
Use `--dashboard-user` and `--dashboard-password` to override the default
dashboard credentials stored in `DALLINGER_DASHBOARD_USER` and
`DALLINGER_DASHBOARD_PASSWORD`.

## Generated experiment contents

The generated repository includes:

- `experiment.py` with an empty runnable PsyNet `Exp`.
- `config.txt`, `requirements.txt`, `constraints.txt`, `test.py`, `pytest.ini`,
  and `.python-version`.
- `.github/workflows/test.yml` for basic CI.
- `.github/workflows/deploy-hotair.yml` for manually deploying a hotair debug
  run from a selected branch.
- `deploy.txt` containing the generated deployment defaults used to pre-fill the
  workflow.
- `.deploy/ssh/<repository>-ec2.pem`, a git-ignored OpenSSH Ed25519 EC2 SSH
  private key generated during creation.
- A local `.git/hooks/pre-commit` hook that blocks commits containing private
  key material.
- `AGENTS.md` with HTTP links to relevant PsyNetSkills guidance.

## Integration deployment test

This repository includes a manual GitHub Actions workflow,
`Integration deploy generated experiment`, that exercises the full generated
pipeline:

1. Render the latest generated PsyNet experiment template into a fixed
   integration repository with `psynet-github create --no-git`.
2. Configure that repository's generated workflow secrets.
3. Push template updates to the fixed integration repository when needed.
4. Dispatch the integration repository's `deploy-hotair.yml` workflow.
5. Watch that workflow to completion and print its logs.
6. Clean up matching AWS EC2/key-pair resources.

Configure the required secrets from a local clone with:

```bash
gh auth refresh -s workflow
python scripts/setup_secrets.py \
  --repo OWNER/psynet-github \
  --aws-profile default \
  --use-gh-token \
  --dns-domain example.com
```

The fixed integration repository defaults to `psynet-github-integration` under
`PSYNET_GITHUB_TEST_OWNER` or this repository's owner. The integration workflow
creates that repository on first run if it does not exist, then keeps reusing it.
The stored `PSYNET_GITHUB_TEST_TOKEN` must be able to create the fixed
repository if missing, push to it, and configure secrets in it. For a classic
GitHub token, this typically means `repo`; add `workflow` if template updates
need to create or update `.github/workflows/deploy-hotair.yml`. If you do not
configure `--dns-domain`, provide `dns_host` or `dns_domain` when manually
dispatching the workflow.

The `workflow` scope is required only when the integration workflow needs to
create or update workflow files in the fixed integration repository. GitHub
rejects pushes that create or update `.github/workflows/*` without it.
