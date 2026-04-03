from __future__ import annotations

import json
from pathlib import Path

from .models import LanguageCode, ReminderExample, ReminderItem, SaveVocabRequest, SavedVocabItem, StoryMemoryEntry


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VOCAB_PATH = DATA_DIR / "saved_vocab.json"
REMINDERS_PATH = DATA_DIR / "reminders.json"
ADVENTURE_BRAIN_DIR = DATA_DIR / "adventure_brains"
STORY_BRAIN_PATH = DATA_DIR / "story_brain.json"
STORY_BRAIN_MARKDOWN_PATH = DATA_DIR / "story_brain.md"
RECENT_STORY_DETAIL_COUNT = 5
OLDER_STORY_SUMMARY_COUNT = 20


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ADVENTURE_BRAIN_DIR.mkdir(parents=True, exist_ok=True)


def load_vocab(language: LanguageCode = "french") -> list[SavedVocabItem]:
    _ensure_data_dir()
    if not VOCAB_PATH.exists():
        return []
    raw = _read_json(VOCAB_PATH)
    return [SavedVocabItem(**item) for item in raw if item.get("language", "french") == language]


def load_phrase_dictionary(language: LanguageCode = "french") -> dict[str, dict[str, str]]:
    _ensure_data_dir()
    dictionary_path = DATA_DIR / f"{language}_dictionary.json"
    if not dictionary_path.exists():
        return {}
    return _read_json(dictionary_path)


def save_vocab_item(request: SaveVocabRequest) -> list[SavedVocabItem]:
    _ensure_data_dir()
    existing_raw: list[dict[str, str]] = []
    if VOCAB_PATH.exists():
        existing_raw = _read_json(VOCAB_PATH)
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
    raw = _read_json(REMINDERS_PATH)
    return [ReminderItem(**item) for item in raw if item.get("language", "french") == language]


def record_reminder_hit(
    *,
    language: LanguageCode = "french",
    key: str,
    label: str,
    explanation: str,
    target: str,
    answer: str,
    example_wrong: str = "",
    example_correct: str = "",
    example_wrong_focus: str = "",
    example_correct_focus: str = "",
) -> list[ReminderItem]:
    _ensure_data_dir()
    existing_raw: list[dict[str, str]] = []
    if REMINDERS_PATH.exists():
        existing_raw = _read_json(REMINDERS_PATH)
    items = [ReminderItem(**item) for item in existing_raw]

    for item in items:
        if item.language == language and item.key == key:
            item.count += 1
            item.label = label
            item.explanation = explanation
            item.last_target = target
            item.last_answer = answer
            if example_wrong and example_correct:
                normalized_wrong = example_wrong.strip().lower()
                normalized_correct = example_correct.strip().lower()
                item.examples = [
                    example for example in item.examples
                    if not (
                        example.wrong.strip().lower() == normalized_wrong
                        and example.correct.strip().lower() == normalized_correct
                    )
                ]
                item.examples.insert(
                    0,
                    ReminderExample(
                        wrong=example_wrong,
                        correct=example_correct,
                        wrong_focus=example_wrong_focus,
                        correct_focus=example_correct_focus,
                    ),
                )
                item.examples = item.examples[:3]
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
                examples=(
                    [
                        ReminderExample(
                            wrong=example_wrong,
                            correct=example_correct,
                            wrong_focus=example_wrong_focus,
                            correct_focus=example_correct_focus,
                        )
                    ]
                    if example_wrong and example_correct
                    else []
                ),
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


def load_story_brain(language: LanguageCode | None = None) -> list[StoryMemoryEntry]:
    _ensure_data_dir()
    if not STORY_BRAIN_PATH.exists():
        return []
    raw = _read_json(STORY_BRAIN_PATH)
    items = [StoryMemoryEntry(**item) for item in raw]
    if language is None:
        return items
    return [item for item in items if item.language == language]


