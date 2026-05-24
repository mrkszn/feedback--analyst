# LangGraph + LangChain — рабочая инструкция

Эта памятка для меня (Claude) и для агентов в команде. Она фиксирует **где мы используем LangGraph/LangChain, где — нет, и почему**. Без неё легко скатиться в одну из двух крайностей: либо завернуть всё в LangChain-обёртки и потерять контроль, либо игнорировать графовую модель и поставить рукописный switch-case в обработчиках.

---

## TL;DR

- **LangGraph** — основной caркас агентского цикла интервью. State-machine с циклами Q&A, ветвлением, persistent state. **Используем.**
- **LangChain (`langchain-core`)** — `ChatPromptTemplate`, structured output, message-объекты. **Используем точечно** в узлах графа.
- **`langchain-openai` (`ChatOpenAI`)** — единый LLM-объект, проброшенный во все узлы LangGraph. **Используем.**
- **`langchain-pinecone` (`PineconeVectorStore`)** — обёртка над Pinecone. **Используем для upsert/similarity_search.** Для прямого upsert вектора без metadata-парсинга можно и pinecone-client напрямую.
- **`langchain` (метапакет, агенты/chains/loaders)** — **в основном НЕ используем.** Нам не нужны `AgentExecutor`, `RetrievalQA`, document loaders. У нас своя оркестрация через LangGraph.
- **Whisper** — НЕ оборачиваем в LangChain (`OpenAIWhisperParser` и подобные перегружены). Используем `openai` SDK напрямую.
- **Embeddings** — для генерации текста-в-вектор можно `OpenAIEmbeddings` из `langchain-openai` (он же используется внутри `PineconeVectorStore`).

---

## Где LangGraph живёт в архитектуре

```
Telegram update
     │
     ▼
aiogram handler (per-session FSM: AWAITING_FEEDBACK | IN_INTERVIEW | FINALIZING)
     │
     ▼  (передаёт текущий transcript + новый user message)
LangGraph runner: invoke(state) → next_state + bot_reply
     │
     ▼
aiogram отправляет bot_reply, обновляет FSM
```

**aiogram FSM** ловит транспортные состояния (когда мы ждём voice, когда — текст-ответ, когда диалог закрыт). **LangGraph** ловит логические состояния агента (анализирую отзыв → выбираю вопросы → задаю → принимаю ответ → ещё вопросы? → собираю карточку). Эти два state-machine **не дублируют друг друга**: aiogram про «что пришло», LangGraph про «что отвечает».

---

## Граф интервью (целевая форма)

Узлы (nodes) — соответствуют функциям из плана (`docs/functions/*.md`):

```
              ┌──────────────────────────────┐
              │ START                        │
              └────────────┬─────────────────┘
                           │
                           ▼
              ┌──────────────────────────────┐
              │ analyze_feedback             │  ← agent_analyze_feedback
              │ (in: raw text; out: summary, │
              │  sentiment, topics, emotion) │
              └────────────┬─────────────────┘
                           │
                           ▼
              ┌──────────────────────────────┐
              │ select_questions             │  ← agent_select_questions
              │ (выбирает 3-5 из admin-пула, │
              │  адаптируя под контекст)     │
              └────────────┬─────────────────┘
                           │
                           ▼
            ┌────────────►┌──────────────────────────────┐
            │             │ ask_next_question            │
            │             │ (формулирует и отдаёт юзеру) │
            │             └────────────┬─────────────────┘
            │                          │
            │   ┌──────── INTERRUPT ───┤   (выходим в aiogram, ждём ответ)
            │   │                      │
            │   ▼                      ▼
            │  AWAIT_USER             ┌──────────────────────────────┐
            │   │                     │ extract_metric               │  ← agent_extract_metric
            │   │ (ответ пришёл)      │ (answer → marked_value)      │
            │   └────────────────────►└────────────┬─────────────────┘
            │                                       │
            │                  ┌────────────────────┤
            │                  │ has_more?          │  ← conditional edge
            │                  ▼                    ▼
            └─────────── ДА                       НЕТ
                                                   │
                                                   ▼
                                      ┌──────────────────────────────┐
                                      │ build_client_card            │  ← agent_build_client_card
                                      │ (свободный summary → embed)  │
                                      └────────────┬─────────────────┘
                                                   │
                                                   ▼
                                                  END
```

