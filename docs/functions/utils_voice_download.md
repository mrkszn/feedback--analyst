# utils.voice_download.download_voice_to_tmp

## Назначение

Когда гость в Telegram присылает голосовое сообщение, агенту нужен локальный файл для передачи в Whisper STT. Telegram отдаёт лишь `file_id` — фактическое скачивание делает эта функция: запрашивает у Telegram метаданные файла, кладёт содержимое в локальный временный каталог под уникальным именем и возвращает `Path`. Это **самая нижняя** утилита voice-пайплайна; над ней живут [[integrations_whisper_transcribe]] и [[guest_handle_feedback_voice]].

Функция не делает транскрипцию, не валидирует длительность и не очищает старые tmp-файлы — у неё одна ответственность: скачать байты в файл.

## Сигнатура

```python
from pathlib import Path
from aiogram import Bot

async def download_voice_to_tmp(
    file_id: str,
    bot: Bot,
    tmp_dir: Path | str | None = None,
) -> Path: ...
```

- `file_id` — идентификатор Telegram-файла (из `message.voice.file_id`).
- `bot` — экземпляр `aiogram.Bot` (нужен для `get_file` и `download_file`).
- `tmp_dir` — каталог для записи. Если `None`, берётся из `settings.voice_tmp_dir`.
- **Возвращает:** абсолютный `Path` к скачанному файлу.
- **Исключения:**
  - `aiogram.exceptions.TelegramAPIError` — пробрасываем как есть (невалидный `file_id`, файл устарел, сетевая ошибка). Не глотаем.
  - `OSError` — если не удалось создать каталог или записать файл.

## Зависимости

- `aiogram.Bot.get_file(file_id)` → объект `File` с полем `file_path`.
- `aiogram.Bot.download_file(file_path, destination=...)` — пишет байты на диск.
- `config.settings.voice_tmp_dir` — дефолтный каталог.
- `pathlib.Path`, `uuid.uuid4` — формирование уникального имени.

## Шаги реализации

1. Резолвить эффективный `tmp_dir`: если параметр `None` — `Path(settings.voice_tmp_dir)`, иначе `Path(tmp_dir)`. Привести к абсолютному пути через `.resolve()`.
2. `tmp_dir.mkdir(parents=True, exist_ok=True)` — каталог может ещё не существовать (первый запуск, в .gitignore).
3. Получить метаданные: `file = await bot.get_file(file_id)`. Из них взять `file.file_path` (путь на серверах Telegram) и расширение из этого пути (обычно `.oga`).
4. Сформировать локальный путь: `tmp_dir / f"{uuid.uuid4().hex}{ext}"`. UUID гарантирует отсутствие коллизий при конкурентных загрузках.
5. `await bot.download_file(file.file_path, destination=str(local_path))`.
6. Вернуть `local_path`.

## Edge cases

- **tmp_dir не существует** → создаём через `mkdir(parents=True, exist_ok=True)`.
- **Расширение отсутствует в `file_path`** → используем `.oga` как дефолт (Telegram-стандарт для voice).
- **`file_id` невалиден / устарел** → `TelegramAPIError` пробрасывается вызывающему. Хэндлер уровнем выше отвечает гостю «не удалось скачать голос».
- **Диск переполнен** → `OSError` пробрасывается. Логируем в caller'е.
- **Воркер прибит до завершения скачивания** → останется частично записанный файл. Очистка — задача отдельной утилиты (вне scope этой функции).
- **Несколько параллельных вызовов** → UUID-имя устраняет коллизии.

Что **не** делаем (намеренно):
- Не лимитируем размер/длительность файла — это валидация уровня хэндлера.
- Не конвертируем форматы (ogg → mp3) — Whisper SDK принимает `.oga`/`.ogg`.
- Не удаляем старые файлы — отдельная фоновая задача / TTL в filesystem.

## Тесты

`tests/test_utils_voice_download.py`:

- **Unit:**
  - `test_download_creates_file_with_uuid_name` — мокаем `Bot.get_file` и `Bot.download_file`, проверяем что итоговый путь существует и имя — UUID-hex + расширение.
  - `test_default_tmp_dir_from_settings` — без `tmp_dir` берётся `settings.voice_tmp_dir`.
  - `test_explicit_tmp_dir_is_created` — передаём несуществующий путь, проверяем что mkdir отработал.
  - `test_oga_default_extension_when_path_has_none` — мокаем `file_path` без расширения, ожидаем `.oga`.
  - `test_telegram_api_error_propagates` — `bot.get_file` бросает `TelegramAPIError`, проверяем что исключение не глотается.
- **Интеграция:** **отложена** — требует живого Telegram update с voice. Покрывается ручным тестом E2E на стадии группы E (`guest_handle_feedback_voice`).
- **Ручной:** не нужен на этом этапе.

## /goal

> Функция `download_voice_to_tmp` имплементирована в `utils/voice_download.py` по сигнатуре; все pytest-тесты из `tests/test_utils_voice_download.py` зелёные; `uv run ruff check .` и `uv run mypy .` без новых ошибок; reviewer ✅ approve; **сделан коммит** `feat(utils): implement download_voice_to_tmp` по формату из `docs/GIT.md §4-5` (этот `.md`, код функции и тесты — в одном коммите). Push не обязателен.

## Команда (TeamCreate)

- **Шаблон:** **T1 — Standard Impl** (нет внешнего API → не T2)
- **team_name:** `fn-utils-voice-download`
- **Состав (имена обязательны для SendMessage):**
  - `team-lead` — `subagent_type: claude`. Промпт «team-lead» из плана с подставленными `{FN}=download_voice_to_tmp` и `{MD_PATH}=telegram-waiter/docs/functions/utils_voice_download.md`.
  - `implementer` — `subagent_type: general-purpose`. Промпт «implementer» с теми же подстановками.
  - `tester` — `subagent_type: general-purpose`. Промпт «tester».
  - `reviewer` — `subagent_type: Explore`. Промпт «reviewer».

Все 4 промпта-шаблона — в `~/.claude/plans/imperative-stirring-dove.md`, секция «Промпты ролей». Тимлид сам подставит `{FN}`/`{MD_PATH}` при чтении задачи.

## Permissions

Наследуются из `telegram-waiter/.claude/settings.local.json`. Доп. требований нет — функция чисто файловая, сетевых вызовов вне Telegram API нет, секреты не трогаются.

## Next

→ [integrations_openai_chat.md](integrations_openai_chat.md)
