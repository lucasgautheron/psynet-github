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
It also generates a unique EC2 SSH key under the generated repository's
git-ignored `.deploy/ssh/` directory and copies the private key into the
`EC2_SSH_PRIVATE_KEY` GitHub Actions secret.

`--set-aws-secrets` is opt-in because it copies local AWS credentials into the
new repository's GitHub Actions secrets. It reads `aws_access_key_id`,
`aws_secret_access_key`, and optional `aws_session_token` from the selected AWS
profile and stores them as `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and
`AWS_SESSION_TOKEN`.

Use `--ec2-ssh-key-path` to choose a different private-key destination, or
`--no-ec2-ssh-key` to skip EC2 key generation and secret configuration.

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
- `.deploy/ssh/<repository>-ec2.pem`, a git-ignored EC2 SSH private key generated
  during creation.
- `AGENTS.md` with HTTP links to relevant PsyNetSkills guidance.
