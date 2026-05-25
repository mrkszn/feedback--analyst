# Smoke wet-run — проверка инфраструктуры автономной сессии

Это короткий тест (3–5 минут), не настоящая разработческая сессия. Цель — убедиться, что весь pipeline работает: tmux + permissions + git checkpoint + claude session + tool access.

## Что нужно сделать

1. Прочитать файл `docs/GIT.md` (он есть в проекте).
2. Сделать `git status` и `git log -1 --oneline` — проверить, что ты на ветке `autonomous/<TS>` и можешь читать репозиторий.
3. Прочитать `config.py` (один файл).
4. Создать **тестовый файл** `tmp/smoke_proof.txt` с содержимым:
   ```
   SMOKE OK at <ISO timestamp>
   Branch: <current branch>
   ```
5. Запустить `uv run pytest -q` — проверить, что тулинг работает.
6. **НЕ ДЕЛАЙ КОММИТ** — это просто smoke, не настоящая работа.
7. Распечатать финальный отчёт в stdout:

```
============================================================
SMOKE WET-RUN REPORT
============================================================
Branch:        <current branch>
Pytest:        <passed/failed>
Read access:   docs/GIT.md ✓, config.py ✓
Write access:  tmp/smoke_proof.txt ✓
Tools that work:
  - Bash (uv run pytest): ✓/✗
  - Read: ✓/✗
  - Write: ✓/✗
  - git (status/log): ✓/✗
============================================================
SMOKE OK — pipeline ready for full autonomous session.
============================================================
```

8. **Завершить сессию.** Не жди дальнейших указаний — это smoke, человек подтвердит результат и запустит настоящую сессию отдельно.

## Red lines (даже для smoke)

- ❌ Не пиши никаких файлов вне `telegram-waiter/`
- ❌ Не делай git commit / git push
- ❌ Не вызывай OpenAI / Supabase / Pinecone — это smoke инфры, не сервисов
- ❌ Не спавн новых команд через TeamCreate — этот тест 1-агентовый
