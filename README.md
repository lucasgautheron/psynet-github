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

The GitHub-creating path requires an authenticated
[GitHub CLI](https://cli.github.com/) installation. The command renders a
minimal PsyNet experiment, initializes git, commits the scaffold, creates the
GitHub repository with `gh repo create`, and pushes the starter commit.

## Generated experiment contents

The generated repository includes:

- `experiment.py` with an empty runnable PsyNet `Exp`.
- `config.txt`, `requirements.txt`, `constraints.txt`, `test.py`, `pytest.ini`,
  and `.python-version`.
- `.github/workflows/test.yml` for basic CI.
- `AGENTS.md` with HTTP links to relevant PsyNetSkills guidance.
