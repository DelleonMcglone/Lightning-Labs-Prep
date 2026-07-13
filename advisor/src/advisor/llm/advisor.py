"""The LLM advisor layer (SPEC M4, FR7).

Claude receives the knowledge base + the sanitized deterministic report and
returns, per recommendation id: a headline, a short narrative, and a
priority order with reasons. It re-phrases and re-ranks; it never computes.
Guards:

- input is sanitized (privacy.py) — no pubkeys/channel points/aliases;
- output narratives are validated against the deterministic fact set —
  a narrative containing an unknown number ≥ 1,000 is dropped and that
  item falls back to the engine's own summary;
- any failure (no key, network, bad JSON) raises LlmUnavailable and the
  CLI falls back to the offline report. The LLM is an enhancement, never
  a dependency.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ..config import Settings
from ..models import NodeSnapshot
from ..recommend.models import Recommendation, RecommendationReport
from ..signals import NodeSignals
from .privacy import collect_numeric_facts, narrative_violations, sanitize_report

KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"

SYSTEM_PROMPT = """You are a Lightning Network liquidity advisor speaking to \
a node operator who may not be an expert. You receive a deterministic \
engine's recommendations as JSON facts.

Rules you must follow exactly:
1. NEVER compute, alter, extrapolate or round numbers. Only repeat numbers \
that appear verbatim in the input facts. If you need a figure that isn't \
there, describe it qualitatively instead.
2. Re-rank only when the knowledge heuristics give a clear reason; \
otherwise keep the engine's order. Severity CRITICAL items stay first.
3. For each recommendation, write a headline (max 60 chars) and a short \
narrative (2-4 sentences) explaining WHY in seesaw terms an operator \
understands. Mention the biggest caveat.
4. Output ONLY a JSON array, one object per recommendation id you were \
given: {"id": "...", "rank": 1, "headline": "...", "narrative": "...", \
"priority_reason": "..."}.

Domain knowledge:
"""


class EnhancedItem(BaseModel):
    rec: Recommendation
    headline: str
    narrative: str
    priority_reason: str = ""
    narrative_from_llm: bool = True


class EnhancedReport(BaseModel):
    items: list[EnhancedItem]
    model: str = ""
    note: str = ""


class LlmUnavailable(RuntimeError):
    """Raised when the LLM layer can't run; caller falls back to offline."""


def load_knowledge() -> str:
    parts = []
    if KNOWLEDGE_DIR.is_dir():
        for f in sorted(KNOWLEDGE_DIR.glob("[0-9]*.md")):
            parts.append(f"\n--- {f.name} ---\n{f.read_text()}")
    return "\n".join(parts)


def _extract_json(text: str) -> list:
    """Parse the model's JSON array, tolerating code fences."""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("no JSON array in model output")
    return json.loads(m.group(0))


def enhance_report(
    report: RecommendationReport,
    sig: NodeSignals,
    snap: NodeSnapshot,
    settings: Settings,
    client: Optional[object] = None,
) -> EnhancedReport:
    """Run the LLM layer. `client` is injectable for tests."""
    if not report.recommendations:
        return EnhancedReport(items=[], note="nothing to enhance")

    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise LlmUnavailable("ANTHROPIC_API_KEY not set")
        try:
            import anthropic
            client = anthropic.Anthropic()
        except Exception as exc:  # pragma: no cover
            raise LlmUnavailable(f"anthropic client failed: {exc}") from exc

    payload, _aliases = sanitize_report(report, sig, snap)
    facts = collect_numeric_facts(report, sig, snap)

    try:
        response = client.messages.create(  # type: ignore[attr-defined]
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            system=SYSTEM_PROMPT + load_knowledge(),
            messages=[{
                "role": "user",
                "content": (
                    "Here is the deterministic report. Respond with the "
                    "JSON array only.\n\n" + json.dumps(payload, indent=1)
                ),
            }],
        )
        text = "".join(
            b.text for b in response.content if getattr(b, "type", "") == "text"
        )
        ranked = _extract_json(text)
    except LlmUnavailable:
        raise
    except Exception as exc:
        raise LlmUnavailable(f"LLM call failed: {exc}") from exc

    by_id = {
        f"{r.rule}-{i}": r for i, r in enumerate(report.recommendations)
    }
    items: list[EnhancedItem] = []
    seen = set()
    for entry in sorted(ranked, key=lambda e: e.get("rank", 99)):
        rec = by_id.get(entry.get("id", ""))
        if rec is None or entry.get("id") in seen:
            continue
        seen.add(entry["id"])
        narrative = str(entry.get("narrative", "")).strip()
        headline = str(entry.get("headline", rec.title)).strip()
        bad = narrative_violations(narrative, facts) + narrative_violations(
            headline, facts
        )
        if bad or not narrative:
            # Number contract violated → deterministic text wins.
            items.append(EnhancedItem(
                rec=rec, headline=rec.title, narrative=rec.summary,
                priority_reason="deterministic fallback "
                                f"(unverified numbers: {bad})" if bad else "",
                narrative_from_llm=False,
            ))
        else:
            items.append(EnhancedItem(
                rec=rec, headline=headline, narrative=narrative,
                priority_reason=str(entry.get("priority_reason", "")),
            ))

    # Anything the model dropped keeps its deterministic form, engine order.
    for rec_id, rec in by_id.items():
        if rec_id not in seen:
            items.append(EnhancedItem(
                rec=rec, headline=rec.title, narrative=rec.summary,
                narrative_from_llm=False,
            ))

    return EnhancedReport(items=items, model=settings.llm_model)
