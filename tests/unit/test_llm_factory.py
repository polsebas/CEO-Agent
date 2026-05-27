"""LLM provider selection in agent factory."""

from agents.factory import _google_model, get_resilient_model
from core.config import settings


def test_google_model_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "")
    assert _google_model() is None


def test_google_model_builds_gemini(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "test-key")
    monkeypatch.setattr(settings, "google_gemini_model", "gemini-3.5-flash")
    model = _google_model()
    assert model is not None
    assert model.id == "gemini-3.5-flash"
    assert model.api_key == "test-key"


def test_llm_provider_google(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "google")
    monkeypatch.setattr(settings, "google_api_key", "test-key")
    monkeypatch.setattr(settings, "google_gemini_model", "gemini-3.5-flash")
    monkeypatch.setattr(settings, "anthropic_api_key", "skip-anthropic")
    model = get_resilient_model()
    assert model is not None
    assert model.id == "gemini-3.5-flash"


def test_llm_provider_auto_prefers_google(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "google_api_key", "google-key")
    monkeypatch.setattr(settings, "anthropic_api_key", "anthropic-key")
    monkeypatch.setattr(settings, "openai_api_key", "openai-key")
    monkeypatch.setattr(settings, "google_gemini_model", "gemini-3.5-flash")
    model = get_resilient_model()
    assert model is not None
    assert model.provider == "Google"
