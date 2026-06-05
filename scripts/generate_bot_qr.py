"""Generate a QR-code PNG that opens the guest bot in Telegram.

Usage:
    # Plain "open bot" QR — brand-violet eyes on white, 512×512 PNG.
    uv run python scripts/generate_bot_qr.py @ADMIN_FEEDBACK

    # Same, but with a start payload (will arrive at the bot as /start <payload>
    # in t.me deep-link semantics — useful for tagging tables / sources).
    uv run python scripts/generate_bot_qr.py @ADMIN_FEEDBACK --start table12

    # Custom output path / size.
    uv run python scripts/generate_bot_qr.py @MyBot --out runs/qr.png --size 1024

    # Auto-discover username via the bot token (no need to pass @handle).
    uv run python scripts/generate_bot_qr.py --auto

The script avoids any "import the bot's main" surprises — it talks to the
Telegram REST API directly for --auto, and otherwise just builds a
`https://t.me/<bot>` deep-link.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

try:
    import qrcode
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "qrcode is not installed. Add it to dev deps:\n  uv add --group dev qrcode[pil]\n"
    )
    raise SystemExit(1) from exc

from PIL import Image  # qrcode[pil] brings Pillow in


def _resolve_username_from_token(token: str) -> str:
    """Hit https://api.telegram.org/bot<TOKEN>/getMe → return `username`."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url, timeout=10) as resp:
        import json

        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram getMe returned not-ok: {body}")
    user = body["result"].get("username")
    if not user:
        raise RuntimeError("Bot has no username — set one in @BotFather first.")
    return str(user)


def _build_url(username: str, start_payload: str | None) -> str:
    user = username.lstrip("@")
    if start_payload:
        # Telegram t.me deep-link: tapping the QR opens the bot AND fires
        # /start <payload> on first interaction. Payloads are limited to
        # 64 chars in [A-Za-z0-9_-]; we don't validate, Telegram will.
        return f"https://t.me/{user}?start={start_payload}"
    return f"https://t.me/{user}"


def _make_qr_image(
    url: str,
    *,
    size_px: int,
    fg: str,
    bg: str,
) -> Image.Image:
    """Build a QR with strong error-correction, then resize cleanly."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30 % — survives a logo / damage
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    # qrcode + Pillow expose loose `Any` typing on their wrappers; cast to
    # Image so the call-site stays strongly typed for mypy.
    img: Image.Image = qr.make_image(fill_color=fg, back_color=bg).convert("RGB")
    if size_px and img.size[0] != size_px:
        img = img.resize((size_px, size_px), Image.Resampling.NEAREST)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "username",
        nargs="?",
        help="Bot username (with or without leading @). Optional if --auto is given.",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Optional start payload — fires /start <payload> on first interaction.",
    )
    parser.add_argument(
        "--out",
        default="bot_qr.png",
        help="Output PNG path. Default: ./bot_qr.png",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=512,
        help="Output size in px (square). Default: 512.",
    )
    parser.add_argument(
        "--fg",
        default="#7c3aed",  # InsightFlow brand violet
        help="QR foreground colour (hex). Default: #7c3aed (brand violet).",
    )
    parser.add_argument(
        "--bg",
        default="#ffffff",
        help="QR background colour (hex). Default: white.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Resolve the bot username by hitting Telegram getMe with TELEGRAM_GUEST_BOT_TOKEN.",
    )
    args = parser.parse_args()

    if args.auto:
        token = os.environ.get("TELEGRAM_GUEST_BOT_TOKEN")
        if not token:
            sys.stderr.write(
                "--auto requested but TELEGRAM_GUEST_BOT_TOKEN is not in env.\n"
                "Source your .env first, or pass the username explicitly.\n"
            )
            raise SystemExit(2)
        username = _resolve_username_from_token(token)
    else:
        if not args.username:
            parser.error("Pass the bot username, or use --auto.")
        username = args.username

    url = _build_url(username, args.start)
    img = _make_qr_image(url, size_px=args.size, fg=args.fg, bg=args.bg)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"✓ QR saved → {out.resolve()}")
    print(f"  payload  → {url}")


if __name__ == "__main__":
    main()
