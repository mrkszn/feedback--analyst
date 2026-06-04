# Deployment to your own server

План развёртывания: backend + 2 бота → собственный VPS (systemd + nginx +
Let's Encrypt); Mini App → **Vercel** (static SPA из Vite-сборки).

> **Stack change (vs предыдущей итерации):** Mini App был запланирован как
> Next.js production на VPS через `voice-miniapp.service`. Переключились на
> Vite + React → static deploy на Vercel. Причина: Telegram Mini App это
> pure-client SPA в WebView (SSR невозможен в принципе — initData/JWT
> клиентские), Vite даёт ~200 KB bundle vs Next ~500 KB+, что критично для
> cold-load UX в Telegram. Vercel хостит static build бесплатно с CDN и
> auto-deploy из git push, что заменяет старую цепочку `pnpm build +
> systemd voice-miniapp + nginx proxy_pass :3000`.

## Что хостим у себя vs. что остаётся в облаке

| Компонент | Где живёт |
|---|---|
| `bot_admin` (polling) | **свой VPS**, systemd |
| `bot_guest` (polling) | **свой VPS**, systemd |
| FastAPI `api.*` (HTTP API, uvicorn) | **свой VPS**, systemd |
| Mini App (Vite static SPA) | **Vercel** (free tier, auto-deploy из git) |
| nginx reverse proxy + HTTPS (для api.*) | **свой VPS** |
| Supabase (Postgres + storage) | облако (managed) |
| Pinecone (vector index) | облако (managed) |
| OpenAI (chat + Whisper + embeddings) | облако (managed) |
| Telegram Bot API | Telegram |

---

## Минимальные требования к VPS

| Ресурс | Минимум | Рекомендую |
|---|---|---|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB SSD | 40 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| Сеть | 1 IPv4 публичный | + IPv6 опц. |

**Варианты провайдеров** (примерные цены EUR/мес для рекомендованной конфы):

- **Hetzner Cloud CPX21** — €5.83 (Germany / Finland / US). Лучший price/perf для рунета и EU
- **DigitalOcean Basic 2GB** — $14 (San Francisco / Frankfurt)
- **Linode Shared CPU 2GB** — $14
- **Timeweb Cloud** — от 250₽/мес (Россия, если нужна локальная юрисдикция)
- **VK Cloud / Yandex Cloud** — гибче, дороже, для прод-нагрузок

Memory headroom: Python-процессы по 150-250 MB; nginx 30 MB; ffmpeg при voice — еще ~100 MB пиково. Mini App build больше не живёт на VPS (Vercel-managed) — раньше Next.js забирал 600-800 MB. На 2 GB сейчас комфортно; 4 GB остаётся рекомендацией под рост.

---

## Что нужно подготовить ДО деплоя

1. **VPS** — арендован, IP получен, корневой SSH-доступ настроен
2. **Домен** — купленный и DNS управляется (Cloudflare / Namecheap / reg.ru)
3. **DNS A-record для backend** (укажи на VPS IP):
   - `api.твой-домен` → VPS IP
   - Mini App хостится на Vercel; либо используем дефолтный
     `telegram-waiter-admin-miniapp.vercel.app`, либо привязываем
     `miniapp.твой-домен` (CNAME → `cname.vercel-dns.com.`). Custom domain
     настраивается в Vercel dashboard, certificate auto-issued.
4. **Email для Let's Encrypt** (нужен один раз для `api.твой-домен`)
5. **Production credentials** — сейчас в `.env` у тебя dev-ключи; перед прод-деплоем:
   - Сгенерируй новый `MINI_APP_SESSION_SECRET` (`openssl rand -hex 32`)
   - Создай отдельный admin bot + guest bot у `@BotFather` с прод-username'ами
   - Возможно отдельный Supabase project (опц. — можно стартовать с того же)
   - Возможно отдельный Pinecone namespace (`PINECONE_NAMESPACE=prod`)
6. **Vercel account** — бесплатный tier хватит. Connect GitHub → импорт репо
   `telegram-waiter-admin-miniapp`. Build command: `pnpm build`, Output dir:
   `dist`, Framework preset: **Vite**.
7. **GitHub Personal Access Token** (read-only для private репо `telegram-waiter` на VPS)

---

## План деплоя — 8 этапов

### Этап 1 — Хардинг сервера (15 мин)

- Создать non-root пользователя `deploy` + sudo
- Отключить root SSH login + парольный auth (только ключи)
- Включить `ufw` файрвол: разрешить только 22, 80, 443
- Поставить `fail2ban` для защиты SSH
- Обновить систему: `apt update && apt upgrade -y`

### Этап 2 — Установить системные зависимости (20 мин)

- Python 3.12 (через deadsnakes PPA или `apt install python3.12`)
- `uv` — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `nginx`
- `certbot` + `python3-certbot-nginx`
- `git`, `tmux` (для отладки)
- `ffmpeg` — для voice-обработки в guest-боте
- `jq` — для скриптов

> Node.js / pnpm на VPS больше не нужны — Mini App собирается и хостится на
> Vercel.

### Этап 3 — Клонировать репозитории (5 мин)

В `/srv/` или `/opt/`:

```
sudo mkdir -p /srv/voice && sudo chown deploy:deploy /srv/voice
cd /srv/voice
git clone https://<TOKEN>@github.com/mrkszn/feedback--analyst.git telegram-waiter
```

Или через SSH deploy keys (рекомендую — токены протухают). Mini App клонировать
на VPS НЕ нужно — он живёт на Vercel.

### Этап 4 — Backend setup (30 мин)

```
cd /srv/voice/telegram-waiter
uv sync                         # установит все Python deps
cp .env.example .env            # заполнить прод-значениями
nano .env                       # подставить prod TELEGRAM tokens, MINI_APP_SESSION_SECRET, ADMIN_MINI_APP_URL=https://miniapp.твой-домен, ALLOWED_MINI_APP_ORIGINS=https://miniapp.твой-домен
uv run python scripts/smoke.py  # smoke check creds (всё ли подтянуто)
```

### Этап 5 — Mini App setup на Vercel (10 мин, web UI)

Все шаги — в Vercel dashboard, никакого SSH:

1. **Connect Git** — Vercel → New Project → Import репозиторий
   `telegram-waiter-admin-miniapp` (после Phase 4C он будет создан).
2. **Framework preset** — Vite (Vercel определит автоматически по
   `vite.config.ts`).
3. **Build command** — `pnpm build` (или Vercel default).
4. **Output directory** — `dist`.
5. **Environment variables** (Project Settings → Environment Variables):
   - `VITE_API_BASE_URL=https://api.твой-домен`
   - `VITE_AUTH_ENDPOINT=/admin/auth`
   - `VITE_APP_ENV=production`
6. **Domain** — либо оставь дефолт `*.vercel.app`, либо привяжи
   `miniapp.твой-домен` (Vercel выдаст инструкции по CNAME / A-records).
7. **Deploy** — Vercel автоматически собирает на каждый `git push` в main +
   делает preview-deploy на каждый PR.

В **Telegram BotFather** → admin bot → Configure Mini App → URL =
`https://telegram-waiter-admin-miniapp.vercel.app` (или твой custom domain).

### Этап 6 — systemd units на VPS (10 мин)

Создать 3 файла в `/etc/systemd/system/`:

- `voice-api.service` — uvicorn на 127.0.0.1:8000
- `voice-bot-admin.service` — `python -m bot_admin`
- `voice-bot-guest.service` — `python -m bot_guest`

Все 3 — с `Restart=always`, `RestartSec=10`, `User=deploy`, переменные через `EnvironmentFile=`. Готовые шаблоны можно нагенерить — см. ниже.

```
sudo systemctl daemon-reload
sudo systemctl enable --now voice-api voice-bot-admin voice-bot-guest
sudo systemctl status voice-*
```

### Этап 7 — nginx + Let's Encrypt SSL для backend (15 мин)

Один server-блок:

- `api.твой-домен` → `proxy_pass http://127.0.0.1:8000;`

Дополнительно: HSTS, gzip, `client_max_body_size 2M`, security headers.
`X-Frame-Options DENY` оставляем — backend frame'ить никто не должен. Mini App
живёт на Vercel со своими headers; Telegram WebApp требует embedding только
для frontend домена, а на Vercel это решается через `vercel.json` headers
(`frame-ancestors https://web.telegram.org`).

После nginx-конфига:

```
sudo certbot --nginx -d api.твой-домен \
    --email твой@email --agree-tos --no-eff-email
```

Certbot пропишет `listen 443 ssl`, auto-renew через `systemctl timer` уже включён.

### Этап 8 — Verify end-to-end (15 мин)

1. `curl https://api.твой-домен/docs` → 200, видишь Swagger UI
2. `curl https://telegram-waiter-admin-miniapp.vercel.app` (или твой custom domain) → 200, видишь Vite SPA index
3. В Telegram: `/start` admin-боту → `/miniapp` → tap «Открыть Mini App»
   - Mini App открывается **внутри** Telegram
   - Auth flow: initData → JWT → /dashboard загружается
   - Походи по 5 страницам (Главная, Метрики, Топики, Клиенты, Чат)
4. `/ask «топ-3 жалобы за неделю»` в Mini App chat — LLM отвечает
5. В guest-боте: `/start` → дай отзыв → пройди interview → проверь что в admin Mini App данные обновились через минуту

---

## Полный bash-скрипт деплоя

Я могу подготовить `scripts/deploy/`:

- `01_provision.sh` — хардинг + системные deps (запускается под root на свежем VPS)
- `02_clone.sh` — git clone backend
- `03_setup_backend.sh` — uv sync + smoke check
- `04_systemd.sh` — генерит systemd units из шаблонов (3 unit'а — api + 2 бота)
- `05_nginx.sh` — генерит nginx confs + запускает certbot (только `api.твой-домен`)
- `06_verify.sh` — health-check endpoint pings

Mini App деплой — через Vercel UI, скрипты не нужны.

Это **отдельная мини-сессия** перед самим деплоем. Скажи когда готов — соберу.

---

## Update workflow после деплоя

После `git push` в `telegram-waiter` (backend) → main:

```
# Через GitHub Actions (см. .github/workflows/deploy.yml) — авто, без SSH.
# Или вручную:
ssh deploy@VPS
cd /srv/voice/telegram-waiter && git pull && uv sync && \
    sudo systemctl restart voice-api voice-bot-admin voice-bot-guest
```

После `git push` в `telegram-waiter-admin-miniapp` (frontend) → main:

```
# Ничего делать не надо — Vercel сам собирает и публикует.
# Preview-deploys на каждый PR — тоже автоматически.
```

---

## Backup + disaster recovery

| Что | Стратегия |
|---|---|
| Supabase Postgres | автоматические PITR backups у Supabase (Pro plan); free tier — daily snapshots 7 дней. Бесплатный экспорт через CLI: `supabase db dump > backup.sql` |
| Pinecone vectors | нет автоматического backup; периодически экспорт через API (если критично — расскажи, накидаю export-скрипт) |
| VPS state | snapshot 1×/неделю через провайдер (Hetzner — €0.012/GB/мес) |
| Code | репо в GitHub (если что — clone заново) |
| Env / secrets | хранить в secure password manager (1Password / Bitwarden vault) |

Что НЕ нуждается в backup'е — само приложение stateless, любая нода легко поднимается из git clone + .env.

---

## Мониторинг и алертинг (опц.)

- **UptimeRobot** (free) — пинг каждые 5 мин на `https://api.твой-домен/docs` и Vercel URL. Шлёт email/Telegram при downtime. Vercel сам показывает uptime в dashboard.
- **Sentry** (free 5k events/мес) — error tracking для FastAPI и Vite SPA (опц.)
- **journalctl** — встроенные логи systemd, ротация автоматическая
- **htop / atop** — interactive process monitor для ad-hoc отладки
- **Telegram self-bot** — кастомный hook от bot_admin, шлёт alert если /admin/overview возвращает 5xx

---

## Стоимость (примерно, в месяц EUR)

| | EU (Hetzner) | RU (Timeweb) |
|---|---|---|
| VPS 2vCPU/4GB | 5.83 | 4.50 |
| Domain `.com`/`.app` | 1.0 (avg, годовая платёж/12) | 1.0 |
| Snapshot weekly 40GB | 0.48 | 0.30 |
| Supabase free tier | 0 | 0 |
| Pinecone free tier | 0 | 0 |
| OpenAI (~10-50 запросов/день) | ~3-8 | ~3-8 |
| **Итого** | **~10-15** | **~9-14** |

При росте нагрузки самый дорогой компонент — OpenAI (LLM в `/ask`). На 100+ запросов/день стоимость может подскочить до $30-50/мес — это уже момент думать про caching на стороне backend или dropping cheaper model fallback.

---

## Open questions для тебя

1. **VPS-провайдер** — Hetzner / DigitalOcean / Timeweb / уже свой?
2. **Домен** — есть купленный? Какой стек хочешь использовать?
3. **Russian jurisdiction обязательна** (Timeweb/Yandex)? или EU допустима (Hetzner — самый дёшевый)?
4. **Когда стартуем** — после ручного тестирования через cloudflared в Telegram (текущая фаза)? или сразу планируем production setup?
5. **Single VPS или разнесение?** Backend + Mini App на одной коробке нормально для MVP; при большой нагрузке имеет смысл разнести.
6. **Auto-deploy через GitHub Actions** — нужно? Если да — настроим SSH deploy key + workflow.

После твоих ответов на пункты 1-3 — соберу `scripts/deploy/` под конкретного провайдера/конфу.
