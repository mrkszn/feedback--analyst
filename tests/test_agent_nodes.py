import pytest

from agent.nodes.analyze import FeedbackSummary, analyze_feedback
from agent.nodes.card import ClientCard, build_client_card
from agent.nodes.extract import extract_metric_from_answer
from agent.nodes.select import SelectedQuestions, select_adaptive_questions
from agent.prompts import (
    build_analyze_prompt,
    build_card_prompt,
    build_extract_prompt,
    build_select_prompt,
)

# --- prompts ---


def test_analyze_prompt_has_feedback_placeholder() -> None:
    p = build_analyze_prompt()
    msgs = p.format_messages(feedback_text="ужин был отличный")
    assert len(msgs) == 2
    assert "ужин был отличный" in str(msgs[1].content)


def test_select_prompt_has_pool_and_feedback() -> None:
    p = build_select_prompt()
    msgs = p.format_messages(feedback_summary="{}", pool="- 1: q", min=3, max=5)
    text = "\n".join(str(m.content) for m in msgs)
    assert "{}" in text
    assert "- 1: q" in text


def test_extract_prompt_has_question_and_answer() -> None:
    p = build_extract_prompt()
    msgs = p.format_messages(
        question_text="Скорость?", expected_type="number", enum_values=None, answer_text="5"
    )
    text = "\n".join(str(m.content) for m in msgs)
    assert "Скорость?" in text
    assert "5" in text


def test_card_prompt_has_dialog() -> None:
    p = build_card_prompt()
    msgs = p.format_messages(feedback_summary="{}", dialog="X")
    text = "\n".join(str(m.content) for m in msgs)
    assert "X" in text


# --- analyze_feedback ---


async def test_analyze_feedback_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = FeedbackSummary(summary="ok", sentiment="positive", topics=["food"], emotion="joy")

    async def fake_chat(messages, **kwargs):
        assert kwargs.get("response_model") is FeedbackSummary
        return expected

    monkeypatch.setattr("agent.nodes.analyze.chat_completion", fake_chat)
    result = await analyze_feedback("ужин был отличный")
    assert result == expected


async def test_analyze_empty_raises() -> None:
    with pytest.raises(ValueError):
        await analyze_feedback("   ")


# --- select_adaptive_questions ---


async def test_select_empty_pool_returns_empty() -> None:
    summary = FeedbackSummary(summary="x", sentiment="neutral", topics=[], emotion="")
    result = await select_adaptive_questions(summary, pool=[])
    assert result.question_ids == []


async def test_select_filters_unknown_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = FeedbackSummary(summary="x", sentiment="neutral", topics=[], emotion="")
    pool = [
        {"id": "1", "metric_key": "a", "text": "q1"},
        {"id": "2", "metric_key": "b", "text": "q2"},
        {"id": "3", "metric_key": "c", "text": "q3"},
    ]

    async def fake_chat(messages, **kwargs):
        return SelectedQuestions(question_ids=["1", "999", "2"], reasoning="r")

    monkeypatch.setattr("agent.nodes.select.chat_completion", fake_chat)
    result = await select_adaptive_questions(summary, pool, min_questions=2, max_questions=5)
    assert result.question_ids == ["1", "2", "3"][:3] or set(result.question_ids) >= {"1", "2"}
    assert "999" not in result.question_ids


