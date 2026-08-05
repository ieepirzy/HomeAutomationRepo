"""Morning briefing text generation.

Tone: calm, operational, concise, non-judgmental, non-nagging (spec
section 14). Uses Claude for the natural-language pass; falls back to a
deterministic template built from the same structured facts if the LLM
call fails or refuses, so a broken/rate-limited API key never blocks the
wake flow — it just produces a plainer briefing.

Never invents data: weather and priorities are omitted from both the
prompt and the template if not supplied.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from . import config

logger = logging.getLogger("briefing.text")

SYSTEM_PROMPT = """\
You write a short spoken morning briefing for someone who has just gotten \
out of bed. Read it aloud in your head before answering — it will be \
played as audio while they walk to the kitchen.

Tone: calm, operational, concise, non-judgmental, non-nagging. Never \
mention streaks, wake times, or missed days as a scold — the streak is \
informational, not a performance review. Do not use exclamation points, \
emoji, or hype language ("Great job!", "You've got this!"). Do not \
invent information that wasn't provided to you — if weather or \
priorities are missing, simply don't mention them.

Structure, in order, using only the sections you have real data for:
1. A brief greeting by name.
2. Current wake streak, stated plainly as a fact (only if provided).
3. Weather, in one sentence (only if provided).
4. The one to three priorities for today (only if provided).

Keep the whole thing under 70 words. Output only the briefing text — no \
preamble, no headers, no markdown.\
"""


@dataclass
class BriefingInputs:
    name: str
    current_streak: Optional[int]
    weather_summary: Optional[str]
    priorities: list[str]


def build_deterministic_template(inputs: BriefingInputs) -> str:
    """Zero-dependency fallback. Must never fail and must never invent
    data — every clause is conditional on the input actually being
    present."""
    parts = [f"Good morning, {inputs.name}."]

    if inputs.current_streak is not None and inputs.current_streak > 0:
        day_word = "day" if inputs.current_streak == 1 else "days"
        parts.append(f"Current streak: {inputs.current_streak} {day_word}.")

    if inputs.weather_summary:
        parts.append(f"Weather: {inputs.weather_summary}.")

    if inputs.priorities:
        if len(inputs.priorities) == 1:
            parts.append(f"Today's priority: {inputs.priorities[0]}.")
        else:
            joined = "; ".join(inputs.priorities[:3])
            parts.append(f"Today's priorities: {joined}.")

    return " ".join(parts)


def _user_prompt(inputs: BriefingInputs) -> str:
    lines = [f"Name: {inputs.name}"]
    if inputs.current_streak is not None:
        lines.append(f"Current wake streak: {inputs.current_streak} days")
    if inputs.weather_summary:
        lines.append(f"Weather: {inputs.weather_summary}")
    if inputs.priorities:
        lines.append("Priorities today: " + "; ".join(inputs.priorities[:3]))
    if len(lines) == 1:
        lines.append("(No other data available today — greeting only.)")
    return "\n".join(lines)


async def generate_briefing_text(inputs: BriefingInputs) -> tuple[str, bool]:
    """Returns (text, used_llm). used_llm is False whenever the
    deterministic fallback was used, for observability/logging."""
    if not config.ANTHROPIC_API_KEY:
        logger.info("no ANTHROPIC_API_KEY configured, using deterministic template")
        return build_deterministic_template(inputs), False

    try:
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        # This is a short, low-stakes daily generation task — effort:low
        # is the right cost/latency tradeoff (see project docs on
        # matching effort to task complexity). Adaptive thinking is left
        # at its default rather than explicitly disabled, since the
        # target model may reject an explicit "disabled" setting at
        # higher effort combinations and low effort is cheap regardless.
        response = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": _user_prompt(inputs)}],
        )

        if response.stop_reason == "refusal":
            logger.warning("briefing generation refused by model, using deterministic template")
            return build_deterministic_template(inputs), False

        text_blocks = [block.text for block in response.content if block.type == "text"]
        text = " ".join(text_blocks).strip()
        if not text:
            logger.warning("briefing generation returned empty text, using deterministic template")
            return build_deterministic_template(inputs), False

        return text, True

    except Exception as exc:  # noqa: BLE001 - any failure must fall back, never propagate
        logger.warning("briefing LLM call failed (%s), using deterministic template", exc)
        return build_deterministic_template(inputs), False
