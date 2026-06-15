from pathlib import Path

from psynet_github.create import update_scripts


def test_update_scripts_only_updates_psynet_github_managed_files(tmp_path):
    experiment_dir = tmp_path / "my-experiment"
    workflow_dir = experiment_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)

    files_to_preserve = {
        "requirements.txt": "psynet==custom\n",
        "config.txt": "[Config]\ntitle = custom\n",
        "experiment.py": "# custom experiment\n",
        "Dockerfile": "# custom dockerfile\n",
        "test.py": "# custom test\n",
        ".gitignore": "# custom ignore\n",
    }
    for relative_path, text in files_to_preserve.items():
        path = experiment_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    managed_workflow = workflow_dir / "deploy-hotair.yml"
    managed_workflow.write_text("stale workflow\n", encoding="utf-8")
    psynet_workflow = workflow_dir / "test.yml"
    psynet_workflow.write_text("custom test workflow\n", encoding="utf-8")

    result = update_scripts(experiment_dir, repo_name="my-experiment")

    assert result.directory == experiment_dir
    assert result.updated_files == (managed_workflow,)
    assert "Deploy hotair debug experiment" in managed_workflow.read_text(
        encoding="utf-8"
    )
    assert 'default: "my-experiment-debug"' in managed_workflow.read_text(
        encoding="utf-8"
    )

    for relative_path, text in files_to_preserve.items():
        assert (experiment_dir / relative_path).read_text(encoding="utf-8") == text
    assert psynet_workflow.read_text(encoding="utf-8") == "custom test workflow\n"
