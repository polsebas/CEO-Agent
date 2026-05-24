"""4-tier deterministic-first preprocessor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PreprocessorTier(str, Enum):
    REGEX = "tier1_regex"
    EMBEDDING = "tier2_embedding"
    CLASSIFIER = "tier3_classifier"
    COGNITION = "tier4_cognition"


@dataclass
class PreprocessorResult:
    tier: PreprocessorTier
    tool_name: str | None = None
    params: dict | None = None
    confidence: float = 0.0
    raw_input: str = ""


TIER1_PATTERNS: list[tuple[re.Pattern[str], str, dict]] = [
    (re.compile(r"how many prs?\s*(are\s*)?(open|blocked)", re.I), "list_github_prs", {"status": "open"}),
    (re.compile(r"(open|blocked)\s*prs?", re.I), "list_github_prs", {"status": "open"}),
    (re.compile(r"repo\s*health", re.I), "get_repo_health", {}),
    (re.compile(r"github\s*status", re.I), "get_repo_health", {}),
    (re.compile(r"runway", re.I), "calculate_runway", {}),
    (re.compile(r"cashflow|cash flow", re.I), "get_cashflow_summary", {}),
    (re.compile(r"kpi|dashboard", re.I), "read_kpi_dashboard", {}),
    (re.compile(r"blockers?", re.I), "detect_blockers", {}),
    (re.compile(r"analytics|conversion", re.I), "get_analytics_summary", {}),
]

TIER2_KEYWORDS: list[tuple[set[str], str, dict]] = [
    ({"pull", "request", "github", "pr"}, "list_github_prs", {"status": "open"}),
    ({"deployment", "repository", "health"}, "get_repo_health", {}),
    ({"revenue", "financial", "burn"}, "get_cashflow_summary", {}),
    ({"task", "operations", "bottleneck"}, "detect_blockers", {}),
    ({"marketing", "campaign", "cac"}, "get_analytics_summary", {}),
]

TIER3_KEYWORDS: list[tuple[set[str], str]] = [
    ({"anomaly", "incident", "deployment", "outage"}, "delegate_cto"),
    ({"budget", "runway", "forecast"}, "delegate_cfo"),
    ({"blocker", "team", "sync"}, "delegate_coo"),
    ({"campaign", "funnel", "acquisition"}, "delegate_cmo"),
]


class Preprocessor:
    def process(self, user_input: str) -> PreprocessorResult:
        text = user_input.strip()
        result = self._tier1_regex(text)
        if result:
            return result
        result = self._tier2_embedding(text)
        if result:
            return result
        result = self._tier3_classifier(text)
        if result:
            return result
        return PreprocessorResult(tier=PreprocessorTier.COGNITION, raw_input=text)

    def _tier1_regex(self, text: str) -> PreprocessorResult | None:
        for pattern, tool, params in TIER1_PATTERNS:
            if pattern.search(text):
                return PreprocessorResult(
                    tier=PreprocessorTier.REGEX,
                    tool_name=tool,
                    params=params,
                    confidence=0.95,
                    raw_input=text,
                )
        return None

    def _tier2_embedding(self, text: str) -> PreprocessorResult | None:
        words = set(re.findall(r"\w+", text.lower()))
        best_score = 0.0
        best: PreprocessorResult | None = None
        for keywords, tool, params in TIER2_KEYWORDS:
            overlap = len(words & keywords) / max(len(keywords), 1)
            if overlap > best_score and overlap >= 0.5:
                best_score = overlap
                best = PreprocessorResult(
                    tier=PreprocessorTier.EMBEDDING,
                    tool_name=tool,
                    params=params,
                    confidence=overlap,
                    raw_input=text,
                )
        return best

    def _tier3_classifier(self, text: str) -> PreprocessorResult | None:
        words = set(re.findall(r"\w+", text.lower()))
        for keywords, action in TIER3_KEYWORDS:
            if words & keywords:
                return PreprocessorResult(
                    tier=PreprocessorTier.CLASSIFIER,
                    tool_name=action,
                    params={"query": text},
                    confidence=0.75,
                    raw_input=text,
                )
        return None


preprocessor = Preprocessor()
