"""LLM rewrite step with two providers, chosen by PP_PROVIDER:
  ollama    (default) local model via http://localhost:11434, free and private
  anthropic           Claude API, needs ANTHROPIC_API_KEY and credits

Flow: ask the model, validate every rewrite with guard.py, retry once telling
the model which rules it broke, and show nothing if it still fails. If the
provider itself is unreachable we fall back to a template so the extension
still shows something during development."""

import json
import logging
import os
import re
from collections import Counter

import anthropic
import httpx

from .analyze import Analysis
from .guard import Violation, filter_rewrites
from .schemas import SuggestRequest

log = logging.getLogger(__name__)

# Settings, each can be changed with an environment variable
PROVIDER = os.environ.get("PP_PROVIDER", "ollama")
TIMEOUT_S = float(os.environ.get("PP_LLM_TIMEOUT", "40"))
OLLAMA_URL = os.environ.get("PP_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("PP_OLLAMA_MODEL", "llama3.2:3b")
CLAUDE_MODEL = os.environ.get("PP_MODEL", "claude-opus-5-5")

SYSTEM = """You improve a user's draft prompt for an AI chat assistant. You output a better prompt that the user will send themselves. You never answer the draft.

You MAY add structure: ask the assistant to ask clarifying questions first, to state its assumptions, to use a format (steps, table, short paragraphs), or to cover certain aspects.
You MUST NOT choose anything the user did not state: no numbers, quantities, word limits, durations, budgets, dates, names, places, audiences, topics or products. If something important is unknown, tell the assistant to ask the user for it.

Other rules:
- Every rewrite is an instruction addressed to the assistant. Never put questions to the user in it; write "ask me ..." instead.
- Keep the user's intent and wording where possible. Stay short.
- Write in the same language as the draft.
- Give 1 to 3 distinct rewrites, best first.
- If the draft is casual conversation, a greeting, or not a request for work, return an empty list.

Examples:
Draft: plan my trip
{"rewrites": ["Help me plan a trip. First ask me the questions you need, such as where, when, budget and interests, then propose an itinerary organized day by day."]}

Draft: write an email
{"rewrites": ["Help me write an email. Ask me who it is for and what it should say, then draft it with a subject line and a clear closing."]}

Draft: explain blockchain
{"rewrites": ["Explain blockchain in plain language: start with the core idea, then an everyday analogy, then one real-world use. Afterwards, ask whether I want more technical depth."]}

Draft: fix my bug
{"rewrites": ["Help me fix a bug. Ask me for the code, the exact error message, what I expected and what happened instead, then explain the cause before giving the fix."]}

Draft: how was your day
{"rewrites": []}

Reply with ONLY a JSON object like {"rewrites": ["..."]}. No prose, no code fences."""

PLACEHOLDER_RULE = (
    "\n\nThe draft contains placeholders such as [EMAIL_1]. Copy them exactly as written. "
    "Never create new ones."
)

REWRITES_SCHEMA = {
    "type": "object",
    "properties": {"rewrites": {"type": "array", "items": {"type": "string"}}},
    "required": ["rewrites"],
}

# Matches placeholders like [EMAIL_1] that the extension puts in place of personal data
_HAS_PLACEHOLDER = re.compile(r"\[[A-Z][A-Z0-9_ ]*\]")

# One SDK client for the whole process (it reads ANTHROPIC_API_KEY itself)
_claude = anthropic.Anthropic()

# Process-lifetime counters: how often we retry, give up, or reject for each rule.
STATS: Counter[str] = Counter()


def _system_for(draft: str) -> str:
    """The system prompt, plus the placeholder rule when the draft contains [EMAIL_1]-style slots."""
    if _HAS_PLACEHOLDER.search(draft):
        return SYSTEM + PLACEHOLDER_RULE
    return SYSTEM


def _build_user_message(req: SuggestRequest, analysis: Analysis) -> str:
    """Everything the model should see about this draft, as one text block."""
    parts = [f"Draft prompt:\n{req.draft}"]

    if analysis.missing:
        parts.append("Likely missing: " + ", ".join(analysis.missing))

    # Up to the last 4 chat messages, for context
    if req.recent_messages:
        lines = []
        for message in req.recent_messages[-4:]:
            lines.append(f"{message.role}: {message.content}")
        parts.append("Recent conversation:\n" + "\n".join(lines))

    # Up to 3 of the user's earlier good prompts, so the rewrite matches their style
    if req.similar_prompts:
        lines = []
        for prompt in req.similar_prompts[:3]:
            lines.append(f"- {prompt}")
        parts.append("The user's past prompts that worked, for style:\n" + "\n".join(lines))

    return "\n\n".join(parts)


def _retry_message(user_message: str, problems: list[Violation]) -> str:
    """The same request again, plus the list of rules the first answer broke (each listed once)."""
    reasons = []
    for problem in problems:
        text = str(problem)
        if text not in reasons:
            reasons.append(text)

    lines = []
    for reason in reasons:
        lines.append(f"- {reason}")
    rules = "\n".join(lines)

    return (
        f"{user_message}\n\nYour previous answer was rejected for these reasons:\n{rules}\n"
        "Try again. Do not add numbers, placeholders or details that are not in the draft."
    )


def _clean_rewrites(items: list) -> list[str]:
    """Keep only non-empty strings (trimmed), at most 3."""
    result = []
    for item in items:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result[:3]


def _parse(text: str) -> list[str] | None:
    """Accept {"rewrites": [...]} or a bare [...], tolerating stray prose around it.
    Returns None when nothing parseable was found, [] when the model said 'no rewrite'."""
    # Try an object first, then a bare list
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        # From the first opening bracket to the last closing one
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start == -1 or end <= start:
            continue
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            continue  # not valid JSON: try the other bracket type

        if isinstance(data, dict):
            items = data.get("rewrites")
        else:
            items = data
        if isinstance(items, list):
            return _clean_rewrites(items)
    return None


def _fallback(req: SuggestRequest, analysis: Analysis) -> list[str]:
    """A fixed template, used only when the model can't be reached (keeps development usable)."""
    asks = "; ".join(analysis.missing)
    if not asks:
        asks = "more detail"
    return [f"{req.draft.strip()}\n\n(Stub rewrite, no LLM available. Add: {asks}.)"]


def _call_ollama(system: str, user_message: str) -> str:
    """Local model through Ollama's HTTP API. `format` makes it answer in our JSON shape."""
    res = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "format": REWRITES_SCHEMA,
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=TIMEOUT_S,
    )
    res.raise_for_status()
    return res.json()["message"]["content"]


