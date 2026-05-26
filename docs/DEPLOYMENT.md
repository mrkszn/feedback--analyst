# Deployment to your own server

План развёртывания всего стека (backend + 2 бота + Mini App) на собственный
VPS. Без managed-сервисов вроде Vercel/Railway — мы сами поднимаем процессы
через systemd за nginx с Let's Encrypt SSL.

## Что хостим у себя vs. что остаётся в облаке

| Компонент | Где живёт |
|---|---|
| `bot_admin` (polling) | **свой VPS**, systemd |
| `bot_guest` (polling) | **свой VPS**, systemd |
| FastAPI `api.*` (HTTP API, uvicorn) | **свой VPS**, systemd |
| Mini App (Next.js production) | **свой VPS**, systemd |
| nginx reverse proxy + HTTPS | **свой VPS** |
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

Memory headroom важен: Next.js dev/build кушает 600-800 MB; Python-процессы по 150-250 MB; nginx 30 MB. На 2GB можно жить, но 4GB даст запас под рост.

---

## Что нужно подготовить ДО деплоя

1. **VPS** — арендован, IP получен, корневой SSH-доступ настроен
2. **Домен** — купленный и DNS управляется (Cloudflare / Namecheap / reg.ru)
3. **DNS A-records** (укажи на VPS IP):
   - `api.твой-домен` → IP
   - `miniapp.твой-домен` → IP
4. **Email для Let's Encrypt** (нужен один раз для регистрации сертификата)
5. **Production credentials** — сейчас в `.env` у тебя dev-ключи; перед прод-деплоем:
   - Сгенерируй новый `MINI_APP_SESSION_SECRET` (`openssl rand -hex 32`)
   - Создай отдельный admin bot + guest bot у `@BotFather` с прод-username'ами
   - Возможно отдельный Supabase project (опц. — можно стартовать с того же)
   - Возможно отдельный Pinecone namespace (`PINECONE_NAMESPACE=prod`)
6. **GitHub Personal Access Token** (read-only для private репозиториев — `telegram-waiter` + `telegram-waiter-admin-miniapp`)

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
- Node.js 22 LTS — через NodeSource APT repo
- `pnpm` — `npm install -g pnpm`
- `nginx`
- `certbot` + `python3-certbot-nginx`
- `git`, `tmux` (для отладки)
- `ffmpeg` — для voice-обработки в guest-боте
- `jq` — для скриптов

### Этап 3 — Клонировать репозитории (5 мин)

В `/srv/` или `/opt/`:

```
sudo mkdir -p /srv/voice && sudo chown deploy:deploy /srv/voice
cd /srv/voice
git clone https://<TOKEN>@github.com/mrkszn/feedback--analyst.git telegram-waiter
git clone https://<TOKEN>@github.com/mrkszn/telegram-waiter-admin-miniapp.git
```

Или через SSH deploy keys (рекомендую — токены протухают).

### Этап 4 — Backend setup (30 мин)

```
cd /srv/voice/telegram-waiter
uv sync                         # установит все Python deps
cp .env.example .env            # заполнить прод-значениями
nano .env                       # подставить prod TELEGRAM tokens, MINI_APP_SESSION_SECRET, ADMIN_MINI_APP_URL=https://miniapp.твой-домен, ALLOWED_MINI_APP_ORIGINS=https://miniapp.твой-домен
uv run python scripts/smoke.py  # smoke check creds (всё ли подтянуто)
```

### Этап 5 — Mini App setup (20 мин)

```
cd /srv/voice/telegram-waiter-admin-miniapp
pnpm install
cat > .env.production <<EOF
NEXT_PUBLIC_API_BASE_URL=https://api.твой-домен
NEXT_PUBLIC_AUTH_ENDPOINT=/admin/auth
NEXT_PUBLIC_APP_ENV=production
EOF
pnpm build                      # ~2-3 мин, создаст .next/
```

### Этап 6 — systemd units (15 мин)

Создать 4 файла в `/etc/systemd/system/`:

- `voice-api.service` — uvicorn на 127.0.0.1:8000
- `voice-bot-admin.service` — `python -m bot_admin`
- `voice-bot-guest.service` — `python -m bot_guest`
- `voice-miniapp.service` — `pnpm start` (Next.js production) на 127.0.0.1:3000

Все 4 — с `Restart=always`, `RestartSec=10`, `User=deploy`, переменные через `EnvironmentFile=`. Готовые шаблоны можно нагенерить — см. ниже.

```
sudo systemctl daemon-reload
sudo systemctl enable --now voice-api voice-bot-admin voice-bot-guest voice-miniapp
sudo systemctl status voice-*
```

### Этап 7 — nginx + Let's Encrypt SSL (20 мин)

Два server-блока:

- `api.твой-домен` → `proxy_pass http://127.0.0.1:8000;`
- `miniapp.твой-домен` → `proxy_pass http://127.0.0.1:3000;`

Дополнительно: HSTS, gzip, `client_max_body_size 2M`, security headers
(`X-Frame-Options DENY` — но не для miniapp! Telegram WebApp требует embedding, для miniapp используем `frame-ancestors https://web.telegram.org`).

После nginx-конфига:

```
sudo certbot --nginx -d api.твой-домен -d miniapp.твой-домен \
    --email твой@email --agree-tos --no-eff-email
```

Certbot пропишет `listen 443 ssl`, auto-renew через `systemctl timer` уже включён.

### Этап 8 — Verify end-to-end (15 мин)

1. `curl https://api.твой-домен/docs` → 200, видишь Swagger UI
2. `curl https://miniapp.твой-домен` → 200, видишь Next.js root (или HTML с redirect logic)
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
- `02_clone.sh` — git clone обоих репо
- `03_setup_backend.sh` — uv sync + smoke check
- `04_setup_miniapp.sh` — pnpm install + build
- `05_systemd.sh` — генерит systemd units из шаблонов
- `06_nginx.sh` — генерит nginx confs + запускает certbot
- `07_verify.sh` — health-check endpoint pings

Это **отдельная мини-сессия** перед самим деплоем. Скажи когда готов — соберу.

---

## Update workflow после деплоя

После любого `git push` в main:

```
ssh deploy@VPS
cd /srv/voice/telegram-waiter && git pull && uv sync && \
    sudo systemctl restart voice-api voice-bot-admin voice-bot-guest

cd /srv/voice/telegram-waiter-admin-miniapp && git pull && pnpm install --production && \
    pnpm build && sudo systemctl restart voice-miniapp
```

Можно автоматизировать через GitHub Actions + SSH deploy key (отдельная фаза если хочешь zero-touch deploys).

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

- **UptimeRobot** (free) — пинг каждые 5 мин на `https://api.твой-домен/docs` и `https://miniapp.твой-домен`. Шлёт email/Telegram при downtime
- **Sentry** (free 5k events/мес) — error tracking для FastAPI и Next.js (опц.)
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
