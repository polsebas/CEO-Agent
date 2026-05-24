"""Agent factory and Agno agent definitions."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_resilient_model():
    from core.config import settings

    try:
        if settings.anthropic_api_key:
            from agno.models.anthropic import Claude

            return Claude(id="claude-sonnet-4-20250514", temperature=0.0)
    except Exception:
        pass
    try:
        if settings.openai_api_key:
            from agno.models.openai import OpenAIChat

            return OpenAIChat(id="gpt-4o-mini", temperature=0.0)
    except Exception:
        pass
    return None


def create_ceo_agent():
    from agno.agent import Agent

    from schemas.responses import CEOResponse

    model = get_resilient_model()
    instructions = load_prompt("ceo_agent_v1.md")
    kwargs = {
        "name": "CEO Agent",
        "instructions": instructions,
        "output_schema": CEOResponse,
        "tool_call_limit": 8,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_cto_agent():
    from agno.agent import Agent

    from schemas.responses import CTOResponse
    from tools.github.client import analyze_incidents, get_repo_health, list_github_prs, prioritize_bugs

    model = get_resilient_model()
    instructions = load_prompt("cto_agent_v1.md")
    kwargs = {
        "name": "CTO Agent",
        "instructions": instructions,
        "tools": [list_github_prs, get_repo_health, analyze_incidents, prioritize_bugs],
        "output_schema": CTOResponse,
        "tool_call_limit": 5,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_cfo_agent():
    from agno.agent import Agent

    from schemas.responses import CFOResponse
    from tools.stubs.business import calculate_runway, get_cashflow_summary

    model = get_resilient_model()
    kwargs = {
        "name": "CFO Agent",
        "instructions": load_prompt("cfo_agent_v1.md"),
        "tools": [get_cashflow_summary, calculate_runway],
        "output_schema": CFOResponse,
        "tool_call_limit": 5,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_coo_agent():
    from agno.agent import Agent

    from schemas.responses import COOResponse
    from tools.stubs.business import detect_blockers, list_active_tasks

    model = get_resilient_model()
    kwargs = {
        "name": "COO Agent",
        "instructions": load_prompt("coo_agent_v1.md"),
        "tools": [list_active_tasks, detect_blockers],
        "output_schema": COOResponse,
        "tool_call_limit": 5,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_cmo_agent():
    from agno.agent import Agent

    from schemas.responses import CMOResponse
    from tools.stubs.business import get_analytics_summary, propose_campaign

    model = get_resilient_model()
    kwargs = {
        "name": "CMO Agent",
        "instructions": load_prompt("cmo_agent_v1.md"),
        "tools": [get_analytics_summary, propose_campaign],
        "output_schema": CMOResponse,
        "tool_call_limit": 5,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)
