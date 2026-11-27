import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .analyze import MIN_WORDS_TO_SUGGEST, analyze
from .schemas import FeedbackRequest, SuggestRequest, SuggestResponse
from .suggest import generate_suggestions

app = FastAPI(title="Prompt Predictions")

# Chrome sends a CORS preflight (OPTIONS) when the extension's host permission for
# this URL is withheld or not yet granted. Answering it makes the extension work either way.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)

FEEDBACK_LOG = Path(__file__).resolve().parent.parent / "data" / "feedback.jsonl"


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest) -> SuggestResponse:
    # 1) Cheap rule-based check: is the draft weak enough to be worth a suggestion?
    analysis = analyze(req.draft)
    long_enough = len(req.draft.split()) >= MIN_WORDS_TO_SUGGEST
    show = analysis.show and long_enough

    # 2) Only then ask the LLM (slow and, with Claude, paid)
    suggestions = []
    if show:
        suggestions = generate_suggestions(req, analysis)

    # The card appears only if the draft is weak AND we have at least one checked rewrite
    return SuggestResponse(
        suggestion_id=uuid.uuid4().hex,
        score=analysis.score,
        show_suggestion=show and bool(suggestions),
        missing=analysis.missing,
        suggestions=suggestions,
        conflicts=[],  # Phase 3: NLI contradiction check
    )


@app.post("/v1/feedback")
def feedback(req: FeedbackRequest):
    """Appends one line per accepted / edited / dismissed suggestion (JSON Lines file)."""
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "suggestion_id": req.suggestion_id,
        "action": req.action,
    }
    with FEEDBACK_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"ok": True}
