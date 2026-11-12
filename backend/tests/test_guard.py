import pytest

from app.guard import check_rewrite, filter_rewrites


def rules(draft: str, rewrite: str) -> set[str]:
    return {v.rule for v in check_rewrite(draft, rewrite)}


def test_clean_rewrite_passes():
    assert rules("plan my trip", "Help me plan a trip. First ask me where, when and what I like, then propose a day by day itinerary.") == set()


@pytest.mark.parametrize("rewrite", [
    "Plan a trip for 7 days with a detailed itinerary.",
    "Write a story within 500 words.",
    "Give me ideas with a $1000 budget.",
    "Use a 2.5 hour plan.",
])
def test_invented_numbers_rejected(rewrite):
    assert "invented_number" in rules("plan my trip", rewrite)


def test_numbers_already_in_draft_are_allowed():
    assert rules("give me 5 ideas for a trip", "Give me 5 ideas for a trip. Ask me what I enjoy first.") == set()


def test_numbered_list_markers_are_not_invented_numbers():
    rewrite = "Help me plan a trip:\n1. Ask me my preferences\n2) Then propose an itinerary"
    assert "invented_number" not in rules("plan my trip", rewrite)


def test_invented_placeholder_rejected():
    assert "invented_placeholder" in rules("write an email", "Write an email to [EMAIL_1] about [SOME_CONTEXT].")


def test_placeholder_from_draft_is_allowed():
    assert rules("email [EMAIL_1] about lunch", "Write an email to [EMAIL_1] about lunch. Ask me for the tone first.") == set()


def test_meta_talk_rejected_unless_draft_has_it():
    assert "meta" in rules("make it better", "Make the draft prompt clearer and more concise.")
    assert "meta" not in rules("improve the draft prompt below", "Improve the draft prompt below for clarity.")


def test_questions_to_the_user_rejected():
    assert "question_to_user" in rules("plan my trip", "Plan my trip. What is the purpose? Which destination?")


def test_question_allowed_when_draft_is_a_question():
    assert "question_to_user" not in rules("what is react?", "What is React and what problem does it solve?")


def test_echo_rejected_case_insensitively():
    assert "echo" in rules("Write code", "  write CODE ")


def test_blank_rejected():
    assert rules("write code", "  ") == {"empty"}


def test_too_long_rejected():
    assert "too_long" in rules("dogs", "Tell me about dogs. " * 60)


def test_filter_keeps_good_dedupes_and_reports_bad():
    kept, problems = filter_rewrites(
        "plan my trip",
        [
            "Plan a 7 day trip.",
            "Help me plan a trip. Ask me what I need first.",
            "help me plan a trip. ask me what I need first.",
            "Help me plan a trip and give me an itinerary.",
        ],
    )
    assert kept == [
        "Help me plan a trip. Ask me what I need first.",
        "Help me plan a trip and give me an itinerary.",
    ]
    assert [p.rule for p in problems] == ["invented_number"]
