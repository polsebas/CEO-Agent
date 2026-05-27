"""Agent factory — Agno cognition adapters (no runtime authority)."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Agno internal retries disabled — runtime owns StructuredRetryTrace
AGNO_ADAPTER_RETRIES = 0


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _anthropic_model():
    from core.config import settings

    if not settings.anthropic_api_key:
        return None
    from agno.models.anthropic import Claude

    return Claude(id="claude-sonnet-4-20250514", temperature=0.0)


def _openai_model():
    from core.config import settings

    if not settings.openai_api_key:
        return None
    from agno.models.openai import OpenAIChat

    return OpenAIChat(id="gpt-4o-mini", temperature=0.0)


def _google_model():
    from core.config import settings

    if not settings.google_api_key:
        return None
    from agno.models.google import Gemini

    return Gemini(
        id=settings.google_gemini_model,
        api_key=settings.google_api_key,
        temperature=0.0,
    )


_PROVIDERS = {
    "anthropic": _anthropic_model,
    "openai": _openai_model,
    "google": _google_model,
}


def get_resilient_model():
    from core.config import settings

    if settings.llm_provider != "auto":
        try:
            return _PROVIDERS[settings.llm_provider]()
        except Exception:
            return None

    for builder in (_google_model, _anthropic_model, _openai_model):
        try:
            model = builder()
            if model is not None:
                return model
        except Exception:
            pass
    return None


def create_ceo_agent():
    from agno.agent import Agent

    from schemas.responses import CEOResponse

    model = get_resilient_model()
    kwargs = {
        "name": "CEO Agent",
        "instructions": load_prompt("ceo_agent_v1.md"),
        "output_schema": CEOResponse,
        "tool_call_limit": 0,
        "retries": AGNO_ADAPTER_RETRIES,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_cto_agent():
    """CTO adapter — no tools; orchestrator executes tools via router."""
    from agno.agent import Agent

    from schemas.responses import CTOResponse

    model = get_resilient_model()
    kwargs = {
        "name": "CTO Agent",
        "instructions": load_prompt("cto_agent_v1.md"),
        "tools": [],
        "output_schema": CTOResponse,
        "tool_call_limit": 0,
        "retries": AGNO_ADAPTER_RETRIES,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_cfo_agent():
    from agno.agent import Agent

    from schemas.responses import CFOResponse

    model = get_resilient_model()
    kwargs = {
        "name": "CFO Agent",
        "instructions": load_prompt("cfo_agent_v1.md"),
        "tools": [],
        "output_schema": CFOResponse,
        "tool_call_limit": 0,
        "retries": AGNO_ADAPTER_RETRIES,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_coo_agent():
    from agno.agent import Agent

    from schemas.responses import COOResponse

    model = get_resilient_model()
    kwargs = {
        "name": "COO Agent",
        "instructions": load_prompt("coo_agent_v1.md"),
        "tools": [],
        "output_schema": COOResponse,
        "tool_call_limit": 0,
        "retries": AGNO_ADAPTER_RETRIES,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)


def create_cmo_agent():
    from agno.agent import Agent

    from schemas.responses import CMOResponse

    model = get_resilient_model()
    kwargs = {
        "name": "CMO Agent",
        "instructions": load_prompt("cmo_agent_v1.md"),
        "tools": [],
        "output_schema": CMOResponse,
        "tool_call_limit": 0,
        "retries": AGNO_ADAPTER_RETRIES,
    }
    if model:
        kwargs["model"] = model
    return Agent(**kwargs)
