from __future__ import annotations

import json
from pathlib import Path

from .models import ReminderItem, SaveVocabRequest, SavedVocabItem


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VOCAB_PATH = DATA_DIR / "saved_vocab.json"
REMINDERS_PATH = DATA_DIR / "reminders.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_vocab() -> list[SavedVocabItem]:
    _ensure_data_dir()
    if not VOCAB_PATH.exists():
        return []
    raw = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    return [SavedVocabItem(**item) for item in raw]


def save_vocab_item(request: SaveVocabRequest) -> list[SavedVocabItem]:
    _ensure_data_dir()
    items = load_vocab()
    candidate = SavedVocabItem(**request.model_dump())

    for existing in items:
        if (
            existing.english.strip().lower() == candidate.english.strip().lower()
            and existing.french.strip().lower() == candidate.french.strip().lower()
        ):
            return items

    items.append(candidate)
    VOCAB_PATH.write_text(
        json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return items


def vocab_to_anki_csv(items: list[SavedVocabItem]) -> str:
    lines = ["French;English;Note;Source sentence"]
    for item in items:
        values = [
            item.french.replace(";", ","),
            item.english.replace(";", ","),
            item.note.replace(";", ","),
            item.source_sentence.replace(";", ","),
        ]
        lines.append(";".join(values))
    return "\n".join(lines) + "\n"


def load_reminders() -> list[ReminderItem]:
    _ensure_data_dir()
    if not REMINDERS_PATH.exists():
        return []
    raw = json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
    return [ReminderItem(**item) for item in raw]


def record_reminder_hit(
    *,
    key: str,
    label: str,
    explanation: str,
    target: str,
    answer: str,
) -> list[ReminderItem]:
    _ensure_data_dir()
    items = load_reminders()

    for item in items:
        if item.key == key:
            item.count += 1
            item.last_target = target
            item.last_answer = answer
            break
    else:
        items.append(
            ReminderItem(
                key=key,
                label=label,
                explanation=explanation,
                count=1,
                last_target=target,
                last_answer=answer,
            )
        )

    REMINDERS_PATH.write_text(
        json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return items
