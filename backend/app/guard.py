"""Deterministic checks on LLM rewrites. The model is untrusted: whatever the
prompt says, a rewrite that changes the user's intent is worse than no popup.

A rewrite may add structure (format, depth, a request for clarifying
questions). It may not add facts the draft did not contain. We approximate
"facts" with the things a small model most often invents: numbers and
[PLACEHOLDER] slots. Known limit: spelled-out numbers ("three") and invented
topics are not caught; the eval read-through covers those.
"""

import re
from dataclasses import dataclass

MIN_CHARS = 3
ABS_MAX_CHARS = 700
MIN_MAX_CHARS = 240
MAX_GROWTH = 10  # rewrite may be at most this many times longer than the draft

_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_SLOT = re.compile(r"\[[A-Z][A-Z0-9_ ]*\]")
_META = re.compile(
    r"\b(?:the draft|draft prompt|the user'?s? (?:request|prompt|draft|message))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


def _numbers(text: str) -> set[str]:
    """All numbers in the text, ignoring list markers such as "1." or "2)" at line starts."""
    without_markers = _LIST_MARKER.sub("", text)
    return set(_NUMBER.findall(without_markers))


def check_rewrite(draft: str, rewrite: str) -> list[Violation]:
    """All rule violations for one rewrite. Empty list means it is acceptable."""
    draft = draft.strip()
    rewrite = rewrite.strip()
    found: list[Violation] = []

    if len(rewrite) < MIN_CHARS:
        return [Violation("empty", "rewrite is blank")]

    if rewrite.casefold() == draft.casefold():
        found.append(Violation("echo", "rewrite is identical to the draft"))

    # Set difference: numbers in the rewrite that were NOT in the draft
    new_numbers = _numbers(rewrite) - _numbers(draft)
    if new_numbers:
        found.append(Violation("invented_number", f"adds numbers the draft never had: {sorted(new_numbers)}"))

    # Same idea for [PLACEHOLDER] slots
    new_slots = set(_SLOT.findall(rewrite)) - set(_SLOT.findall(draft))
    if new_slots:
        found.append(Violation("invented_placeholder", f"adds placeholders the draft never had: {sorted(new_slots)}"))

    if _META.search(rewrite) and not _META.search(draft):
        found.append(Violation("meta", "talks about the draft instead of being the prompt"))

    # A rewrite is an instruction to the assistant. Extra questions mean the model is
    # talking to the user ("What is the purpose of the trip?") instead of telling the
    # assistant to ask. A question is fine when the draft was itself a question.
    if rewrite.count("?") > draft.count("?"):
        found.append(Violation("question_to_user", "asks the user questions; instruct the assistant to ask instead"))

    # Length limit: 10x the draft, but never below 240 or above 700 characters
    limit = MAX_GROWTH * len(draft)
    if limit < MIN_MAX_CHARS:
        limit = MIN_MAX_CHARS
    if limit > ABS_MAX_CHARS:
        limit = ABS_MAX_CHARS
    if len(rewrite) > limit:
        found.append(Violation("too_long", f"{len(rewrite)} chars, limit is {limit}"))

    return found


def filter_rewrites(draft: str, rewrites: list[str]) -> tuple[list[str], list[Violation]]:
    """Keep acceptable, distinct rewrites in order. Also returns every violation seen."""
    kept: list[str] = []
    seen: set[str] = set()
    problems: list[Violation] = []
    for raw in rewrites:
        rewrite = raw.strip()
        violations = check_rewrite(draft, rewrite)
        problems.extend(violations)
        key = rewrite.casefold()  # casefold = lower case, so "Plan" and "plan" count as the same
        if violations or key in seen:
            continue  # broken, or a duplicate of one we already kept
        seen.add(key)
        kept.append(rewrite)
    return kept, problems
