"""Unit-тесты для utils.voice_download.download_voice_to_tmp.

Сетевые вызовы Telegram замоканы через AsyncMock; `bot.download_file`
имеет side_effect, который создаёт реальный пустой файл по destination —
так мы проверяем и имя файла (UUID + ext), и факт записи.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramAPIError
from aiogram.types import File

from utils.voice_download import download_voice_to_tmp


def _make_bot(file_path: str | None) -> AsyncMock:
    """Собирает AsyncMock-Bot с прибитыми get_file/download_file."""
    bot = AsyncMock()
    bot.get_file = AsyncMock(
        return_value=File(file_id="fid", file_unique_id="uid", file_path=file_path)
    )

    async def _write(src_path: str, destination: str) -> None:
        Path(destination).write_bytes(b"")

    bot.download_file = AsyncMock(side_effect=_write)
    return bot


async def test_download_creates_file_with_uuid_name(tmp_path: Path) -> None:
    bot = _make_bot("voice/file_123.oga")

    result = await download_voice_to_tmp("fid", bot, tmp_dir=tmp_path)

    assert result.exists()
    assert result.parent == tmp_path.resolve()
    assert result.suffix == ".oga"
    stem = result.stem
    assert len(stem) == 32
    int(stem, 16)  # hex — иначе ValueError


async def test_default_tmp_dir_from_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from config import settings

    monkeypatch.setattr(settings, "voice_tmp_dir", str(tmp_path))
    bot = _make_bot("voice/file.oga")

    result = await download_voice_to_tmp("fid", bot, tmp_dir=None)

    assert result.parent == tmp_path.resolve()
    assert result.exists()


async def test_explicit_tmp_dir_is_created(tmp_path: Path) -> None:
    target = tmp_path / "new_sub"
    assert not target.exists()
    bot = _make_bot("voice/file.oga")

    result = await download_voice_to_tmp("fid", bot, tmp_dir=target)

    assert target.exists()
    assert target.is_dir()
    assert result.parent == target.resolve()


async def test_oga_default_extension_when_path_has_none(tmp_path: Path) -> None:
    bot = _make_bot("voice/file_without_ext")

    result = await download_voice_to_tmp("fid", bot, tmp_dir=tmp_path)

    assert result.suffix == ".oga"
    assert result.exists()


async def test_telegram_api_error_propagates(tmp_path: Path) -> None:
    bot = AsyncMock()
    bot.get_file = AsyncMock(side_effect=TelegramAPIError(method=None, message="boom"))  # type: ignore[arg-type]
    bot.download_file = AsyncMock()

    with pytest.raises(TelegramAPIError):
        await download_voice_to_tmp("fid", bot, tmp_dir=tmp_path)

    bot.download_file.assert_not_awaited()
