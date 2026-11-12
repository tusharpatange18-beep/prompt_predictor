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
    words = re.findall(r"[a-zA-Z']+", text.lower())
    n = len(words)
    wordset = set(words)

    score = 0.0
    missing: list[str] = []

    if wordset & TASK_WORDS or text.endswith("?"):
        score += 0.25
    else:
        missing.append("a clear task")

    if n >= 12 and wordset & CONTEXT_WORDS:
        score += 0.2
    else:
        missing.append("context or background")

    if wordset & FORMAT_WORDS:
        score += 0.2
    else:
        missing.append("the output format")

    if wordset & AUDIENCE_WORDS:
        score += 0.15
    else:
        missing.append("audience or constraints")

    score += min(n / 25, 1.0) * 0.2

    return Analysis(score=round(score, 2), missing=missing)
