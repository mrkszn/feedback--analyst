#!/usr/bin/env bash
# Bootstrap the FastAPI HTTP API on the VPS.
#
# This host already has Caddy 2 running as part of the n8n Docker stack
# (/opt/n8n/docker-compose.yml). Caddy owns 80/443 with built-in auto-TLS
# via Let's Encrypt. We use that — no certbot, no nginx, no cloudflared.
#
# Final flow: Vercel SPA → https://api-waiter.178-105-54-29.nip.io
#           → Caddy (in n8n stack) terminates TLS, proxies to
#           → host-gateway:8200 → voice-api.service (uvicorn) → FastAPI
#
# Run ONCE as root after initial install.sh:
#   sudo bash /opt/telegram-waiter/deploy/install-voice-api.sh
#
# Idempotent — safe to re-run.

set -euo pipefail

APP_DIR="/opt/telegram-waiter"
UNIT_SRC="${APP_DIR}/deploy/systemd"
LOG_DIR="/var/log/telegram-waiter"
SUDOERS_FILE="/etc/sudoers.d/telegram-waiter"
CADDYFILE="/opt/n8n/Caddyfile"
N8N_COMPOSE_DIR="/opt/n8n"
HOSTNAME="api-waiter.178-105-54-29.nip.io"
HOST_PORT="8200"

if [[ "${EUID}" -ne 0 ]]; then
  echo "must run as root" >&2
  exit 1
fi

echo "[1/7] sanity"
[[ -x "${APP_DIR}/.venv/bin/uvicorn" ]] || { echo "uvicorn not in .venv — run 'uv sync' under waiter first"; exit 1; }
[[ -f "${UNIT_SRC}/voice-api.service" ]] || { echo "voice-api unit missing in ${UNIT_SRC}"; exit 1; }
[[ -f "${CADDYFILE}" ]] || { echo "Caddyfile not found at ${CADDYFILE} — Caddy stack changed?"; exit 1; }
[[ -f "${N8N_COMPOSE_DIR}/docker-compose.yml" ]] || { echo "n8n compose not at ${N8N_COMPOSE_DIR}"; exit 1; }
command -v docker >/dev/null || { echo "docker not on PATH"; exit 1; }
install -d -o waiter -g waiter -m 0755 "${LOG_DIR}"

echo "[2/7] install/refresh systemd units"
# Refresh bot units too (M1 ExecStart) so the bot_*/__main__.py shims become
# obsolete on this host. We keep the shims in the repo for fresh deploys
# that might land before the unit install.
install -m 0644 "${UNIT_SRC}/bot-guest.service"  /etc/systemd/system/bot-guest.service
install -m 0644 "${UNIT_SRC}/bot-admin.service"  /etc/systemd/system/bot-admin.service
install -m 0644 "${UNIT_SRC}/voice-api.service"  /etc/systemd/system/voice-api.service

echo "[3/7] sudoers — allow waiter to restart voice-api too"
cat > "${SUDOERS_FILE}" <<SUDO
# Updated by deploy/install-voice-api.sh.
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl restart bot-guest.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl restart bot-admin.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl restart voice-api.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl start bot-guest.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl start bot-admin.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl start voice-api.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl stop bot-guest.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl stop bot-admin.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl stop voice-api.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl is-active bot-guest.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl is-active bot-admin.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl is-active voice-api.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl is-failed bot-guest.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl is-failed bot-admin.service
waiter ALL=(root) NOPASSWD: /usr/bin/systemctl is-failed voice-api.service
SUDO
chmod 0440 "${SUDOERS_FILE}"
visudo -c -f "${SUDOERS_FILE}" >/dev/null

echo "[4/7] firewall — block external access to ${HOST_PORT} (only Caddy reaches it)"
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw deny "${HOST_PORT}/tcp" >/dev/null || true
  echo "    ufw: deny ${HOST_PORT}/tcp"
else
  echo "    ufw inactive or missing — port ${HOST_PORT} stays publicly reachable on the IP"
  echo "    (FastAPI has its own auth, but install ufw if you want hygiene)"
