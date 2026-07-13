"""LLM advisor layer (SPEC M4): Claude re-ranks and explains the
deterministic report; privacy filter + number contract enforced."""

from .advisor import EnhancedReport, LlmUnavailable, enhance_report

__all__ = ["EnhancedReport", "LlmUnavailable", "enhance_report"]