def _write_story_brain(items: list[StoryMemoryEntry]) -> None:
    STORY_BRAIN_PATH.write_text(
        json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    STORY_BRAIN_MARKDOWN_PATH.write_text(render_story_brain_markdown(items), encoding="utf-8")


def record_completed_story(entry: StoryMemoryEntry) -> tuple[list[StoryMemoryEntry], bool]:
    _ensure_data_dir()
    items = load_story_brain()
    recorded = True
    for index, existing in enumerate(items):
        if existing.lesson_id == entry.lesson_id:
            items[index] = entry
            recorded = False
            break
    else:
        items.append(entry)

    items.sort(key=lambda item: item.completed_at, reverse=True)
    _write_story_brain(items)
    return items, recorded


def build_story_memory_guidance(language: LanguageCode) -> str:
    entries = load_story_brain(language)
    if not entries:
        return ""

    recent = entries[:RECENT_STORY_DETAIL_COUNT]
    older = entries[RECENT_STORY_DETAIL_COUNT:RECENT_STORY_DETAIL_COUNT + OLDER_STORY_SUMMARY_COUNT]
    lines = [
        "Story memory to keep this lesson fresh:",
        "- Avoid recycling the same core plot, setting, character dynamic, or vocabulary domain from these completed stories.",
        "- Prefer a clearly different setting, conflict, and lexical field when possible.",
        "",
        "Recent completed stories to avoid overlapping with too closely:",
    ]
    for item in recent:
        plot_bits = "; ".join(item.plot_beats[:3]) or "No plot beats recorded."
        vocab_bits = ", ".join(item.vocab_domains[:4]) or "No vocab domains recorded."
        grammar_bits = ", ".join(item.grammar_focuses[:4]) or "No grammar focus recorded."
        lines.extend([
            f"- {item.title} [{item.theme}]",
            f"  Summary: {item.synopsis}",
            f"  Setting/tone: {item.setting or 'Not specified'}; {item.tone or 'No tone note'}",
            f"  Plot beats: {plot_bits}",
            f"  Vocab domains: {vocab_bits}",
            f"  Grammar focus: {grammar_bits}",
        ])

    if older:
        lines.extend(["", "Older completed story summaries:"])
        for item in older:
            lines.append(f"- {item.title}: {item.one_line_summary}")

    return "\n".join(lines)


def render_story_brain_markdown(items: list[StoryMemoryEntry] | None = None) -> str:
    entries = items if items is not None else load_story_brain()
    lines = ["# Story Brain", ""]
    if not entries:
        lines.append("_No completed stories recorded yet._")
        return "\n".join(lines) + "\n"

    for language in ("french", "spanish"):
        language_entries = [item for item in entries if item.language == language]
        if not language_entries:
            continue
        language_label = "French" if language == "french" else "Spanish"
        lines.extend([f"## {language_label}", ""])
        recent = language_entries[:RECENT_STORY_DETAIL_COUNT]
        older = language_entries[RECENT_STORY_DETAIL_COUNT:]
        lines.extend(["### Recent detailed notes", ""])
        for item in recent:
            lines.extend([
                f"#### {item.title}",
                f"- Theme: {item.theme}",
                f"- Difficulty: {item.difficulty}",
                f"- Type: {item.lesson_type}",
                f"- Completed: {item.completed_at}",
                f"- One-line summary: {item.one_line_summary}",
                f"- Synopsis: {item.synopsis}",
                f"- Setting: {item.setting or '—'}",
                f"- Tone: {item.tone or '—'}",
                f"- Plot beats: {', '.join(item.plot_beats) if item.plot_beats else '—'}",
                f"- Vocab domains: {', '.join(item.vocab_domains) if item.vocab_domains else '—'}",
                f"- Grammar focus: {', '.join(item.grammar_focuses) if item.grammar_focuses else '—'}",
                f"- Freshness note: {item.freshness_note or '—'}",
                "",
            ])
        if older:
            lines.extend(["### Older one-line summaries", ""])
            for item in older[:OLDER_STORY_SUMMARY_COUNT]:
                lines.append(f"- {item.title}: {item.one_line_summary}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