**Ключевая особенность** — узел `AWAIT_USER` реализован через **interrupt** LangGraph: граф приостанавливается, persistent state кладётся в checkpoint, aiogram отдаёт пользователю вопрос. Когда юзер отвечает, aiogram resume'ит граф с того же места.

---

## State (структура)

```python
# agent/state.py
from typing import TypedDict, Annotated
from operator import add

class InterviewState(TypedDict):
    session_id: str
    client_id: str
    feedback_raw: str
    feedback_summary: dict  # {summary, sentiment, topics, emotion}
    questions: list[dict]   # выбранные вопросы из admin-пула
    current_q_index: int
    answers: Annotated[list[dict], add]  # [{question_id, answer_text, marked_value}, ...]
    client_card_text: str
    bot_reply: str          # что отправить юзеру следующим сообщением
```

`Annotated[list, add]` — это reducer LangGraph: при возврате узла список `answers` не перезаписывается, а **дополняется** (важно при множественных вызовах extract_metric).

---

## Чек-листы: когда использовать что

### LangGraph — используем когда:
- ✅ нужен **state-машина с циклами** (наш Q&A loop)
- ✅ нужен **interrupt + resume** (ждём пользователя)
- ✅ нужна **persistence checkpoint'ов** (упал процесс → возобновили)
- ✅ нужны **conditional edges** (есть ещё вопросы? — да/нет)
- ✅ нужен **observability** через LangSmith (опционально)

### LangChain (`-core`, `-openai`) — используем точечно когда:
- ✅ нужен `ChatPromptTemplate` с messages-структурой
- ✅ нужен structured output через `.with_structured_output(MySchema)` (Pydantic схема → строгий JSON)
- ✅ единый `ChatOpenAI` объект пробросить во все узлы графа

### LangChain — НЕ используем когда:
- ❌ нужен один OpenAI call без обвязки — пиши через `openai.AsyncOpenAI` напрямую
- ❌ нужен Whisper STT — НЕТ обёртки, используем `openai.AsyncOpenAI.audio.transcriptions.create`
- ❌ нужны loaders, retrievers, document splitters — у нас нет документов, всё в БД
- ❌ нужен `AgentExecutor` или `RetrievalQA` — мы НЕ строим general-purpose агента, у нас узкий граф
- ❌ нужны chains (`LLMChain`, `SequentialChain`) — заменяются узлами графа

---

## Конкретные паттерны

### 1. Создать LLM-клиент (один на процесс)

```python
# agent/llm.py
from langchain_openai import ChatOpenAI
from config import settings

llm = ChatOpenAI(
    model=settings.openai_chat_model,
    api_key=settings.openai_api_key,
    temperature=0.7,           # для interview — живой тон
    timeout=30,
    max_retries=2,
)

# Для structured output — separate handle
llm_structured = llm.with_structured_output  # call site: llm_structured(MyPydanticSchema)
```

### 2. Узел графа со structured output

```python
# agent/nodes/analyze_feedback.py
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from agent.llm import llm

class FeedbackAnalysis(BaseModel):
    summary: str = Field(description="2-3 sentence neutral summary")
    sentiment: Literal["positive", "negative", "mixed", "neutral"]
    topics: list[str] = Field(description="key topics raised by user")
    emotion: str = Field(description="dominant emotion: gratitude, frustration, joy, ...")

prompt = ChatPromptTemplate.from_messages([
    ("system", "Ты анализируешь отзыв клиента ресторана. Отвечай только в указанной схеме."),
    ("user", "Отзыв:\n{feedback}"),
])

chain = prompt | llm.with_structured_output(FeedbackAnalysis)

async def analyze_feedback_node(state: InterviewState) -> dict:
    analysis = await chain.ainvoke({"feedback": state["feedback_raw"]})
    return {"feedback_summary": analysis.model_dump()}
```

### 3. Сборка графа

```python
# agent/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver  # для prod — заменить на Postgres checkpointer

builder = StateGraph(InterviewState)
builder.add_node("analyze_feedback", analyze_feedback_node)
builder.add_node("select_questions", select_questions_node)
builder.add_node("ask_next_question", ask_next_question_node)
builder.add_node("extract_metric", extract_metric_node)
builder.add_node("build_client_card", build_client_card_node)

builder.add_edge(START, "analyze_feedback")
builder.add_edge("analyze_feedback", "select_questions")
builder.add_edge("select_questions", "ask_next_question")
# interrupt после ask_next_question — вернёмся сюда из aiogram
builder.add_edge("ask_next_question", "extract_metric")
builder.add_conditional_edges(
    "extract_metric",
    lambda s: "ask_next_question" if s["current_q_index"] < len(s["questions"]) - 1 else "build_client_card",
    {"ask_next_question": "ask_next_question", "build_client_card": "build_client_card"},
)
builder.add_edge("build_client_card", END)

graph = builder.compile(
    checkpointer=MemorySaver(),                 # dev; prod = PostgresSaver
    interrupt_after=["ask_next_question"],      # пауза тут
)
```

