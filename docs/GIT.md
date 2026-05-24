# Git — правила работы

Эти правила должны соблюдать **все агенты в команде** и человек. Они продиктованы безопасностью (не утечь секрет, не сломать prod) и тем, что у нас два бота на одну БД — кривой merge может уронить пользовательский опыт.

---

## 1. Что **никогда** не коммитим

- `.env`, `.env.local`, `.env.staging`, `.env.prod` (и любые `.env.*` кроме `.env.example`)
- Токены ботов, API-ключи (OpenAI, Pinecone, Supabase, Anthropic, любые)
- `.venv/`, `venv/` — виртуальные окружения
- `*.ogg`, `*.mp3`, `*.wav` — voice-файлы пользователей (PII)
- Дампы БД, `*.sqlite`, `dumps/`
- IDE-конфиги (`.vscode/`, `.idea/`)
- `.claude/state/`, `.claude/cache/`, `.claude/plans/` — локальное состояние Claude Code

Если случайно закоммитил секрет — **немедленно**:
1. Отзови ключ (revoke) в OpenAI/Supabase/Pinecone/Telegram BotFather.
2. Сгенерируй новый и обнови `.env` локально + secrets на хостинге.
3. Только после revoke — переписывай историю (`git filter-repo`) или, проще, **создай новый репо** если он публичный.

## 2. Что **обязательно** коммитим

- `.gitignore`, `.env.example`
- `pyproject.toml`, `uv.lock` — детерминированный lock-файл (uv генерирует, не редактируй руками)
- `.python-version`
- `.claude/settings.local.json` — permissions allowlist (это safety net для всей команды, не секрет)
- `db/migrations/*.sql` — миграции схемы
- `docs/` целиком, включая `docs/functions/*.md`

## 3. Брэнчинг

- **Trunk:** `main` — всегда green (тесты проходят, бот запускается).
- **Feature-ветки:** `feat/<group>-<short-slug>`, e.g. `feat/utils-voice-download`, `feat/agent-analyze-feedback`.
- **Fix-ветки:** `fix/<short-slug>`.
- **Chore:** `chore/<short-slug>` (deps bump, config).
- Один PR = одна функция из плана (одна группа в TeamCreate).
- **Никаких** долгоживущих веток (>1 недели) без явного на то основания.

## 4. Коммиты

- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Заголовок ≤72 символов, императив: `feat: add Whisper STT integration`, не `Added...`.
- Тело коммита — **WHY**, не WHAT (diff и так показывает what).
- Если коммит закрывает функцию из плана — упомянуть её имя в теле: `Implements docs/functions/utils_voice_download.md`.
- **НЕ amend** существующие коммиты после push'а. Делаем НОВЫЙ коммит — пусть история длиннее, зато безопасно.
- Не используем `--no-verify` (хуки — это safety, не помеха).

## 5. Pre-commit хуки (минимум)

После `pre-commit install`:
- `ruff check --fix` — линт
- `ruff format` — формат
- `mypy` — типы (предупреждения OK, ошибки блокируют)
- Проверка, что в diff нет паттернов вида `OPENAI_API_KEY=sk-`, `TELEGRAM_BOT_TOKEN=`, длинных hex/base64 строк.

## 6. PR-чеклист (агенты обязаны выполнять)

- [ ] `uv run pytest` — все тесты зелёные локально
- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run mypy .` без новых ошибок
- [ ] Обновлён `docs/functions/<name>.md` (если работа по функции из плана)
- [ ] В diff нет `.env`, ключей, voice-файлов, `__pycache__`
- [ ] `git diff --stat` запущен и просмотрен глазами
- [ ] Описание PR указывает, какой `/goal` из плана закрывает

## 7. Запрещённые операции без явного OK человека

- `git push --force` (любая ветка, в т.ч. feature)
- `git reset --hard <commit>` на удалённой ветке
- `git rebase main` после того, как PR открыт и кто-то его уже смотрит
- Удаление веток на remote (`git push origin --delete`)
- Любые операции с `main` напрямую (только через PR)

Эти команды стоят в `permissions.ask` в `.claude/settings.local.json` — Claude Code запросит подтверждение.

## 8. Миграции БД и git

- Миграция добавляется ОДНОЙ парой коммитов: SQL-файл + код, который от неё зависит. Не должно быть в `main` ситуации «код есть, миграции нет».
- Имя файла: `db/migrations/NNNN_short_name.sql` с возрастающим NNNN.
- Откат — отдельным новым файлом (down-миграции вручную), не редактируем уже применённый SQL.
- Применение на prod — **через PR-описание** («после merge выполнить: `make migrate-prod`») + ручной запуск владельцем.

## 9. Релизные теги (когда дойдём)

- Tag `v0.1.0` — первый рабочий MVP в prod.
- SemVer: `MAJOR.MINOR.PATCH`. До `v1.0.0` любые ломающие изменения разрешены (это MVP).

## 10. Если в репо ещё нет инициализации

Первая команда от любого агента/человека на чистой машине:
```bash
cd telegram-waiter
git init -b main
git add .
git status   # ВНИМАТЕЛЬНО просматриваем staging — не попал ли .env
git commit -m "chore: bootstrap project skeleton"
```
Только после первого commit'а добавляем remote и пушим.
