from core.preprocessor import preprocessor


def test_tier1_github_prs():
    result = preprocessor.process("How many PRs are open?")
    assert result.tool_name == "list_github_prs"
    assert result.tier.value == "tier1_regex"


def test_tier1_repo_health():
    result = preprocessor.process("Show repo health status")
    assert result.tool_name == "get_repo_health"


def test_tier2_embedding():
    result = preprocessor.process("Check pull request status on github")
    assert result.tool_name == "list_github_prs"
    assert result.tier.value == "tier2_embedding"


def test_tier4_cognition_fallback():
    result = preprocessor.process("What should our strategy be for Q3?")
    assert result.tier.value == "tier4_cognition"
    assert result.tool_name is None


def test_preprocessor_tier12_coverage():
    samples = [
        "How many PRs are open?",
        "repo health",
        "Show KPI dashboard",
        "What is our runway?",
        "Check pull request github",
        "cashflow report",
        "detect blockers",
        "analytics summary",
        "Random strategy question",
        "Tell me about the company vision",
    ]
    tier12 = sum(
        1
        for s in samples
        if preprocessor.process(s).tier.value in ("tier1_regex", "tier2_embedding")
    )
    assert tier12 / len(samples) >= 0.4
