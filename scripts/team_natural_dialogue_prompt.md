# Team prompt — `fn-guest-natural-dialogue` (T2 Integration, ~2 часа)

> **Архитектор → команда:** добавить в guest-бот **живую разговорную фазу** между приёмом отзыва и опросом. Сейчас бот сразу после `/start` + первого сообщения клиента начинает «допрос» по вопросам из admin-пула — UX сухой и опросный. Цель: гость сначала **поговорил** с ботом 3–5 турнов, бот собрал контекст для карточки клиента, а потом **тонко предложил** пройти опрос за скидку. Скидку дать пока нельзя (Cmd #4 не сделан), но **предложение** + согласие/отказ — уже должны работать.

## Required reads (в первый ход)

1. `/Users/markdekker/.claude/plans/imperative-stirring-dove.md` — секция «Этап 2A» + «Архитектурный инвариант данных» (структурное → SQL, свободное → vector). Не нарушать.
2. `docs/GIT.md` — формат коммитов (Conventional Commits, ≤72 заголовок, 1 функция = 1 commit или 1 атомарный logical step).
3. `bot_guest/handlers/feedback.py` — текущий flow `AWAITING_FEEDBACK → IN_INTERVIEW`.
4. `bot_common/fsm/states.py` — текущие states.
5. `agent/nodes/analyze.py`, `agent/nodes/extract.py`, `agent/nodes/card.py` — существующие LLM узлы; их **не ломать**.
6. `agent/prompts.py` — паттерн ChatPromptTemplate.
7. `config.py` — есть `restaurant_context` env, **ИСПОЛЬЗОВАТЬ его как контекст для тона**.

## Goal (что должно работать end-to-end после команды)

1. Гость пишет `/start` → **дружелюбное** приветствие с эмодзи (не сухое «Здравствуйте! Поделитесь впечатлениями...»). 1–2 предложения.
2. Гость пишет текст или voice-отзыв.
3. Бот анализирует (existing `analyze_feedback`), но **НЕ переходит сразу к interview**. Вместо этого:
4. Бот отвечает **эмпатично, живо, с эмодзи**, и задаёт **1 органичный уточняющий вопрос** — _не из admin-пула_, а сгенерированный LLM на основе отзыва.
5. Гость отвечает (текст или voice).
6. Бот снова реагирует + уточняет. **3–5 турнов суммарно** (включая первый ответ из шага 4).
7. Когда LLM решает «контекста достаточно» **ИЛИ** превышено 5 турнов — бот делает **тонкое предложение опроса** с inline-кнопками:
   - `[💛 Давайте]` → переход в `IN_INTERVIEW` (existing flow остаётся как был)
   - `[Нет, спасибо]` → straight to finalize: `build_client_card` собирает карточку из всего разговора (raw feedback + все турны) → save → прощальное сообщение с эмодзи
8. Если pool вопросов пуст (admin не настроил) — после набора контекста ботом всё равно благодарит и финалит без опроса, без оффера скидки. Не молчит.

**Архитектурный инвариант сохраняется:** все слова из IN_DIALOGUE — это «свободная conversation» → попадают в `client_cards.summary_text` → Pinecone vector. Структурные ответы из IN_INTERVIEW (если гость согласился) — в `session_answers.marked_value`. Никакого смешения.

## Состояние ботов (что вне твоего scope)

- Admin-бот, voice question advisor (Cmd #2), reward system (Cmd #4) — **не трогать**.
- Существующие тесты — все 177 должны продолжать проходить. Если ломаешь — это регрессия.

## Файлы

### Создать

| Файл | Что |
|---|---|
| `agent/nodes/dialogue.py` | `continue_dialogue(feedback_summary, history, restaurant_context, turn_count) -> DialogueTurn` — LLM узел. Возвращает structured: `bot_reply: str` (русский, живой, ≤3 предложения, эмодзи разумно), `transition: Literal["continue", "offer_survey"]`, `running_context: dict` (накопленные insights для card). |
| `bot_guest/handlers/dialogue.py` | Handlers: `guest_dialogue_text` (F.text в state IN_DIALOGUE), `guest_dialogue_voice` (F.voice). Цикл: Whisper если voice → save user message → вызвать `continue_dialogue` → save bot message → если transition=offer_survey → переход к next step. |
| `bot_guest/handlers/survey_consent.py` | Handler для inline-кнопок `[💛 Давайте]` / `[Нет, спасибо]` после оффера. callback_data `survey:yes` / `survey:no`. Yes → IN_INTERVIEW (текущий путь). No → straight `_finalize_session` с накопленным history. |
| `tests/test_agent_dialogue.py` | Mock OpenAI: проверки что `continue_dialogue` возвращает валидный transition; при turn_count=5 → forced offer_survey; pydantic model валидируется. |
| `tests/test_guest_dialogue_handler.py` | Mock bot+aiogram+OpenAI: проверки FSM-переходов, что accumulated history передаётся корректно, voice через Whisper включается. |
| `tests/test_guest_survey_consent.py` | callback yes → переход в IN_INTERVIEW, callback no → finalize вызван. |

### Изменить

| Файл | Что |
|---|---|
| `bot_common/fsm/states.py` | Добавить `GuestFlow.IN_DIALOGUE`, `GuestFlow.AWAITING_SURVEY_CONSENT`. **НЕ удалять** существующие states — IN_INTERVIEW по-прежнему нужен. |
| `bot_guest/handlers/start.py` | Изменить текст приветствия на живой с эмодзи. Примерный тон: «Привет! 👋 Расскажи, как тебе у нас сегодня? Можешь голосом или текстом, как удобнее.» (точную формулировку дай согласовать с тоном из restaurant_context). |
| `bot_guest/handlers/feedback.py` | После `analyze_feedback` + `save_feedback_summary`: **НЕ переходить в IN_INTERVIEW сразу**. Вместо этого: переход в `IN_DIALOGUE`, инициализировать FSM data (`history=[]`, `turn_count=0`, `running_context={}`), вызвать `continue_dialogue` для первого bot-турна, отправить ответ гостю. Текущий empty-pool ветка (ddb38bb) пересматривается — теперь даже при пустом пуле бот должен пройти разговорную фазу и закончить «спасибо» без опроса. |
| `bot_guest/__main__.py` | Подключить новый router (`dialogue.router`, `survey_consent.router`). Порядок: dialogue/consent **ДО** существующего interview, чтобы FSM filters правильно сматчились. |
| `agent/prompts.py` | Добавить prompt builder для dialogue node. Тон: **тёплый, живой, с эмодзи, эмпатичный, не льстивый**. Использовать `restaurant_context` как часть system. Forbidden: «согласно нашему опросу», «как было бы вам комфортнее ответить» — никакой бюрократии. Подсмотри тональность из `need-eat/lib/prompts/system.ts` (концептуальный референс, не код). |

### Спецификация `continue_dialogue` (точная)

```python
class DialogueTurn(BaseModel):
    bot_reply: str = Field(..., description="Живой эмпатичный ответ гостю, 1-3 предложения, разрешены эмодзи (не более 2 на сообщение). Без вопросительной анкеты.")
    transition: Literal["continue", "offer_survey"] = Field(
        ..., description="continue = ещё минимум один тур; offer_survey = достаточно контекста, пора предлагать опрос за скидку"
    )
    insights: dict[str, str] = Field(
        default_factory=dict,
        description="Свободные ключ-значение пары, которые бот извлёк из текущего тура. Например {'preference': 'предпочитает острое', 'mood': 'был с детьми, расслабленный'}. Накапливаются в running_context."
    )

async def continue_dialogue(
    *,
    feedback_summary: FeedbackSummary,           # from analyze_feedback
    history: list[dict],                          # [{role: user|bot, content: str}, ...]
    restaurant_context: str,                      # settings.restaurant_context
    turn_count: int,                              # сколько турнов уже было
    max_turns: int = 5,                           # хардлимит — после 5 принудительно offer_survey
) -> DialogueTurn: ...
```

### Спецификация survey-оффера

Текст: что-то вроде:
> «Спасибо за разговор! 🙏 У ресторана есть пара коротких вопросов специально под твой отзыв — займут минутку. За ответы я подарю скидку 🎁 на следующий визит. Хочешь попробовать?»

inline_keyboard:
```
[💛 Давайте]   [Нет, спасибо]
```

callback_data: `survey:yes` / `survey:no`.

**Если pool вопросов пуст:** survey-оффер **не показываем**. Бот говорит «Спасибо большое за рассказ! 🙏 Передам владельцу. Хорошего дня! ☀️» и финалит. Это replaces current empty-pool branch.

## Жёсткие правила (учить уроки прошлых сессий)

1. **Bash discipline** (из `phase_2a_prompt.md`): один Bash = одна команда, никаких `&&`, `;`, `|`. Все пути внутри `telegram-waiter/`.
2. **Naming**: при спавне Agent — используй `lead` (или `coord`), НЕ `team-lead` (collision с parent).
3. **Commit-before-next**: каждый logical step → отдельный коммит. Запрещено уезжать с uncommitted WIP.
4. **NEVER discard untracked**: в wind-down или recovery — `git status -uall` первым, если есть незакоммиченное и тесты зелёные → wip-коммит, не сбрасывать.
5. **Reuse existing**: не переписывай Whisper-обёртку, OpenAI-chat, save_session_message — используй как есть.

## Команда (TeamCreate)

- **Шаблон:** T2 Integration (LLM-узел + voice + handlers + tests)
- **team_name:** `fn-guest-natural-dialogue`
- **Состав:**
  - `lead` (claude) — координация, дробление, commit-protocol, **код НЕ пишет**
  - `implementer` (general-purpose) — handlers + dialogue node + prompt
  - `tester` (general-purpose) — pytest, мок OpenAI/Whisper
  - `reviewer` (Explore) — read-only: тон промта, edge-cases, инвариант данных

## Commit plan (~5 атомарных)

1. `feat(fsm): IN_DIALOGUE + AWAITING_SURVEY_CONSENT states`
2. `feat(agent): continue_dialogue node with lively tone`
3. `feat(bot-guest): dialogue handler (text + voice) routes to continue_dialogue`
4. `feat(bot-guest): survey consent inline buttons + finalize-no-survey path`
5. `refactor(bot-guest): /start + post-feedback transition wired into dialogue phase`

(Если в процессе появится 6-й — добавь, но не группируй несвязанное.)

## Verification (после команды)

1. `uv run pytest -q` — всё зелёное, минимум 177 + новые тесты
2. `uv run ruff check . && uv run mypy .` — clean
3. **Live E2E в Telegram** на свежем запуске `bot_guest` (нужен restart процесса):
   - `/start` → живое приветствие с эмодзи
   - Отправить voice-отзыв «вчера был у вас, сырные палочки понравились, но соус забыли»
   - Бот отвечает эмпатично, **спрашивает** что-то органичное про опыт (не из админ-пула)
   - 2–3 турна natural dialogue
   - Бот **предлагает** опрос: «есть пара вопросов специально под твой отзыв, скидка в подарок 🎁» + кнопки
   - Жми «Нет, спасибо» → бот вежливо благодарит, в Supabase сохранена сессия с feedback_summary + client_card построена из всего разговора
   - Новая сессия: тот же путь, но жми «Давайте» → переход в текущий interview-flow

## /goal

> Guest-бот **разговаривает** с клиентом 3–5 турнов после отзыва, накапливает контекст в client_card, **тонко предлагает** опрос за скидку с inline-кнопками, корректно обрабатывает Yes/No. Тон живой с эмодзи. Все 177 + новые тесты зелёные, ruff/mypy clean, 5 атомарных коммитов на ветке. Reviewer ✅ approve.

## Out of scope (НЕ делать)

- ❌ Cmd #4 reward system (миграция 0003, /redeem) — отдельная сессия
- ❌ Trim admin-бота — он не трогается
- ❌ Изменение FSM-state `IN_INTERVIEW` — он остаётся как есть для гостей, которые согласились на опрос
- ❌ Pinecone / DB schema changes
- ❌ Глобальные правки тона в admin-боте (тон админа — деловой, не «живой»)

Старт.
