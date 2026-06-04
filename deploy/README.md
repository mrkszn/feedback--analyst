# Deploy — VPS + GitHub Actions

Auto-deploy: `git push origin main` → CI runs lint/types/tests → on green, `rsync` code to VPS and `systemctl restart` both bots.

## One-time VPS bootstrap

Done already for `178.105.54.29` (Ubuntu 24.04, Hetzner). To redo on a fresh host:

```bash
# from local machine, as root on VPS:
ssh root@<host> 'mkdir -p /opt/telegram-waiter'
rsync -az --exclude='.venv/' --exclude='.git/' --exclude='__pycache__/' \
  --exclude='runs/' --exclude='tmp/' --exclude='.env' --exclude='design/' \
  ./ root@<host>:/opt/telegram-waiter/
ssh root@<host> 'bash /opt/telegram-waiter/deploy/install.sh'
ssh root@<host> 'chown -R waiter:waiter /opt/telegram-waiter'

# copy your local .env (dev creds reused as prod for now)
scp .env root@<host>:/etc/telegram-waiter/.env
ssh root@<host> 'chown root:waiter /etc/telegram-waiter/.env && chmod 0640 /etc/telegram-waiter/.env'

# sync deps as waiter
ssh root@<host> 'sudo -u waiter /usr/local/bin/uv sync --frozen --project /opt/telegram-waiter'

# install deploy keypair for GitHub Actions
ssh-keygen -t ed25519 -N "" -C github-actions-deploy -f deploy/secrets/deploy_key
ssh root@<host> "echo '$(cat deploy/secrets/deploy_key.pub)' >> /home/waiter/.ssh/authorized_keys"
ssh-keyscan -t ed25519,rsa,ecdsa <host> > deploy/secrets/known_hosts
```

`deploy/secrets/` is `.gitignore`-d. Keep that directory local.

## GitHub Secrets

Add at `Settings → Secrets and variables → Actions → New repository secret`:

| Name | Value | Where to find |
|---|---|---|
| `DEPLOY_SSH_HOST` | `178.105.54.29` | — |
| `DEPLOY_SSH_USER` | `waiter` | — |
| `DEPLOY_SSH_KEY` | full contents of `deploy/secrets/deploy_key` (private) | `cat deploy/secrets/deploy_key` |
| `DEPLOY_SSH_KNOWN_HOSTS` | full contents of `deploy/secrets/known_hosts` | `cat deploy/secrets/known_hosts` |

After setting all four, push any commit to `main` (or trigger `workflow_dispatch`) and watch the `deploy` job in Actions.

## Service ops on VPS

```bash
ssh root@178.105.54.29 'systemctl status bot-guest bot-admin --no-pager'
ssh root@178.105.54.29 'journalctl -u bot-guest -f'
ssh root@178.105.54.29 'cat /var/log/telegram-waiter/bot-guest.log | tail -50'
```

Restart manually:

```bash
ssh waiter@178.105.54.29 'sudo systemctl restart bot-guest.service bot-admin.service'
```

## Updating prod .env

Env file lives at `/etc/telegram-waiter/.env`, owned `root:waiter` mode `0640`. CI/CD does **not** touch it — update manually:

```bash
scp .env root@178.105.54.29:/etc/telegram-waiter/.env
ssh root@178.105.54.29 'chown root:waiter /etc/telegram-waiter/.env && chmod 0640 /etc/telegram-waiter/.env && systemctl restart bot-guest bot-admin'
```

## ⚠️ Dev creds = single-polling-consumer rule

We're running dev Telegram bot tokens in prod. **One token = one polling consumer.** When the VPS bots are up, local `uv run python -m channels.telegram.guest_bot` / `python -m presentations.telegram_admin` will silently lose updates (Telegram routes each update to whichever consumer fetched it first). Stop local bots before working on the same tokens.

When ready to split: create new `@<restaurant>_bot` tokens at @BotFather, push to `/etc/telegram-waiter/.env` on VPS only, keep dev tokens local.
