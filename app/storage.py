from __future__ import annotations

import json
from pathlib import Path

from .models import LanguageCode, ReminderItem, SaveVocabRequest, SavedVocabItem


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VOCAB_PATH = DATA_DIR / "saved_vocab.json"
REMINDERS_PATH = DATA_DIR / "reminders.json"
ADVENTURE_BRAIN_DIR = DATA_DIR / "adventure_brains"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ADVENTURE_BRAIN_DIR.mkdir(parents=True, exist_ok=True)


def load_vocab(language: LanguageCode = "french") -> list[SavedVocabItem]:
    _ensure_data_dir()
    if not VOCAB_PATH.exists():
        return []
    raw = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    return [SavedVocabItem(**item) for item in raw if item.get("language", "french") == language]


def load_phrase_dictionary(language: LanguageCode = "french") -> dict[str, dict[str, str]]:
    _ensure_data_dir()
    dictionary_path = DATA_DIR / f"{language}_dictionary.json"
    if not dictionary_path.exists():
        return {}
    return json.loads(dictionary_path.read_text(encoding="utf-8"))


def save_vocab_item(request: SaveVocabRequest) -> list[SavedVocabItem]:
    _ensure_data_dir()
    existing_raw: list[dict[str, str]] = []
    if VOCAB_PATH.exists():
        existing_raw = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    items = [SavedVocabItem(**item) for item in existing_raw]
    candidate = SavedVocabItem(**request.model_dump())

    for existing in items:
        if (
            existing.language == candidate.language
            and
            existing.english.strip().lower() == candidate.english.strip().lower()
            and existing.french.strip().lower() == candidate.french.strip().lower()
        ):
            return [item for item in items if item.language == request.language]

    items.append(candidate)
    VOCAB_PATH.write_text(
        json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return [item for item in items if item.language == request.language]


def vocab_to_anki_csv(items: list[SavedVocabItem], language: LanguageCode = "french") -> str:
    language_label = "French" if language == "french" else "Spanish"
    lines = ["French;English;Note;Source sentence"]
    lines[0] = f"{language_label};English;Note;Source sentence"
    for item in items:
        values = [
            item.french.replace(";", ","),
            item.english.replace(";", ","),
            item.note.replace(";", ","),
            item.source_sentence.replace(";", ","),
        ]
        lines.append(";".join(values))
    return "\n".join(lines) + "\n"


def load_reminders(language: LanguageCode = "french") -> list[ReminderItem]:
    _ensure_data_dir()
    if not REMINDERS_PATH.exists():
        return []
    raw = json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
    return [ReminderItem(**item) for item in raw if item.get("language", "french") == language]


def record_reminder_hit(
    *,
    language: LanguageCode = "french",
    key: str,
    label: str,
    explanation: str,
    target: str,
    answer: str,
) -> list[ReminderItem]:
    _ensure_data_dir()
    existing_raw: list[dict[str, str]] = []
    if REMINDERS_PATH.exists():
        existing_raw = json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
    items = [ReminderItem(**item) for item in existing_raw]

    for item in items:
        if item.language == language and item.key == key:
            item.count += 1
            item.label = label
            item.explanation = explanation
            item.last_target = target
            item.last_answer = answer
            break
    else:
        items.append(
            ReminderItem(
                language=language,
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
    return [item for item in items if item.language == language]


def save_adventure_brain(session_id: str, markdown: str) -> Path:
    _ensure_data_dir()
    target = ADVENTURE_BRAIN_DIR / f"{session_id}.md"
    target.write_text(markdown, encoding="utf-8")
    return target
