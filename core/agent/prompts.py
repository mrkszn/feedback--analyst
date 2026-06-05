from langchain_core.prompts import ChatPromptTemplate

ANALYZE_SYSTEM = (
    "Ты — помощник сервиса доставки еды, который анализирует свободный отзыв клиента "
    "о заказе и доставке.\n"
    "Выдели: краткое summary, общий sentiment (positive|neutral|negative), "
    "список topics (что именно клиент упомянул: еда, упаковка, курьер, время доставки, "
    "температура блюд, поддержка и т.п.), эмоциональный окрас (emotion).\n"
    "Отвечай строго JSON-объектом по заданной схеме."
)

SELECT_SYSTEM = (
    "Ты — помощник сервиса доставки еды. По первоначальному отзыву клиента и доступному "
    "пулу вопросов выбери от {min} до {max} наиболее релевантных вопросов.\n"
    "Не задавай вопросы, чья метрика уже очевидна из отзыва. Помни: между кухней и "
    "клиентом стоит курьер, поэтому впечатление складывается из двух частей — самой "
    "еды и доставки. Верни JSON с массивом question_ids и кратким reasoning."
)

EXTRACT_SYSTEM = (
    "Извлеки структурированное значение ответа клиента на вопрос сервиса доставки.\n"
    "Тип ожидается: {expected_type}. Если ответ не даёт уверенности — верни value=null.\n"
    "Для enum допустимы только значения из enum_values."
)

CARD_SYSTEM = (
    "Сформируй краткую карточку клиента (3–6 предложений) на основе отзыва о доставке, "
    "извлечённых метрик и диалога. Текст пишется как «третьим лицом для аналитика»: "
    "что заказал, как прошла доставка, что понравилось и что нет; отдельно сигналы "
    "по еде и по курьеру, если они звучат в диалоге."
)

DIALOGUE_SYSTEM = (
    "Ты — внимательный собеседник от лица сервиса доставки еды: тёплый, живой, с лёгкими "
    "эмодзи (не больше двух на сообщение). Контекст бизнеса: {restaurant_context}.\n"
    "Клиент только что оставил отзыв о своём заказе и доставке (анализ ниже). Веди живой "
    "3–5-турновый диалог: коротко эмпатично отреагируй и задай ОДИН органичный уточняющий "
    "вопрос (свой, не из заготовок). Если у клиента смешанные впечатления — мягко помогай "
    "разделить, что относится к самой еде/кухне, а что к курьеру/доставке. Никаких "
    "канцелярских формулировок («согласно опросу», «уточните пожалуйста»).\n"
    'Когда контекста достаточно для карточки клиента — transition="offer_survey", '
    'иначе "continue". Если turn_count >= max_turns - 1 — обязательно "offer_survey".\n'
    "bot_reply: 1–3 предложения, живой русский. insights — короткие key→value "
    "новых наблюдений за этот турн (опционально)."
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
                "Вопрос: {question_text}\nenum_values: {enum_values}\nОтвет клиента: {answer_text}",
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


def build_dialogue_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", DIALOGUE_SYSTEM),
            (
                "user",
                "Анализ отзыва (JSON): {feedback_summary}\n"
                "История диалога:\n{history}\n"
                "turn_count={turn_count} / max_turns={max_turns}\n"
                "Ответь и реши transition.",
            ),
        ]
    )
