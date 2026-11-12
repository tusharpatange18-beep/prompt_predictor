import json

import pytest

from app import suggest as s
from app.analyze import analyze
from app.schemas import SuggestRequest


def run(draft: str, replies: list[str], monkeypatch):
    """Drive generate_suggestions with canned model replies; returns (result, messages sent)."""
    sent: list[str] = []
    queue = list(replies)

    def fake(_system, message):
        sent.append(message)
        return queue.pop(0)

    monkeypatch.setattr(s, "_complete", fake)
    req = SuggestRequest(draft=draft)
    return s.generate_suggestions(req, analyze(draft)), sent


def reply(*rewrites: str) -> str:
    return json.dumps({"rewrites": list(rewrites)})


GOOD = "Help me plan a trip. Ask me what I need first, then propose an itinerary."
BAD = "Plan a 7 day trip with a $1000 budget."


def test_good_reply_passes_through_without_retry(monkeypatch):
    out, sent = run("plan my trip", [reply(GOOD)], monkeypatch)
    assert out == [GOOD]
    assert len(sent) == 1


def test_bad_reply_triggers_one_retry_that_names_the_rule(monkeypatch):
    out, sent = run("plan my trip", [reply(BAD), reply(GOOD)], monkeypatch)
    assert out == [GOOD]
    assert len(sent) == 2
    assert "invented_number" in sent[1]


def test_still_bad_after_retry_shows_nothing(monkeypatch):
    out, sent = run("plan my trip", [reply(BAD), reply(BAD)], monkeypatch)
    assert out == []
    assert len(sent) == 2  # exactly one retry, never a loop


def test_only_valid_rewrites_survive_a_mixed_reply(monkeypatch):
    out, _ = run("plan my trip", [reply(BAD, GOOD)], monkeypatch)
    assert out == [GOOD]


def test_model_saying_no_rewrite_needed_shows_nothing_and_does_not_retry(monkeypatch):
    out, sent = run("how was your day", [reply()], monkeypatch)
    assert out == []
    assert len(sent) == 1


def test_unparseable_reply_is_retried_then_dropped(monkeypatch):
    out, sent = run("plan my trip", ["sorry, I can't do that", "still not json"], monkeypatch)
    assert out == []
    assert "format" in sent[1]


def test_unparseable_then_good_recovers(monkeypatch):
    out, _ = run("plan my trip", ["oops", reply(GOOD)], monkeypatch)
    assert out == [GOOD]


def test_stats_count_each_outcome(monkeypatch):
    s.STATS.clear()
    run("plan my trip", [reply(GOOD)], monkeypatch)
    run("plan my trip", [reply(BAD), reply(GOOD)], monkeypatch)
    run("plan my trip", [reply(BAD), reply(BAD)], monkeypatch)
    run("how was your day", [reply()], monkeypatch)
    assert s.STATS["calls"] == 4
    assert s.STATS["served"] == 2
    assert s.STATS["retried"] == 2
    assert s.STATS["gave_up"] == 1
    assert s.STATS["no_rewrite_needed"] == 1
    assert s.STATS["rejected_invented_number"] == 3


def test_placeholder_rule_only_added_when_draft_has_placeholders():
    assert "Copy them exactly" not in s._system_for("write an email")
    assert "Copy them exactly" in s._system_for("email [EMAIL_1] about lunch")


def test_system_prompt_no_longer_teaches_placeholders_by_example():
    # The 3B model copied "[EMAIL_1]" from the old prompt into unrelated rewrites.
    assert "[EMAIL_1]" not in s._system_for("write an email")