def _call_claude(system: str, user_message: str) -> str:
    """Claude through the Anthropic SDK. Low effort: a short rewrite needs little thinking.
    max_retries=0 because we do our own single retry (with feedback) in generate_suggestions."""
    response = _claude.with_options(timeout=TIMEOUT_S, max_retries=0).messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=system,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": user_message}],
    )
    # A refusal has no usable text; treat it as "no rewrite" so nothing pops up
    if response.stop_reason == "refusal":
        return '{"rewrites": []}'

    # The reply can contain several blocks (e.g. thinking); keep only the text blocks
    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
    return text


def _complete(system: str, user_message: str) -> str:
    """Sends the request to whichever provider PP_PROVIDER chose."""
    if PROVIDER == "anthropic":
        return _call_claude(system, user_message)
    return _call_ollama(system, user_message)


def generate_suggestions(req: SuggestRequest, analysis: Analysis) -> list[str]:
    """Up to 3 checked rewrites, or [] when there is nothing good to show."""
    STATS["calls"] += 1
    system = _system_for(req.draft)
    user_message = _build_user_message(req, analysis)
    problems: list[Violation] = []
    try:
        for attempt in (1, 2):
            # First try: the plain request. Second try: the request plus what went wrong.
            if attempt == 1:
                message = user_message
            else:
                STATS["retried"] += 1
                message = _retry_message(user_message, problems)

            reply = _complete(system, message)
            parsed = _parse(reply)

            if parsed == []:
                STATS["no_rewrite_needed"] += 1
                return []  # the model judged the draft is not a task: no popup
            if parsed is None:
                problems = [Violation("format", "reply was not a JSON object with a 'rewrites' list")]
            else:
                # Drop every rewrite that breaks a rule in guard.py
                kept, problems = filter_rewrites(req.draft, parsed)
                if kept:
                    STATS["served"] += 1
                    return kept

            # This attempt failed: count and log each broken rule, then try again (or give up)
            problem_texts = []
            for problem in problems:
                STATS[f"rejected_{problem.rule}"] += 1
                problem_texts.append(str(problem))
            log.info("attempt %d rejected: %s", attempt, problem_texts)
    # The provider could not be reached or answered in an unexpected shape
    except (anthropic.AnthropicError, httpx.HTTPError, KeyError, TypeError) as e:
        STATS["provider_error"] += 1
        log.warning("LLM call failed (%s), using fallback: %s", PROVIDER, e)
        return _fallback(req, analysis)
    STATS["gave_up"] += 1
    return []  # both attempts failed validation: better no suggestion than a wrong one
