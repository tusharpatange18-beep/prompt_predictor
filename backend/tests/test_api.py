from fastapi.testclient import TestClient

from app import suggest as suggest_mod
from app.analyze import analyze
from app.main import app

client = TestClient(app)


def test_weak_prompt_scores_lower_than_strong():
    weak = analyze("write code")
    strong = analyze(
        "Write a Python function that parses ISO dates for a beginner audience, "
        "as a short code block with comments, and avoid external libraries."
    )
    assert weak.score < strong.score
    assert weak.show and not strong.show


def test_suggest_shape_and_gate(monkeypatch):
    monkeypatch.setattr(suggest_mod, "generate_suggestions", lambda req, a: ["better"])
    monkeypatch.setattr("app.main.generate_suggestions", lambda req, a: ["better"])

    r = client.post("/v1/suggest", json={"draft": "tell me about dogs", "site": "chatgpt"})
    body = r.json()
    assert r.status_code == 200
    assert body["show_suggestion"] is True
    assert body["suggestions"] == ["better"]
    assert set(body) >= {"suggestion_id", "score", "show_suggestion", "missing", "suggestions", "conflicts"}


def test_cors_preflight_from_extension():
    r = client.options(
        "/v1/suggest",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnop",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "chrome-extension://abcdefghijklmnop"


def test_parse_accepts_object_array_and_noise():
    assert suggest_mod._parse('{"rewrites": ["a", " b ", ""]}') == ["a", "b"]
    assert suggest_mod._parse('["x", "y"]') == ["x", "y"]
    assert suggest_mod._parse('Sure! {"rewrites": ["z"]} hope it helps') == ["z"]
    assert suggest_mod._parse('{"rewrites": []}') == []  # "no rewrite needed" is not a parse failure
    assert suggest_mod._parse("no json here") is None


def test_llm_failure_falls_back(monkeypatch):
    import httpx

    def boom(_system, _msg):
        raise httpx.ConnectError("ollama is not running")

    monkeypatch.setattr(suggest_mod, "PROVIDER", "ollama")
    monkeypatch.setattr(suggest_mod, "_call_ollama", boom)
    r = client.post("/v1/suggest", json={"draft": "tell me about dogs"})
    assert r.json()["show_suggestion"] is True
    assert "Stub rewrite" in r.json()["suggestions"][0]


def test_tiny_draft_never_shown():
    r = client.post("/v1/suggest", json={"draft": "hi"})
    assert r.json()["show_suggestion"] is False


def test_feedback_validates_action():
    assert client.post("/v1/feedback", json={"suggestion_id": "x", "action": "nope"}).status_code == 422