fi

echo "[5/7] start voice-api"
systemctl daemon-reload
systemctl enable voice-api.service
systemctl restart bot-guest.service bot-admin.service voice-api.service

# Poll up to ~30s for each unit to settle. Uvicorn cold-start under systemd
# can take ~5-10s on a cold VPS (loading Pinecone client, OpenAI SDK, etc.),
# so a flat sleep 3 + is-active was racing the activating state.
for svc in bot-guest bot-admin voice-api; do
  for i in $(seq 1 15); do
    state=$(systemctl is-active "${svc}.service" 2>&1 || true)
    case "${state}" in
      active)   echo "    ${svc}: active (${i}s)"; break ;;
      failed)   echo "    ${svc}: failed — check 'journalctl -u ${svc}' and 'tail /var/log/telegram-waiter/${svc}.log'"; exit 1 ;;
    esac
    sleep 2
    if [[ "${i}" == "15" ]]; then
      echo "    ${svc}: still ${state} after 30s — check 'journalctl -u ${svc}' and 'tail /var/log/telegram-waiter/${svc}.log'"
      exit 1
    fi
  done
done

# Local smoke: uvicorn binds to :8200 only after importing the FastAPI app
# (Pinecone + OpenAI SDK init), which can take ~10-15 s on a cold start.
# is-active reports active as soon as the systemd process exists, NOT when
# uvicorn is serving — so poll the actual port instead.
echo "    waiting for uvicorn to bind :8200…"
for i in $(seq 1 30); do
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:8200/docs 2>/dev/null || echo "000")
  if [[ "${code}" == "200" ]]; then
    echo "    voice-api: GET /docs returns 200 locally (${i}s)"
    break
  fi
  if [[ "${i}" == "30" ]]; then
    echo "    voice-api: /docs still unreachable after 60s — check 'tail /var/log/telegram-waiter/voice-api.log'"
    exit 1
  fi
  sleep 2
done

echo "[6/7] register the Caddy vhost (idempotent)"
if grep -qF "${HOSTNAME}" "${CADDYFILE}"; then
  echo "    ${HOSTNAME} block already in Caddyfile — skipping append"
else
  cp "${CADDYFILE}" "${CADDYFILE}.bak.$(date -u +%Y%m%d%H%M%S)"
  # Double-quoted heredoc so ${HOSTNAME} expands. The CSP single-quotes around
  # 'self' are inside a double-quoted string in Caddy syntax — no shell parse.
  cat >> "${CADDYFILE}" <<CADDY

${HOSTNAME} {
    reverse_proxy host.docker.internal:8200

    encode gzip

    header {
        -X-Frame-Options
        Content-Security-Policy "frame-ancestors 'self' https://web.telegram.org https://t.me"
    }
}
CADDY
  echo "    appended ${HOSTNAME} block to ${CADDYFILE}"
fi

echo "[7/7] reload Caddy (no container restart)"
cd "${N8N_COMPOSE_DIR}"
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
sleep 2

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  voice-api PUBLIC URL (point Vercel VITE_API_BASE_URL at this):"
echo ""
echo "      https://${HOSTNAME}"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Smoke check (may take ~30s for Let's Encrypt cert on first hit):"
echo "  curl https://${HOSTNAME}/docs"
echo ""
echo "Vercel project env (telegram-waiter-admin-miniapp):"
echo "  VITE_API_BASE_URL=https://${HOSTNAME}"
echo "  VITE_AUTH_ENDPOINT=/admin/auth"
echo ""
echo "After Vercel deploys, update /etc/telegram-waiter/.env on this VPS:"
echo "  ALLOWED_MINI_APP_ORIGINS=https://<your-vercel-domain>.vercel.app,https://${HOSTNAME}"
echo "  ADMIN_MINI_APP_URL=https://<your-vercel-domain>.vercel.app"
echo "Then: sudo systemctl restart bot-admin voice-api"
