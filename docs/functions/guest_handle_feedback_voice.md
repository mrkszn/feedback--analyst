# bot_guest.handlers.feedback.guest_feedback_voice

## Назначение

Принимает голосовое сообщение в `AWAITING_FEEDBACK`. Скачивает через [[utils_voice_download]], транскрибирует через [[integrations_whisper_transcribe]], затем тот же `_process_feedback` что и у текстовой ветки.

## Шаги

1. `download_voice_to_tmp(voice.file_id, message.bot)` → `Path`.
2. `try ... finally`: `transcribe_voice(path)`; в finally — `path.unlink(missing_ok=True)`.
3. Если расшифровка пустая — попросить отправить текстом.
4. Иначе — `_process_feedback(raw_text=text, source="voice")`.

## Edge

- Whisper не услышал — fallback на просьбу текста.
- Удаление tmp в finally — даже если transcribe бросил, файл удаляется.
- Если бот крашнется между download и transcribe — leak (см. Outstanding questions в current_changes.md).

## /goal

Voice-ветка инициирует тот же пайплайн что и текстовая. Tmp-файл удаляется.

## Next

→ [guest_handle_answer.md](guest_handle_answer.md)
