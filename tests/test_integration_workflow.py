from pathlib import Path


WORKFLOW = Path(".github/workflows/integration-deploy.yml")


def test_integration_workflow_exercises_generated_deploy_pipeline():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "PSYNET_GITHUB_TEST_TOKEN" in text
    assert "psynet-github create" in text
    assert "--set-aws-secrets" in text
    assert "gh workflow run deploy-hotair.yml" in text
    assert "gh run watch" in text
    assert "ec2.terminate_instances(InstanceIds=instance_ids)" in text
    assert "gh repo delete" in text


def test_integration_workflow_requires_dns_input_or_variable():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "dns_host" in text
    assert "dns_domain" in text
    assert "PSYNET_GITHUB_TEST_DNS_DOMAIN" in text
    assert "Provide workflow input dns_host" in text
