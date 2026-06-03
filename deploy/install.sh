#!/usr/bin/env bash
# One-time VPS bootstrap. Run as root on a fresh Ubuntu 22.04/24.04 host:
#   curl -fsSL https://raw.githubusercontent.com/<your>/telegram-waiter/main/deploy/install.sh | sudo bash
# Or copy this file to the host and `sudo bash install.sh`.
#
# Creates: `waiter` system user, /opt/telegram-waiter, /etc/telegram-waiter/.env stub,
# /var/log/telegram-waiter, installs Python 3.12 + uv, registers systemd units (disabled).
#
# After running: fill /etc/telegram-waiter/.env, then push to main — CI/CD does the rest.

set -euo pipefail

APP_USER="waiter"
APP_DIR="/opt/telegram-waiter"
ENV_DIR="/etc/telegram-waiter"
LOG_DIR="/var/log/telegram-waiter"
UNIT_SRC="${APP_DIR}/deploy/systemd"

if [[ "${EUID}" -ne 0 ]]; then
  echo "must run as root" >&2
  exit 1
fi

echo "[1/6] apt deps"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl git rsync python3.12 python3.12-venv

echo "[2/6] uv (system-wide /usr/local/bin/uv)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
fi
uv --version

echo "[3/6] app user + dirs"
id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash "${APP_USER}"
install -d -o "${APP_USER}" -g "${APP_USER}" -m 0755 "${APP_DIR}"
install -d -o "${APP_USER}" -g "${APP_USER}" -m 0755 "${LOG_DIR}"
install -d -o root          -g "${APP_USER}" -m 0750 "${ENV_DIR}"

echo "[4/6] env stub (only if missing)"
if [[ ! -f "${ENV_DIR}/.env" ]]; then
  cat > "${ENV_DIR}/.env" <<'ENV'
# Fill these with prod values (or current dev creds — see docs/ENVIRONMENTS.md)
ENV=prod
LOG_LEVEL=INFO

TELEGRAM_GUEST_BOT_TOKEN=
TELEGRAM_ADMIN_BOT_TOKEN=
ADMIN_BOOTSTRAP_TOKEN=

OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-5.5
OPENAI_WHISPER_MODEL=whisper-1
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_USAGE_TAG=prod

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

PINECONE_API_KEY=
PINECONE_INDEX=client-cards
PINECONE_NAMESPACE=prod

VOICE_TMP_DIR=/opt/telegram-waiter/tmp/voice
RESTAURANT_CONTEXT=
MINI_APP_SESSION_SECRET=
ALLOWED_MINI_APP_ORIGINS=
ENV
  chmod 0640 "${ENV_DIR}/.env"
  chown root:"${APP_USER}" "${ENV_DIR}/.env"
  echo "  wrote ${ENV_DIR}/.env stub — fill it before starting units"
else
  echo "  ${ENV_DIR}/.env exists — keeping"
fi

echo "[5/6] grant deployer ssh access"
# The CI/CD deploy user is the same `waiter` user. The SSH public key must be
# added to /home/waiter/.ssh/authorized_keys out-of-band (e.g. via cloud-init
# or `ssh-copy-id`). This script does not write keys.
install -d -o "${APP_USER}" -g "${APP_USER}" -m 0700 "/home/${APP_USER}/.ssh"
touch "/home/${APP_USER}/.ssh/authorized_keys"
chown "${APP_USER}:${APP_USER}" "/home/${APP_USER}/.ssh/authorized_keys"
chmod 0600 "/home/${APP_USER}/.ssh/authorized_keys"

# Allow `waiter` to restart only its own units without password.
SUDOERS_FILE="/etc/sudoers.d/telegram-waiter"
cat > "${SUDOERS_FILE}" <<SUDO
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl restart bot-guest.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl restart bot-admin.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl start bot-guest.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl start bot-admin.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl stop bot-guest.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl stop bot-admin.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl is-active bot-guest.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl is-active bot-admin.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl is-failed bot-guest.service
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl is-failed bot-admin.service
SUDO
chmod 0440 "${SUDOERS_FILE}"
visudo -c -f "${SUDOERS_FILE}" >/dev/null

echo "[6/6] systemd units (placed but not started — code is not deployed yet)"
if [[ -d "${UNIT_SRC}" ]]; then
  install -m 0644 "${UNIT_SRC}/bot-guest.service" /etc/systemd/system/bot-guest.service
  install -m 0644 "${UNIT_SRC}/bot-admin.service" /etc/systemd/system/bot-admin.service
  systemctl daemon-reload
  systemctl enable bot-guest.service bot-admin.service
  echo "  units enabled. Will start after first CI/CD deploy."
else
  echo "  ${UNIT_SRC} missing — bootstrap before first 'git pull' is fine,"
  echo "  re-run after first deploy or copy units manually."
fi

echo ""
echo "DONE. Next:"
echo "  1. Add the CI/CD ssh pubkey to /home/${APP_USER}/.ssh/authorized_keys"
echo "  2. Fill ${ENV_DIR}/.env"
echo "  3. In GitHub repo Settings → Secrets: set DEPLOY_SSH_HOST, DEPLOY_SSH_USER=${APP_USER}, DEPLOY_SSH_KEY, DEPLOY_SSH_KNOWN_HOSTS"
echo "  4. Push to main — CI runs validate → deploy → bots start."
