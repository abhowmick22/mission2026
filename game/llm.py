"""LLM integration using Google Gemini Flash for enhanced game narration.

All functions gracefully fall back to the original text when:
- GEMINI_API_KEY env var is not set
- google-generativeai package is not installed
- Any API call fails or times out
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_model = None
_enabled: bool | None = None

SYSTEM_PROMPT = (
    "You are a dramatic geopolitics news narrator for a strategy game. "
    "Write punchy, vivid news-brief style text. "
    "Never mention game mechanics, points, or stats directly. "
    "Narrate as if reporting real-world geopolitics."
)


def _get_model():
    """Lazy-initialize the Gemini model. Returns None if unavailable."""
    global _model, _enabled
    if _enabled is False:
        return None
    if _model is not None:
        return _model

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _enabled = False
        log.info("GEMINI_API_KEY not set — LLM narration disabled")
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "temperature": 0.85,
                "max_output_tokens": 120,
                "top_p": 0.9,
            },
        )
        _enabled = True
        log.info("Gemini Flash narration enabled")
        return _model
    except ImportError:
        _enabled = False
        log.info("google-generativeai not installed — LLM narration disabled")
        return None
    except Exception as e:
        _enabled = False
        log.warning(f"Failed to initialize Gemini: {e}")
        return None


def _call(prompt: str, fallback: str) -> str:
    """Call the LLM with a prompt, returning fallback on any failure."""
    model = _get_model()
    if not model:
        return fallback
    try:
        response = model.generate_content(prompt)
        text = response.text.strip().strip('"')
        return text if text else fallback
    except Exception as e:
        log.debug(f"LLM call failed: {e}")
        return fallback


def enrich_action_result(player_name: str, action_result: str) -> str:
    """Enhance a player action result with more vivid narration."""
    prompt = (
        f"Rewrite as a 1-2 sentence news flash (max 40 words). "
        f"Keep all key facts about what happened and who is involved.\n\n"
        f"Nation: {player_name}\n"
        f"Event: {action_result}\n\n"
        f"News flash:"
    )
    return _call(prompt, action_result)


def enrich_world_event(
    headline: str, description: str, player_name: str
) -> tuple[str, str]:
    """Enhance a world event headline and description."""
    prompt = (
        f"Rewrite this world event as a vivid news headline (max 12 words) "
        f"and a one-sentence description (max 25 words). "
        f"Keep the core event.\n\n"
        f"Headline: {headline}\n"
        f"Details: {description}\n"
        f"Key nation: {player_name}\n\n"
        f"Format exactly as:\n"
        f"HEADLINE: <headline>\n"
        f"DETAIL: <description>"
    )
    result = _call(prompt, "")
    if not result:
        return headline, description

    try:
        new_headline = headline
        new_desc = description
        for line in result.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("HEADLINE:"):
                val = line.split(":", 1)[1].strip().strip('"')
                if val:
                    new_headline = val
            elif line.upper().startswith("DETAIL:"):
                val = line.split(":", 1)[1].strip().strip('"')
                if val:
                    new_desc = val
        return new_headline, new_desc
    except Exception:
        return headline, description


def enrich_ai_reaction(
    country_name: str,
    action_text: str,
    player_name: str,
    relationship: float,
) -> str:
    """Narrate an AI country's action more vividly."""
    rel_tone = (
        "allied" if relationship > 30
        else "hostile" if relationship < -30
        else "neutral"
    )
    prompt = (
        f"Rewrite as a 1-sentence diplomatic dispatch (max 30 words).\n\n"
        f"{country_name} ({rel_tone} toward {player_name}) acts:\n"
        f"{action_text}\n\n"
        f"Dispatch:"
    )
    return _call(prompt, action_text)


def is_enabled() -> bool:
    """Check if LLM narration is active."""
    _get_model()
    return _enabled is True
