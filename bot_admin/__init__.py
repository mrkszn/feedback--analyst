"""Backward-compat shim for systemd units pinned to the pre-M1 module path.

The admin bot moved to `presentations.telegram_admin` in the M1 refactor (R1,
commit fa62669). The systemd unit file in the repo was updated, but the unit
already installed at /etc/systemd/system/bot-admin.service on the VPS still
points at the old path (`python -m bot_admin`) — the install.sh that copies
units to /etc/systemd/system/ only runs once per VPS bootstrap.

Until the VPS sudoers is widened to allow `systemctl daemon-reload` + install
of unit files (so CI can sync them), this package re-exports the new
entry-point so the legacy command keeps working. Delete after the unit on
the VPS is migrated.
"""
