from __future__ import annotations

import json
import re
from pathlib import Path
from difflib import SequenceMatcher

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


_PATTERN_ARROW_RE = re.compile(r"\s*(?:->|→|=>|&rarr;)\s*")


def _split_pattern_parts(value: str) -> list[str]:
    return [part.strip() for part in _PATTERN_ARROW_RE.split(str(value or "")) if part.strip()]


def _normalize_pattern_example(
    wrong: str,
    correct: str,
    wrong_focus: str = "",
    correct_focus: str = "",
) -> ReminderExample | None:
    wrong_parts = _split_pattern_parts(wrong)
    correct_parts = _split_pattern_parts(correct)

    normalized_wrong = wrong_parts[0] if wrong_parts else str(wrong or "").strip()
    normalized_correct = correct_parts[-1] if correct_parts else str(correct or "").strip()

    if not normalized_correct and len(wrong_parts) >= 2:
        normalized_correct = wrong_parts[-1]

    if normalized_wrong == normalized_correct and len(wrong_parts) >= 2:
        normalized_correct = wrong_parts[-1]

    normalized_wrong = normalized_wrong.strip()
    normalized_correct = normalized_correct.strip()
    if not normalized_wrong or not normalized_correct:
        return None

    normalized_wrong_focus = str(wrong_focus or "").strip()
    normalized_correct_focus = str(correct_focus or "").strip()

    if normalized_wrong_focus and normalized_wrong_focus not in normalized_wrong:
        normalized_wrong_focus = ""
    if normalized_correct_focus and normalized_correct_focus not in normalized_correct:
        normalized_correct_focus = ""

    return ReminderExample(
        wrong=normalized_wrong,
        correct=normalized_correct,
        wrong_focus=normalized_wrong_focus,
        correct_focus=normalized_correct_focus,
    )


def _sanitize_reminder_item(item: ReminderItem) -> tuple[ReminderItem, bool]:
    changed = False
    cleaned_examples: list[ReminderExample] = []
    seen_pairs: set[tuple[str, str]] = set()

    for example in item.examples:
        cleaned = _normalize_pattern_example(
            example.wrong,
            example.correct,
            example.wrong_focus,
            example.correct_focus,
        )
        if cleaned is None:
            changed = True
            continue

        pair_key = (cleaned.wrong.strip().lower(), cleaned.correct.strip().lower())
        if pair_key in seen_pairs:
            changed = True
            continue
        seen_pairs.add(pair_key)
        cleaned_examples.append(cleaned)
        if cleaned != example:
            changed = True

    if changed:
        item.examples = cleaned_examples[:3]

    return item, changed


def _looks_like_spelling_example(example: ReminderExample) -> bool:
    wrong_tokens = [token for token in re.split(r"\s+", example.wrong.strip()) if token]
    correct_tokens = [token for token in re.split(r"\s+", example.correct.strip()) if token]
    if len(wrong_tokens) != len(correct_tokens) or not wrong_tokens:
        return False

    mismatches = [
        (wrong_token, correct_token)
        for wrong_token, correct_token in zip(wrong_tokens, correct_tokens)
        if wrong_token.strip().lower() != correct_token.strip().lower()
    ]
    if len(mismatches) != 1:
        return False

    wrong_token, correct_token = mismatches[0]
    ratio = SequenceMatcher(None, wrong_token.lower(), correct_token.lower()).ratio()
    return ratio >= 0.65


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
    items = [ReminderItem(**item) for item in raw]
    changed = False
    seen_examples_by_language: dict[str, set[tuple[str, str]]] = {}
    for item in items:
        _, item_changed = _sanitize_reminder_item(item)
        changed = changed or item_changed
        explanation_lower = item.explanation.lower()
        if (
            item.key != "spelling"
            and (
                "spelling" in explanation_lower
                or "orthograph" in explanation_lower
            )
        ):
            item.key = "spelling"
            item.label = "Spelling"
            changed = True
        elif (
            item.key == "spelling"
            and (
                "subject" in explanation_lower
                or "verb" in explanation_lower
                or "conjug" in explanation_lower
                or "agreement" in explanation_lower
            )
        ):
            item.key = "verbs"
            item.label = "Verbs"
            changed = True
        language_key = item.language
        seen_pairs = seen_examples_by_language.setdefault(language_key, set())
        filtered_examples: list[ReminderExample] = []
        for example in item.examples:
            pair_key = (
                example.wrong.strip().lower(),
                example.correct.strip().lower(),
            )
            if pair_key in seen_pairs:
                changed = True
                continue
            seen_pairs.add(pair_key)
            filtered_examples.append(example)
        if len(filtered_examples) != len(item.examples):
            item.examples = filtered_examples[:3]
    if changed:
        REMINDERS_PATH.write_text(
            json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return [item for item in items if item.language == language]


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
                normalized_example = _normalize_pattern_example(
                    example_wrong,
                    example_correct,
                    example_wrong_focus,
                    example_correct_focus,
                )
                if normalized_example is None:
                    break
                normalized_wrong = normalized_example.wrong.strip().lower()
                normalized_correct = normalized_example.correct.strip().lower()
                item.examples = [
                    example for example in item.examples
                    if not (
                        example.wrong.strip().lower() == normalized_wrong
                        and example.correct.strip().lower() == normalized_correct
                    )
                ]
                item.examples.insert(0, normalized_example)
                item.examples = item.examples[:3]
            break
    else:
        normalized_example = _normalize_pattern_example(
            example_wrong,
            example_correct,
            example_wrong_focus,
            example_correct_focus,
        )
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
                    [normalized_example]
                    if normalized_example is not None
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
