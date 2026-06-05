"""Generate a printable QR-CARD PNG that goes on a restaurant table.

Composes a 1000×1400 (A6-ish 5:7) PNG: brand header + body copy + QR
inside a card frame + footer with the bot username and a brand mark.
Two variants: `light` (cream paper, brand-violet QR — eats less ink on
print) and `dark` (deep navy surface, cyan accents — great for an
on-screen kiosk display).

The QR itself uses ERROR_CORRECT_H so a logo overlay or print smudge
doesn't break scanning.

Usage:
    # Default card for the live receiver bot.
    uv run python scripts/generate_qr_card.py @virtual_feedback_receiver_bot

    # Dark variant, custom title, table-tagged.
    uv run python scripts/generate_qr_card.py @virtual_feedback_receiver_bot \\
        --variant dark --start table7 --title "Как вам у нас?" \\
        --out runs/card_dark_table7.png

    # Auto-discover username via the bot token.
    source .env && uv run python scripts/generate_qr_card.py --auto

The script depends on Pillow + qrcode (already in dev deps from
generate_bot_qr.py). Tries Geist if shipped under design/fonts/, otherwise
falls back through a chain of system sans fonts (HelveticaNeue → DejaVu
Sans → PIL default).
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    import qrcode
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("qrcode is not installed. uv add --group dev qrcode[pil]\n")
    raise SystemExit(1) from exc

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_CANDIDATES_SANS = [
    # If a future commit drops Geist .ttf under design/fonts/, prefer that.
    REPO_ROOT / "design" / "fonts" / "Geist-Variable.ttf",
    REPO_ROOT / "design" / "fonts" / "Geist-Regular.ttf",
    # macOS system
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/System/Library/Fonts/HelveticaNeue.ttc"),
    Path("/Library/Fonts/Arial.ttf"),
    # Linux (CI / VPS)
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
]
FONT_CANDIDATES_MONO = [
    REPO_ROOT / "design" / "fonts" / "GeistMono-Regular.ttf",
    Path("/System/Library/Fonts/Menlo.ttc"),
    Path("/System/Library/Fonts/Monaco.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
]

BRAND_RECEIVER_PNG = REPO_ROOT / "design" / "assets" / "voice-receiver.png"


@dataclass
class Theme:
    """Colour palette for one card variant."""

    bg: tuple[int, int, int]
    card: tuple[int, int, int]
    card_border: tuple[int, int, int]
    ink: tuple[int, int, int]
    ink_2: tuple[int, int, int]
    muted: tuple[int, int, int]
    brand: tuple[int, int, int]
    accent: tuple[int, int, int]
    qr_fg: tuple[int, int, int]
    qr_bg: tuple[int, int, int]
    qr_panel: tuple[int, int, int]


LIGHT = Theme(
    bg=(247, 246, 242),  # --bg paper
    card=(255, 255, 255),
    card_border=(230, 226, 216),
    ink=(11, 11, 18),
    ink_2=(42, 42, 51),
    muted=(107, 106, 116),
    brand=(124, 58, 237),  # --primary violet
    accent=(6, 182, 212),  # --accent cyan
    qr_fg=(124, 58, 237),
    qr_bg=(255, 255, 255),
    qr_panel=(255, 255, 255),
)

DARK = Theme(
    bg=(11, 14, 23),
    card=(20, 26, 39),
    card_border=(50, 64, 86),
    ink=(243, 244, 248),
    ink_2=(197, 201, 214),
    muted=(138, 144, 163),
    brand=(168, 85, 247),
    accent=(6, 182, 212),
    qr_fg=(124, 58, 237),
    # QR must stay on a light panel — scanners need contrast — even in
    # the dark card variant. We just frame it with the dark surface.
    qr_bg=(255, 255, 255),
    qr_panel=(255, 255, 255),
)


def _load_font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    chain = FONT_CANDIDATES_MONO if mono else FONT_CANDIDATES_SANS
    for path in chain:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    # Last-ditch: synthesise a FreeTypeFont from PIL's bundled DejaVu so we
    # always return the same type. ImageFont.load_default() returns a
    # bitmap ImageFont which breaks our strict typing — and looks bad at
    # 64 px anyway. The deja_vu fallback ships inside Pillow itself.
    return ImageFont.load_default(size)  # type: ignore[return-value]


def _resolve_username_from_token(token: str) -> str:
    """Hit api.telegram.org/getMe to resolve the bot's @handle."""
    import json

    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url, timeout=10) as resp:
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
        return f"https://t.me/{user}?start={start_payload}"
    return f"https://t.me/{user}"