async def test_select_pads_below_min(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = FeedbackSummary(summary="x", sentiment="neutral", topics=[], emotion="")
    pool = [
        {"id": "1", "metric_key": "a", "text": "q1"},
        {"id": "2", "metric_key": "b", "text": "q2"},
        {"id": "3", "metric_key": "c", "text": "q3"},
    ]

    async def fake_chat(messages, **kwargs):
        return SelectedQuestions(question_ids=["1"], reasoning="r")

    monkeypatch.setattr("agent.nodes.select.chat_completion", fake_chat)
    result = await select_adaptive_questions(summary, pool, min_questions=3, max_questions=5)
    assert len(result.question_ids) == 3
    assert "1" in result.question_ids


async def test_select_truncates_above_max(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = FeedbackSummary(summary="x", sentiment="neutral", topics=[], emotion="")
    pool = [{"id": str(i), "metric_key": f"m{i}", "text": f"q{i}"} for i in range(10)]

    async def fake_chat(messages, **kwargs):
        return SelectedQuestions(question_ids=[str(i) for i in range(10)], reasoning="r")

    monkeypatch.setattr("agent.nodes.select.chat_completion", fake_chat)
    result = await select_adaptive_questions(summary, pool, min_questions=3, max_questions=5)
    assert len(result.question_ids) == 5


# --- extract_metric_from_answer ---


async def test_extract_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.nodes.extract import _TextValue

    async def fake_chat(messages, **kwargs):
        return _TextValue(value="хорошо")

    monkeypatch.setattr("agent.nodes.extract.chat_completion", fake_chat)
    q = {"text": "Q?", "expected_type": "text"}
    assert await extract_metric_from_answer(question=q, answer_text="да") == "хорошо"


async def test_extract_number(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.nodes.extract import _NumberValue

    async def fake_chat(messages, **kwargs):
        return _NumberValue(value=4.0)

    monkeypatch.setattr("agent.nodes.extract.chat_completion", fake_chat)
    q = {"text": "Q?", "expected_type": "number"}
    assert await extract_metric_from_answer(question=q, answer_text="четыре") == 4.0


async def test_extract_enum_in_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.nodes.extract import _EnumValue

    async def fake_chat(messages, **kwargs):
        return _EnumValue(value="medium")

    monkeypatch.setattr("agent.nodes.extract.chat_completion", fake_chat)
    q = {"text": "Q?", "expected_type": "enum", "enum_values": ["low", "medium", "high"]}
    assert await extract_metric_from_answer(question=q, answer_text="средне") == "medium"


async def test_extract_enum_out_of_values_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.nodes.extract import _EnumValue

    async def fake_chat(messages, **kwargs):
        return _EnumValue(value="extreme")

    monkeypatch.setattr("agent.nodes.extract.chat_completion", fake_chat)
    q = {"text": "Q?", "expected_type": "enum", "enum_values": ["low", "high"]}
    assert await extract_metric_from_answer(question=q, answer_text="x") is None


async def test_extract_enum_without_values_raises() -> None:
    q = {"text": "Q?", "expected_type": "enum"}
    with pytest.raises(ValueError):
        await extract_metric_from_answer(question=q, answer_text="x")


async def test_extract_empty_answer_raises() -> None:
    q = {"text": "Q?", "expected_type": "text"}
    with pytest.raises(ValueError):
        await extract_metric_from_answer(question=q, answer_text="   ")


# --- build_client_card ---


async def test_build_card_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = ClientCard(
        summary_text="Клиент остался доволен и упомянул скорость сервиса.",
        sentiment="positive",
        topics=["service"],
    )

    async def fake_chat(messages, **kwargs):
        return expected

    monkeypatch.setattr("agent.nodes.card.chat_completion", fake_chat)
    summary = FeedbackSummary(summary="x", sentiment="positive", topics=["food"], emotion="joy")
    result = await build_client_card(feedback_summary=summary, answers=[])
    assert result.summary_text.startswith("Клиент")


async def test_build_card_too_short_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages, **kwargs):
        return ClientCard(summary_text="ok", sentiment="", topics=[])

    monkeypatch.setattr("agent.nodes.card.chat_completion", fake_chat)
    summary = FeedbackSummary(summary="x", sentiment="neutral", topics=[], emotion="")
    with pytest.raises(ValueError):
        await build_client_card(feedback_summary=summary, answers=[])


async def test_build_card_passes_through_sentiment_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat(messages, **kwargs):
        return ClientCard(
            summary_text="A very satisfactory long-enough summary text here.",
            sentiment="",
            topics=[],
        )

    monkeypatch.setattr("agent.nodes.card.chat_completion", fake_chat)
    summary = FeedbackSummary(
        summary="x", sentiment="positive", topics=["food", "service"], emotion="joy"
    )
    result = await build_client_card(feedback_summary=summary, answers=[])
    assert result.sentiment == "positive"
    assert result.topics == ["food", "service"]
