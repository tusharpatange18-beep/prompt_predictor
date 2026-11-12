"""Run every weak prompt through the live pipeline and count specific failures.

Usage (from repo root):  backend/.venv/Scripts/python evals/run_eval.py [--limit N]

Automatic checks are rough proxies. They find candidates for failure; the real
judge is you reading evals/results.jsonl. Checks:
  stub      the LLM call failed and the template was used
  empty     no suggestion came back
  echo      the suggestion is just the draft again
  invented  the suggestion adds numbers the draft did not contain (e.g. "100 words")
  verbose   the suggestion is more than 12x longer than the draft
  overlap   word overlap (F1) with the ideal rewrite, higher is closer
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.analyze import analyze  # noqa: E402
from app.schemas import SuggestRequest  # noqa: E402
from app.suggest import PROVIDER, STATS, generate_suggestions  # noqa: E402

STOP = set("a an the to of and or in on for with is are be it this that you your my me i as at by from".split())


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP}


def f1(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    common = len(wa & wb)
    if not common:
        return 0.0
    p, r = common / len(wa), common / len(wb)
    return 2 * p * r / (p + r)


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--file", default="prompts.jsonl", help="file inside evals/ (e.g. prompts_mid.jsonl)")
    args = ap.parse_args()

    src = ROOT / "evals" / args.file
    rows = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = rows[: args.limit]
    print(f"provider={PROVIDER}  file={args.file}  prompts={len(rows)}\n")

    out = []
    for i, row in enumerate(rows, 1):
        weak = row["weak"]
        a = analyze(weak)
        t0 = time.time()
        suggestions = generate_suggestions(SuggestRequest(draft=weak), a)
        secs = time.time() - t0
        best = suggestions[0] if suggestions else ""

        flags = {
            "gate": a.show,
            "stub": "Stub rewrite" in best,
            "empty": not best,
            "echo": bool(best) and best.strip().lower() == weak.strip().lower(),
            "invented": bool(numbers(best) - numbers(weak)),
            "verbose": bool(best) and len(best) > 12 * max(len(weak), 20),
        }
        out.append({**row, "suggestion": best, "all": suggestions, "secs": round(secs, 1),
                    "overlap": round(f1(best, row["ideal"]), 2), **flags})
        bad = [k for k in ("stub", "empty", "echo", "invented", "verbose") if flags[k]]
        print(f"{i:2d}/{len(rows)} {secs:4.1f}s  {weak!r:38}  {','.join(bad) or 'ok'}")

    results = ROOT / "evals" / f"results_{src.stem}.jsonl"
    results.write_text("\n".join(json.dumps(r) for r in out), encoding="utf-8")

    n = len(out)
    pct = lambda key: f"{sum(r[key] for r in out)}/{n} ({100 * sum(r[key] for r in out) / n:.0f}%)"
    secs = sorted(r["secs"] for r in out)
    print("\n=== Summary ===")
    print(f"gate fired:        {pct('gate')}   (all inputs are weak, so this should be ~100%)")
    print(f"stub fallback:     {pct('stub')}")
    print(f"empty:             {pct('empty')}")
    print(f"echo of draft:     {pct('echo')}")
    print(f"invented numbers:  {pct('invented')}")
    print(f"verbose (>12x):    {pct('verbose')}")
    print(f"mean overlap w/ ideal: {sum(r['overlap'] for r in out) / n:.2f}")
    print(f"latency: median {secs[n // 2]:.1f}s, p90 {secs[int(n * 0.9) - 1]:.1f}s, max {secs[-1]:.1f}s")
    print(f"pipeline counters: {dict(STATS)}")
    print(f"\nRead {results.relative_to(ROOT)} for the real verdict.")


if __name__ == "__main__":
    main()
