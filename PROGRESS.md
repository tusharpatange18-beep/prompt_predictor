# PROGRESS

## Learner profile
- FastAPI: has used it before (comfortable).
- TypeScript: a little familiar.
- Chrome extensions: currently exploring.
- On 2026-10-31 the user switched from mentor mode to "build Phase 1 for me". Phases 2-4 not started.

## Done
- Week 1 (user-written): MV3 skeleton, esbuild, input detection via MutationObserver, debounce.
- Phase 1 build (written by Claude, built and unit-tested, NOT yet verified live in ChatGPT):
  - extension: background worker (timeout 15 s), suggestion card (shadow DOM), PII stripping with reversible placeholders, accept/dismiss/edited feedback.
  - backend: POST /v1/suggest, POST /v1/feedback (jsonl log), rule-based gate, Claude rewrite with template fallback. 4 pytest tests pass.
  - evals: 50 weak prompts with ideal rewrites, plus a runner.

## Phase 1 gate: PASSED (2026-10-31)
- Live in ChatGPT: real rewrites from Ollama llama3.2:3b appear in the card.
- Quality findings from the first live test ("how was your day"):
  - The gate fired on casual small talk, which is a needless popup. Phase 2 goal.
  - The 3B model invented a constraint ("approx. 100-150 words") that the user never implied, which breaks the system prompt rule. Measure how often on the eval set.

## Eval baseline 1 (2026-10-31, ollama llama3.2:3b, 50 prompts, evals/run_eval.py)
- Stub 0%, empty 0%, echo 0%. Latency median 3.9 s, p90 7.5 s, max 9.1 s.
- Invented numbers 44%, verbose (>12x draft) 24%, mean overlap with ideal 0.13.
- Read-through findings:
  - Hallucinated specifics that change the user's intent ("7 days", "$1000 budget", "a new restaurant", "500 words").
  - Placeholder leakage: invents [EMAIL_1], [NAME_1], [SOME_CONTEXT] from the system prompt example. The extension would insert them literally, since the PII map has no entry.
  - Misreads meta drafts: "make it better" became "Make the draft prompt clearer...".
  - Good cases: "history of rome", "write code", "tell me about dogs".
- Eval flaw: many "ideal" rewrites invent specifics too (Lisbon, 4 kg). Overlap is a weak metric. Ideals for vague prompts should add structure, not facts.
- Candidate fixes: (1) prompt rule against specifics plus few-shot examples, mention placeholders only when the draft has them; (2) deterministic guard that drops suggestions with numbers or placeholders absent from the draft; (3) try a larger local model; (4) rewrite the ideals.

## Eval baseline 2 (after guard.py + new prompt + one retry)
- Empty 2% (1/50, "debug my api"), invented numbers 0%, verbose 0%, latency median 3.9 s, p90 6.2 s, max 11.1 s. 30 pytest tests pass.
- Caveat: "invented numbers 0%" uses the same rule as the guard, so it is a regression check, not independent evidence. The read-through is the real evidence.
- Fixed: hallucinated specifics, placeholder leakage, "make it better" meta-confusion.
- Remaining problems found by reading:
  - Mixed voice: rewrites contain questions aimed at the user ("Plan my trip. What's the purpose of the trip? ...") instead of instructing the assistant to ask.
  - "fix my bug" became "Describe the bug and how you would fix it", which misreads the task.
  - Many rewrites are "ask me questions". ChatGPT would ask anyway, so the real value must be tested on mid-quality prompts, not one-liners.
- Next: add 20-30 mid-quality prompts to the eval, add a voice check (rewrite must not contain questions addressed to the user), consider a bigger model, and log the retry rate.
- Old outputs are saved in evals/results_baseline1.jsonl.

## Eval baseline 3 (guard + voice rule + retry logging; 33 tests pass)
- Weak set (50): served 48, gave up 2 ("what should i name my company", "write a cover letter"), retried 25, latency median 3.3 s, p90 4.6 s, max 25.9 s.
  Rejections: too_long 19, question_to_user 7, invented_number 3. Half of all calls need a retry, mostly because of the length cap, which doubles latency for them.
- Mid set (25): served 25, retried 6, latency median 2.5 s.
- Fixed: "fix my bug" now reads correctly; voice is "ask me ..." instead of questions to the user.
- Remaining quality issues:
  - Every rewrite follows one template ("X. Ask me about A, B, C, then propose Y"), copied from the few-shot examples.
  - Occasional intent drift: "history of rome" became "Help me write a history of Rome".
  - Invented "e.g." options, e.g. "(e.g. JSON, assertions)" for unit tests.
- BIG FINDING: casual messages still trigger nonsense popups. 6 of 6 tested: "thanks that helped a lot" became "Help me thank someone...", "how was your day" became "Ask me how I can help you with your day...". The 3B model cannot judge "this is not a task", so the empty-list escape hatch does not work. Also "what is 15 percent of 80" is a complete question yet scores 0.03 on the keyword gate.
  The fix belongs in the gate (Phase 2): a conversational and complete-question filter that does not rely on the LLM.
- Tuning ideas: raise MIN_MAX_CHARS from 240 to about 320 to cut retries (measure with the retried counter); vary the few-shot examples.

## Current step
- Phase 1 gate: the card appears live in ChatGPT (verified with the stub on 2026-10-31, after adding CORS middleware for the extension origin).
- Now wiring real rewrites through Ollama (llama3.2:3b). The provider is chosen with PP_PROVIDER=ollama|anthropic. If Ollama is down, the backend falls back to the stub.
- Still to verify: clicking a suggestion inserts it into the ChatGPT box.

## How to run
1. Backend (from backend/): `.venv\Scripts\activate`, set `$env:ANTHROPIC_API_KEY`, then `uvicorn app.main:app --port 8000`.
2. Extension (from extension/): `npm run build`, reload it at chrome://extensions, refresh chatgpt.com.
3. Eval (from repo root): `backend\.venv\Scripts\python evals\run_eval.py --limit 5`.
4. Tests (from backend/): `.venv\Scripts\python -m pytest -q`.

## Next
- Phase 2: IndexedDB history, embeddings, retrieve.py, replace the rule-based gate tuning with data, measure fewer needless popups.

## Revisit / known issues
- Default model is claude-opus-5-5 (override with PP_MODEL). It may be slow for a live popup. Try claude-haiku-5-5 or claude-sonnet-5-5 and compare latency against rewrite quality on the eval set.
- The heuristic score is gameable: the fallback stub scores higher just by containing keywords. Do not trust "mean uplift" without reading outputs. Build an LLM or human judge in Phase 2.
- PII: regex catches emails, phones, cards, API keys only. Names and places (e.g. in the Step 2 test) still go to the backend. Needs an NER step.
- Accepted text is inserted via document.execCommand (deprecated but the only approach that works with ProseMirror). Verify in the live page.
- ChatGPT selectors are brittle; keep them in sites/chatgpt.ts.
- Feedback "edited" is inferred when the draft changes after accepting; refine later.
- recent_messages and similar_prompts are sent empty until Phases 2-3.
- Unanswered check questions: why route backend calls via the service worker; why attach the input listener once; why read the draft inside the debounced callback.
- typescript ^7.0.2: typecheck passed.
