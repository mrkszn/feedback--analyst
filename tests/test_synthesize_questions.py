import pytest

from agent.nodes.synthesize_questions import (
    QuestionDraft,
    _QuestionDraftList,
    regenerate_single_question,
    synthesize_questions,
)

# --- synthesize_questions ---


async def test_synthesize_empty_transcript_raises() -> None:
    with pytest.raises(ValueError):
        await synthesize_questions("   ", count=3, restaurant_context="ctx")


async def test_synthesize_zero_count_raises() -> None:
    with pytest.raises(ValueError):
        await synthesize_questions("надо опросить", count=0, restaurant_context="ctx")


@pytest.mark.parametrize(
    "draft",
    [
        QuestionDraft(text="Открытый отзыв?", metric_key="open", expected_type="text"),
        QuestionDraft(text="Оценка 1-5?", metric_key="rating", expected_type="number"),
        QuestionDraft(text="Понравилось?", metric_key="liked", expected_type="boolean"),
        QuestionDraft(
            text="Что заказали?",
            metric_key="dish",
            expected_type="enum",
            enum_values=["суп", "салат", "стейк"],
        ),
    ],
)
async def test_synthesize_returns_each_type(
    monkeypatch: pytest.MonkeyPatch, draft: QuestionDraft
) -> None:
    captured: dict = {}

    async def fake_chat(messages, **kwargs):
        captured["response_model"] = kwargs.get("response_model")
        return _QuestionDraftList(drafts=[draft])

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("text", count=3, restaurant_context="ctx")
    assert len(result) == 1
    assert result[0].expected_type == draft.expected_type
    assert result[0].text == draft.text
    assert captured["response_model"] is _QuestionDraftList


async def test_synthesize_enum_with_valid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(
                    text="Какой соус?",
                    metric_key="sauce",
                    expected_type="enum",
                    enum_values=["сырный", "томатный", "острый"],
                )
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("надо спросить про соус", count=1, restaurant_context="")
    assert len(result) == 1
    assert result[0].enum_values is not None
    assert 2 <= len(result[0].enum_values) <= 5


async def test_synthesize_drops_enum_with_one_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """enum с <2 значений невалидно и должно быть отфильтровано."""

    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(
                    text="Solo enum",
                    metric_key="solo",
                    expected_type="enum",
                    enum_values=["only"],
                ),
                QuestionDraft(
                    text="Open",
                    metric_key="open",
                    expected_type="text",
                ),
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("transcript", count=2, restaurant_context="")
    assert len(result) == 1
    assert result[0].metric_key == "open"


async def test_synthesize_drops_enum_with_six_values(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(
                    text="Big enum",
                    metric_key="big",
                    expected_type="enum",
                    enum_values=["a", "b", "c", "d", "e", "f"],
                ),
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("t", count=3, restaurant_context="")
    assert result == []


async def test_synthesize_caps_at_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """Если LLM вернёт больше count — обрезаем."""

    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(text=f"Q{i}", metric_key=f"m{i}", expected_type="text")
                for i in range(10)
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("t", count=3, restaurant_context="")
    assert len(result) == 3


async def test_synthesize_count_n_returns_at_most_n(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(text="Q1", metric_key="m1", expected_type="text"),
                QuestionDraft(text="Q2", metric_key="m2", expected_type="number"),
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("t", count=5, restaurant_context="")
    assert len(result) <= 5


async def test_synthesize_filters_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(text="  ", metric_key="m1", expected_type="text"),
                QuestionDraft(text="ok", metric_key="m2", expected_type="text"),
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("t", count=2, restaurant_context="")
    assert len(result) == 1
    assert result[0].metric_key == "m2"


async def test_synthesize_clears_enum_values_for_non_enum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_chat(messages, **kwargs):
        return _QuestionDraftList(
            drafts=[
                QuestionDraft(
                    text="open",
                    metric_key="open",
                    expected_type="text",
                    enum_values=["leak", "junk"],
                ),
            ]
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await synthesize_questions("t", count=1, restaurant_context="")
    assert result[0].enum_values is None


# --- regenerate_single_question ---


async def test_regenerate_returns_distinct_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    existing = [
        QuestionDraft(text="A?", metric_key="a", expected_type="text"),
        QuestionDraft(text="B?", metric_key="b", expected_type="number"),
    ]
    new_draft = QuestionDraft(text="C?", metric_key="c", expected_type="boolean")

    async def fake_chat(messages, **kwargs):
        captured["response_model"] = kwargs.get("response_model")
        captured["messages"] = messages
        return new_draft

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    result = await regenerate_single_question(
        transcript="t",
        current_draft=existing[0],
        all_drafts=existing,
        restaurant_context="ctx",
    )
    assert result == new_draft
    assert result.text not in {d.text for d in existing}
    assert result.metric_key not in {d.metric_key for d in existing}
    assert captured["response_model"] is QuestionDraft


async def test_regenerate_passes_all_drafts_in_user_msg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = [
        QuestionDraft(text="HelloWorld?", metric_key="hw", expected_type="text"),
    ]

    async def fake_chat(messages, **kwargs):
        return QuestionDraft(text="New?", metric_key="new", expected_type="text")

    captured: dict = {}

    async def capturing(messages, **kwargs):
        captured["messages"] = messages
        return await fake_chat(messages, **kwargs)

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", capturing)
    await regenerate_single_question(
        transcript="t",
        current_draft=existing[0],
        all_drafts=existing,
        restaurant_context="ctx",
    )
    user_content = "\n".join(m["content"] for m in captured["messages"] if m["role"] == "user")
    assert "HelloWorld?" in user_content


async def test_regenerate_empty_transcript_raises() -> None:
    with pytest.raises(ValueError):
        await regenerate_single_question(
            transcript="  ",
            current_draft=QuestionDraft(text="a", metric_key="a", expected_type="text"),
            all_drafts=[],
            restaurant_context="ctx",
        )


async def test_regenerate_invalid_enum_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages, **kwargs):
        return QuestionDraft(
            text="bad",
            metric_key="bad",
            expected_type="enum",
            enum_values=["one"],
        )

    monkeypatch.setattr("agent.nodes.synthesize_questions.chat_completion", fake_chat)
    with pytest.raises(ValueError):
        await regenerate_single_question(
            transcript="t",
            current_draft=QuestionDraft(text="x", metric_key="x", expected_type="text"),
            all_drafts=[],
            restaurant_context="ctx",
        )
