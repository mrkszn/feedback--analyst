import uuid
from pathlib import Path

from aiogram import Bot

from config import settings


async def download_voice_to_tmp(
    file_id: str,
    bot: Bot,
    tmp_dir: Path | str | None = None,
) -> Path:
    tmp_dir = Path(settings.voice_tmp_dir) if tmp_dir is None else Path(tmp_dir)
    tmp_dir = tmp_dir.resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    file = await bot.get_file(file_id)
    if not file.file_path:
        raise ValueError(f"Telegram returned File without file_path for file_id={file_id}")

    ext = Path(file.file_path).suffix or ".oga"
    local_path = tmp_dir / f"{uuid.uuid4().hex}{ext}"
    await bot.download_file(file.file_path, destination=str(local_path))
    return local_path