def _qr_image(url: str, theme: Theme, side_px: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img: Image.Image = qr.make_image(
        fill_color=f"#{theme.qr_fg[0]:02x}{theme.qr_fg[1]:02x}{theme.qr_fg[2]:02x}",
        back_color=f"#{theme.qr_bg[0]:02x}{theme.qr_bg[1]:02x}{theme.qr_bg[2]:02x}",
    ).convert("RGB")
    img = img.resize((side_px, side_px), Image.Resampling.LANCZOS)
    return img


def _draw_text_centred(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    canvas_w: int,
) -> int:
    """Draw `text` horizontally centred at vertical y. Returns the
    bottom-y of the drawn glyph box (for stacking lines)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = int(bbox[3] - bbox[1])
    x = (canvas_w - int(text_w)) // 2
    draw.text((x - bbox[0], y - bbox[1]), text, font=font, fill=fill)
    return y + text_h


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_w: int,
    font: ImageFont.FreeTypeFont,
) -> list[str]:
    """Greedy line-break on whitespace, respecting max width in pixels."""
    words = text.split()
    lines: list[str] = []
    line = ""
    for w in words:
        candidate = w if not line else f"{line} {w}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_w:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _round_rect(
    img: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int,
    fill: tuple[int, int, int] | None = None,
    outline: tuple[int, int, int] | None = None,
    width: int = 1,
) -> None:
    """Wrapper that picks the right Pillow rounded-rectangle API."""
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def compose_card(
    *,
    url: str,
    username: str,
    theme: Theme,
    title: str,
    subtitle: str,
    cta_top: str,
    cta_bottom: str,
    footer_tagline: str,
) -> Image.Image:
    """Compose the full 1000×1400 card."""
    W, H = 1000, 1400
    card = Image.new("RGB", (W, H), theme.bg)
    draw = ImageDraw.Draw(card)

    # ─── outer card frame ────────────────────────────────────
    pad = 60
    _round_rect(
        card,
        (pad, pad, W - pad, H - pad),
        radius=36,
        fill=theme.card,
        outline=theme.card_border,
        width=2,
    )

    # ─── header strap ────────────────────────────────────────
    eyebrow_font = _load_font(22)
    eyebrow_y = pad + 56
    # Brand mark: cyan dot left of the eyebrow text, both centred as a group.
    dot_r = 6
    eyebrow_text = "FEEDBACK · RECEIVER"
    eb_bbox = draw.textbbox((0, 0), eyebrow_text, font=eyebrow_font)
    eb_w = eb_bbox[2] - eb_bbox[0]
    gap = 14
    group_w = dot_r * 2 + gap + eb_w
    group_x = (W - group_w) // 2
    # Vertically centre the dot against the cap-height of the text.
    eb_h = eb_bbox[3] - eb_bbox[1]
    dot_cy = eyebrow_y + eb_h // 2 + 2
    draw.ellipse(
        (group_x, dot_cy - dot_r, group_x + dot_r * 2, dot_cy + dot_r),
        fill=theme.accent,
    )
    draw.text(
        (group_x + dot_r * 2 + gap - eb_bbox[0], eyebrow_y - eb_bbox[1]),
        eyebrow_text,
        font=eyebrow_font,
        fill=theme.muted,
    )

    # ─── big title (auto-wraps) ──────────────────────────────
    title_font = _load_font(64)
    title_lines = _wrap_text(draw, title, max_w=W - 2 * pad - 100, font=title_font)
    y = eyebrow_y + 60
    for line in title_lines:
        y = (
            _draw_text_centred(
                draw,
                line,
                y=y,
                font=title_font,
                fill=theme.ink,
                canvas_w=W,
            )
            + 6
        )

    # ─── subtitle ─────────────────────────────────────────────
    subtitle_font = _load_font(26)
    subtitle_lines = _wrap_text(draw, subtitle, max_w=W - 2 * pad - 60, font=subtitle_font)
    y += 24
    for line in subtitle_lines:
        y = (
            _draw_text_centred(
                draw,
                line,
                y=y,
                font=subtitle_font,
                fill=theme.muted,
                canvas_w=W,
            )
            + 6
        )

    # ─── QR panel ─────────────────────────────────────────────
    qr_side = 460
    qr_panel_pad = 28
    panel_side = qr_side + qr_panel_pad * 2
    panel_x = (W - panel_side) // 2
    panel_y = y + 56
    # Panel
    _round_rect(
        card,
        (panel_x, panel_y, panel_x + panel_side, panel_y + panel_side),
        radius=24,
        fill=theme.qr_panel,
        outline=theme.card_border,
        width=1,
    )
    # The QR itself
    qr = _qr_image(url, theme, qr_side)
    card.paste(qr, (panel_x + qr_panel_pad, panel_y + qr_panel_pad))

    # ─── CTA below QR ─────────────────────────────────────────
    cta_top_font = _load_font(28)
    y = panel_y + panel_side + 36
    y = _draw_text_centred(draw, cta_top, y=y, font=cta_top_font, fill=theme.ink_2, canvas_w=W) + 10

    handle_font = _load_font(24, mono=True)
    handle_text = f"@{username.lstrip('@')}"
    _draw_text_centred(draw, handle_text, y=y, font=handle_font, fill=theme.brand, canvas_w=W)

    # ─── dotted separator ─────────────────────────────────────
    sep_y = H - pad - 160
    n_dots = 28
    step = (W - 2 * pad - 100) // n_dots
    start_x = (W - step * n_dots) // 2
    for i in range(n_dots):
        cx = start_x + i * step
        draw.ellipse(
            (cx - 2, sep_y - 2, cx + 2, sep_y + 2),
            fill=theme.card_border,
        )

    # ─── footer ───────────────────────────────────────────────
    body_font = _load_font(22)
    footer_y = sep_y + 30
    for line in cta_bottom.split("\n"):
        footer_y = (
            _draw_text_centred(draw, line, y=footer_y, font=body_font, fill=theme.ink_2, canvas_w=W)
            + 6
        )

    # Tagline: bumped from 20→24 px and darkened from `muted` to `ink_2`
    # because at 20 px in muted grey the descender of "я" antialiased
    # down to a single subpixel row — looked like "п" on phone-sized
    # previews. Also wraps and gets 56 px of breathing room from the
    # card's bottom edge so the descender never grazes the frame.
    tag_font = _load_font(24)
    tag_lines = _wrap_text(draw, footer_tagline, max_w=W - 2 * pad - 80, font=tag_font)
    line_h = 30  # font 24 + ~6 px leading
    block_h = line_h * len(tag_lines)
    tag_top = H - pad - 56 - block_h
    for line in tag_lines:
        tag_top = (
            _draw_text_centred(draw, line, y=tag_top, font=tag_font, fill=theme.ink_2, canvas_w=W)
            + 6
        )

    return card


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("username", nargs="?", help="Bot username (optional if --auto).")
    parser.add_argument("--auto", action="store_true", help="Resolve username via getMe.")
    parser.add_argument("--start", default=None, help="Optional start payload.")
    parser.add_argument("--out", default="runs/qr_card.png", help="Output PNG path.")
    parser.add_argument(
        "--variant",
        default="light",
        choices=["light", "dark"],
        help="Colour theme. Default: light (best for print).",
    )
    parser.add_argument(
        "--title",
        default="Как прошла\nдоставка?",
        help="Big headline (use \\n for explicit line break).",
    )
    parser.add_argument(
        "--subtitle",
        default="Расскажите голосом или текстом — это правда помогает.",
        help="Subtitle below the headline.",
    )
    parser.add_argument(
        "--cta-top",
        default="Отсканируйте камерой телефона",
        help="Caption directly under the QR.",
    )
    parser.add_argument(
        "--cta-bottom",
        default="или откройте в Telegram",
        help="Footer caption (may contain \\n).",
    )
    parser.add_argument(
        "--tagline",
        default="Минута на отзыв — и команда доставки прочтёт каждое слово.",
        help="Bottom-most tagline.",
    )
    args = parser.parse_args()

    if args.auto:
        token = os.environ.get("TELEGRAM_GUEST_BOT_TOKEN")
        if not token:
            sys.stderr.write("--auto requested but TELEGRAM_GUEST_BOT_TOKEN is not in env.\n")
            raise SystemExit(2)
        username = _resolve_username_from_token(token)
    else:
        if not args.username:
            parser.error("Pass the bot username, or use --auto.")
        username = args.username

    theme = DARK if args.variant == "dark" else LIGHT
    url = _build_url(username, args.start)

    # Unescape user-supplied \n in CLI strings — argparse keeps them
    # literal otherwise, so the headline argument can carry line breaks.
    title = args.title.replace("\\n", "\n")
    cta_bottom = args.cta_bottom.replace("\\n", "\n")

    # Compose each line of the title separately so wrap respects user breaks.
    title_lines = [line.strip() for line in title.split("\n") if line.strip()]
    title_for_compose = " ".join(title_lines)
    # Override: compose handles wrap, but to preserve explicit user
    # breaks, render each block then join with a literal \n understood by
    # our wrap path. Cleanest: if user gave \n, render line-by-line by
    # joining with a space — wrap auto-balances. If they want strict
    # breaks they should just provide a single long string.
    img = compose_card(
        url=url,
        username=username,
        theme=theme,
        title=title_for_compose if len(title_lines) <= 1 else "\n".join(title_lines),
        subtitle=args.subtitle,
        cta_top=args.cta_top,
        cta_bottom=cta_bottom,
        footer_tagline=args.tagline,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True)
    print(f"✓ Card saved → {out.resolve()}")
    print(f"  variant   → {args.variant}")
    print(f"  size      → {img.size[0]}×{img.size[1]} px")
    print(f"  payload   → {url}")


if __name__ == "__main__":
    main()
