from langchain_core.prompts import ChatPromptTemplate

ANALYZE_SYSTEM = (
    "Ты — помощник ресторана, который анализирует свободный отзыв гостя.\n"
    "Выдели: краткое summary, общий sentiment (positive|neutral|negative), "
    "список topics, эмоциональный окрас (emotion).\n"
    "Отвечай строго JSON-объектом по заданной схеме."
)

SELECT_SYSTEM = (
    "Ты — помощник ресторана. По первоначальному отзыву гостя и доступному пулу вопросов "
    "выбери от {min} до {max} наиболее релевантных вопросов.\n"
    "Не задавай вопросы, чья метрика уже очевидна из отзыва. Верни JSON с массивом "
    "question_ids и кратким reasoning."
)

EXTRACT_SYSTEM = (
    "Извлеки структурированное значение ответа гостя на вопрос ресторана.\n"
    "Тип ожидается: {expected_type}. Если ответ не даёт уверенности — верни value=null.\n"
    "Для enum допустимы только значения из enum_values."
)

CARD_SYSTEM = (
    "Сформируй краткую карточку клиента (3–6 предложений) на основе отзыва, "
    "извлечённых метрик и диалога. Текст пишется как «третьим лицом для аналитика»."
)


def build_analyze_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", ANALYZE_SYSTEM),
            ("user", "Отзыв:\n{feedback_text}"),
        ]
    )


def build_select_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SELECT_SYSTEM),
            (
                "user",
                "Контекст отзыва (JSON):\n{feedback_summary}\n\nДоступный пул вопросов:\n{pool}",
            ),
        ]
    )


def build_extract_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", EXTRACT_SYSTEM),
            (
                "user",
                "Вопрос: {question_text}\nenum_values: {enum_values}\nОтвет гостя: {answer_text}",
            ),
        ]
    )


def build_card_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", CARD_SYSTEM),
            (
                "user",
                "Анализ отзыва (JSON):\n{feedback_summary}\n\nДиалог и ответы:\n{dialog}",
            ),
        ]
    )
