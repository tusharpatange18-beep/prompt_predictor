"""Rule-based quality gate: is this draft weak enough to be worth a suggestion?

Scores 0..1 from five cheap signals. This is deliberately simple; Phase 3
replaces it with a trained classifier, and the eval set tells us if that helps.
"""

import re
from dataclasses import dataclass

SHOW_BELOW = 0.6
MIN_WORDS_TO_SUGGEST = 3

TASK_WORDS = {
    "write", "explain", "summarize", "summarise", "list", "create", "generate",
    "compare", "translate", "fix", "debug", "review", "analyze", "analyse",
    "draft", "build", "design", "plan", "convert", "refactor", "describe",
    "outline", "suggest", "recommend", "teach", "help",
}
FORMAT_WORDS = {
    "bullet", "bullets", "table", "json", "csv", "steps", "paragraph",
    "paragraphs", "words", "sentences", "short", "concise", "markdown", "code",
    "list", "outline", "tldr",
}
AUDIENCE_WORDS = {
    "beginner", "beginners", "expert", "professional", "casual", "formal",
    "audience", "tone", "student", "students", "manager", "kids", "child",
    "audience", "under", "within", "avoid", "only", "without", "must",
}
CONTEXT_WORDS = {"because", "so", "context", "background", "currently", "my", "our", "using", "for", "about"}


@dataclass
class Analysis:
    score: float
    missing: list[str]

    @property
    def show(self) -> bool:
        return self.score < SHOW_BELOW


def analyze(draft: str) -> Analysis:
    text = draft.strip()
    words = re.findall(r"[a-zA-Z']+", text.lower())  # lower-case words, no punctuation
    n = len(words)
    wordset = set(words)

    score = 0.0
    missing: list[str] = []

    # Each check below: `wordset & SOME_WORDS` is the set of words the two share,
    # so it is true when the draft contains at least one of those words.

    # A task word (write, explain, ...) or a question: +0.25
    if wordset & TASK_WORDS or text.endswith("?"):
        score += 0.25
    else:
        missing.append("a clear task")

    # Some context: at least 12 words and a context word (because, my, using, ...): +0.2
    if n >= 12 and wordset & CONTEXT_WORDS:
        score += 0.2
    else:
        missing.append("context or background")

    # An output format (table, bullets, steps, ...): +0.2
    if wordset & FORMAT_WORDS:
        score += 0.2
    else:
        missing.append("the output format")

    # An audience or a constraint (beginner, formal, avoid, ...): +0.15
    if wordset & AUDIENCE_WORDS:
        score += 0.15
    else:
        missing.append("audience or constraints")

    # Length: up to +0.2, reached at 25 words (longer drafts get no extra)
    length_part = n / 25
    if length_part > 1.0:
        length_part = 1.0
    score += length_part * 0.2

    return Analysis(score=round(score, 2), missing=missing)