### 4. Вызов из aiogram-handler

```python
# bot_guest/handlers/answer.py
from agent.graph import graph

config = {"configurable": {"thread_id": str(session_id)}}

# Первый запуск (после получения отзыва)
async for event in graph.astream({"feedback_raw": text, ...}, config):
    pass
# Тут граф остановился на interrupt_after=["ask_next_question"]
state = await graph.aget_state(config)
await message.answer(state.values["bot_reply"])

# Возобновление после ответа пользователя
async for event in graph.astream({"answers": [{"answer_text": user_answer}]}, config):
    pass
```

### 5. Vector store через LangChain-Pinecone

```python
# integrations/pinecone_store.py
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from config import settings

embeddings = OpenAIEmbeddings(
    model=settings.openai_embed_model,
    api_key=settings.openai_api_key,
)

vector_store = PineconeVectorStore(
    index_name=settings.pinecone_index,
    namespace=settings.pinecone_namespace,
    embedding=embeddings,
    pinecone_api_key=settings.pinecone_api_key,
)

# Upsert
await vector_store.aadd_texts(
    texts=[card.summary_text],
    metadatas=[{"client_id": ..., "session_id": ..., "sentiment": ...}],
    ids=[str(session_id)],
)

# Search (на Этап 2)
results = await vector_store.asimilarity_search("гости, ценящие острое", k=5, namespace="prod")
```

---

## Checkpointer: dev vs prod

- **Dev (local):** `MemorySaver()` — состояние в RAM, теряется при рестарте. Норм для итераций.
- **Prod:** `PostgresSaver` или собственная имплементация поверх Supabase. Без него — если процесс упал в середине интервью, сессия теряется.

В v1 можно стартовать с `MemorySaver`, миграция на Postgres — отдельная задача в Этапе 1.5.

---

## Observability — LangSmith (опционально)

LangSmith — paid SaaS от LangChain Inc для трассировки графов. Включается одним env var:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=telegram-waiter-local
```

Полезно при дебаге сложных promt-цепочек. **В MVP — не обязателен.** Достаточно structlog с уровнем DEBUG.

---

## Что выкинуть из плана / изменить

Группа D «Agent layer» в плане остаётся как набор **узлов LangGraph**, не как набор независимых функций. Перепишем секцию имплементации в каждом `docs/functions/agent_*.md`:
- сигнатура узла: `async def <name>_node(state: InterviewState) -> dict`
- возвращает **частичный апдейт** состояния
- зависимости: `langchain_core.prompts.ChatPromptTemplate`, `agent.llm.llm`

`agent_build_interview_prompt` теперь не отдельная функция, а **набор `ChatPromptTemplate`** в `agent/prompts.py`, импортируемый узлами. Я обновлю соответствующий `.md` в момент работы над ним.

---

## Anti-patterns (личное напоминание)

- ❌ Не оборачивай `openai.AsyncOpenAI` в LangChain «потому что красивее» — если нет structured output / нет шаблона / нет нужды в integration с другими LC-компонентами, прямой SDK быстрее и понятнее.
- ❌ Не используй `langchain.agents.AgentExecutor` — у нас узкая задача, граф контролируем сами.
- ❌ Не клади бизнес-логику в `RunnableLambda` — это превращается в нечитаемый pipeline. Узел графа = обычная async-функция.
- ❌ Не делай узлы графа с побочкой в БД БЕЗ возврата изменений в state — checkpointer не сможет восстановить контекст после ребута.
- ❌ Не путай `thread_id` (у LangGraph — это идентификатор разговора) с `session_id` (у нас в БД). Хотя их можно совпадать сделать.

---

## Когда обновлять эту памятку

- При смене мажорной версии LangGraph/LangChain (API ломается).
- Когда добавляем checkpointer на Postgres.
- Когда подключаем LangSmith и фиксируем способ маскирования PII в трейсах.
- Когда находим новый anti-pattern на ревью.
