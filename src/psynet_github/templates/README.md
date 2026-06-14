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
