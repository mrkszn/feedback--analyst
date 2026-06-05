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

echo "[4/7] firewall — allow Caddy (any docker bridge) to reach :${HOST_PORT}"
# ufw default-deny-incoming on this VPS means any traffic from the docker
# bridge gateways (172.16-172.31) to host:${HOST_PORT} is dropped unless
# explicitly allowed. Caddy lives in n8n's compose stack and reaches us
# via its own bridge gateway (e.g. 172.20.0.1) → we need an allow rule
# for the whole 172.16.0.0/12 range (covers all docker bridges).
#
# We also remove any prior over-broad 'deny ${HOST_PORT}/tcp' from older
# install runs of this script.
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
  if ufw status numbered 2>/dev/null | grep -q "DENY.*${HOST_PORT}/tcp"; then
    yes | ufw delete deny "${HOST_PORT}/tcp" >/dev/null 2>&1 || true
    echo "    removed prior over-broad 'deny ${HOST_PORT}/tcp'"
  fi
  if ufw status 2>/dev/null | grep -qE "${HOST_PORT}/tcp.*172\.16\.0\.0/12"; then
    echo "    ufw: allow from 172.16.0.0/12 to :${HOST_PORT}/tcp — already present"
  else
    ufw allow in from 172.16.0.0/12 to any port "${HOST_PORT}" proto tcp \
        comment "voice-api from docker bridges" >/dev/null
    echo "    ufw: allow from 172.16.0.0/12 to :${HOST_PORT}/tcp (covers all docker bridges)"
  fi
else
  echo "    ufw inactive — nothing to do (host firewall not enforcing)"
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
# We do NOT use 'host.docker.internal' here because Docker's host-gateway
# semantic resolves to docker0's gateway (172.17.0.1) regardless of which
# bridge Caddy actually runs on. If docker0 is down (no containers
# attached) — and on this multi-stack VPS it is — packets to that IP just
# time out. Instead, ask the Caddy container what its OWN default gateway
# is and pin reverse_proxy to that IP. Robust across container/bridge
# recreations.
CADDY_GW=$(docker exec n8n-caddy-1 sh -c 'ip route show default 2>/dev/null' | awk '/default/ {print $3}' || true)
if [[ -z "${CADDY_GW}" ]]; then
  echo "    could not read Caddy default gateway — abort"
  exit 1
fi
echo "    Caddy default gateway: ${CADDY_GW}"

UPSTREAM="${CADDY_GW}:${HOST_PORT}"
if grep -qF "${HOSTNAME}" "${CADDYFILE}"; then
  # Block already there. Make sure upstream IP still points at the live
  # Caddy gateway (could have shifted after a stack rebuild).
  if grep -A2 "${HOSTNAME}" "${CADDYFILE}" | grep -q "reverse_proxy ${UPSTREAM}"; then
    echo "    ${HOSTNAME} block present + upstream up-to-date — skipping"
  else
    cp "${CADDYFILE}" "${CADDYFILE}.bak.$(date -u +%Y%m%d%H%M%S)"
    sed -i "/^${HOSTNAME//./\\.} {/,/^}/ s|reverse_proxy [^[:space:]]*|reverse_proxy ${UPSTREAM}|" "${CADDYFILE}"
    echo "    refreshed reverse_proxy → ${UPSTREAM} in existing ${HOSTNAME} block"
  fi
else
  cp "${CADDYFILE}" "${CADDYFILE}.bak.$(date -u +%Y%m%d%H%M%S)"
  cat >> "${CADDYFILE}" <<CADDY

${HOSTNAME} {
    reverse_proxy ${UPSTREAM}

    encode gzip

    header {
        -X-Frame-Options
        Content-Security-Policy "frame-ancestors 'self' https://web.telegram.org https://t.me"
    }
}
CADDY
  echo "    appended ${HOSTNAME} → ${UPSTREAM} to ${CADDYFILE}"
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
