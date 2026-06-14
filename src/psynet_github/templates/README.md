# {{project_title}}

{{description}}

This repository contains a starter PsyNet experiment. It was generated with
`psynet-github create`.

## Repository layout

- `experiment.py` defines the PsyNet experiment.
- `config.txt` contains Dallinger/PsyNet configuration.
- `requirements.txt` pins PsyNet from GitLab.
- `constraints.txt` is present for Dallinger dependency locking workflows.
- `test.py` runs the standard PsyNet experiment test through pytest.
- `.github/workflows/test.yml` runs a basic GitHub Actions test suite.
- `.github/workflows/deploy-hotair.yml` can provision EC2 and start a hotair
  debug deployment from a selected branch.
- `deploy.txt` records the default deployment inputs generated for the workflow.
- `.deploy/ssh/` stores the generated EC2 SSH keypair. This directory is
  intentionally ignored by git.
- `AGENTS.md` links PsyNetSkills guidance for future agent work.

## Local checks

From the repository root:

```bash
python -m pip install --upgrade pip wheel
pip install -r requirements.txt pytest
python experiment.py
pytest test.py
```

For full local PsyNet validation, ensure PostgreSQL, Redis, Docker, and the
Heroku CLI are available, then run:

```bash
psynet test local
```

## Hotair debug deployment

The generated `Deploy hotair debug experiment` GitHub Actions workflow can be
run manually from the Actions tab. It accepts a branch, tag, or commit SHA to
deploy, plus deployment parameters pre-filled from `deploy.txt`.

Before running it, configure GitHub secrets or repository/environment variables
for:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` if your AWS credentials require one
- `EC2_SSH_PRIVATE_KEY`
- `DALLINGER_DASHBOARD_USER`
- `DALLINGER_DASHBOARD_PASSWORD`

`psynet-github create` generates a unique EC2 SSH keypair under `.deploy/ssh/`
and, when it creates the GitHub repository, copies the private key into the
`EC2_SSH_PRIVATE_KEY` GitHub Actions secret.

If this repository was created with:

```bash
psynet-github create {{repo_full_name}} --set-aws-secrets
```

then `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional
`AWS_SESSION_TOKEN` were copied from the selected local AWS profile into GitHub
Actions secrets during repository creation.

The workflow checks whether the configured EC2 server already exists, provisions
it with `dallinger ec2 provision` if needed, attempts to stop an existing debug
app with `psynet destroy ssh`, and starts a fresh run with `psynet debug ssh`.
