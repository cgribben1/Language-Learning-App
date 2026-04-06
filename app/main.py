from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .adventure_service import AdventureService
from .ai_service import AIService, canonicalize_reminder_category, normalize_french
from .models import AdventureActionRequest, AdventureStartRequest, AdventureStateResponse, EvaluationRequest, EvaluationResponse, LessonRequest, LessonResponse, PhraseExplainRequest, PhraseExplainResponse, ReminderResponse, SaveVocabRequest, SavedVocabResponse, StoryBrainResponse, StoryCompleteRequest, StorySuggestionRequest, StorySuggestionResponse
from .storage import load_reminders, load_story_brain, load_vocab, record_completed_story, record_reminder_hit, save_vocab_item, vocab_to_anki_csv


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="French Story Trainer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

ai_service = AIService()
adventure_service = AdventureService()

_PATTERN_FUNCTION_WORDS = {
    "french": {
        "a", "à", "de", "du", "des", "d", "en", "dans", "sur", "sous", "chez", "vers", "pour",
        "par", "avec", "sans", "entre", "avant", "apres", "après", "depuis", "le", "la", "les",
        "un", "une", "au", "aux", "de la", "de l", "ce", "cet", "cette", "ces", "je", "j",
        "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "ne", "pas", "y", "l", "m",
        "t", "s",
    },
    "spanish": {
        "a", "de", "del", "al", "en", "con", "sin", "por", "para", "sobre", "entre", "desde",
        "hasta", "el", "la", "los", "las", "un", "una", "unos", "unas", "este", "esta",
        "estos", "estas", "yo", "tu", "tú", "el", "él", "ella", "nosotros", "vosotros",
        "ellos", "ellas", "no", "se", "lo", "le", "la",
    },
}


def _pattern_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"\s+", (text or "").strip()) if token]


def _has_content_token(tokens: list[str], language: str) -> bool:
    function_words = _PATTERN_FUNCTION_WORDS.get(language, set())
    return any(normalize_french(token) not in function_words for token in tokens)


def _pattern_has_sufficient_context(wrong: str, correct: str, key: str, language: str) -> bool:
    normalized_wrong = normalize_french(wrong)
    normalized_correct = normalize_french(correct)
    if not normalized_wrong or not normalized_correct or normalized_wrong == normalized_correct:
        return False

    wrong_tokens = _pattern_tokens(wrong)
    correct_tokens = _pattern_tokens(correct)
    if not wrong_tokens or not correct_tokens:
        return False

    normalized_key = (key or "").strip().lower()
    if normalized_key in {"verbs", "agreement", "articles"}:
        return len(wrong_tokens) >= 2 and len(correct_tokens) >= 2
    if normalized_key in {"prepositions", "small_words", "pronouns", "negation"}:
        return (
            len(wrong_tokens) >= 2
            and len(correct_tokens) >= 2
            and (_has_content_token(wrong_tokens, language) or _has_content_token(correct_tokens, language))
        )
    return len(wrong_tokens) >= 2 or len(correct_tokens) >= 2


def _build_dev_version() -> str:
    tracked_paths = sorted(
        list(BASE_DIR.glob("*.py")) +
        list(STATIC_DIR.glob("*.html")) +
        list(STATIC_DIR.glob("*.css")) +
        list(STATIC_DIR.glob("*.js"))
    )
    fingerprint = "|".join(
        f"{path.name}:{path.stat().st_mtime_ns}" for path in tracked_paths if path.exists()
    )
    return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:12]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict[str, object]:
    return {
        "openai_enabled": ai_service.enabled,
        "adventure_openai_enabled": adventure_service.enabled,
        "languages": ["french", "spanish"],
        "difficulties": ["A1", "A2", "B1", "B2", "C1"],
        "lesson_types": ["story", "dialogue", "film_scene", "auto"],
    }


@app.get("/api/dev/version")
def dev_version() -> dict[str, str]:
    return {"version": _build_dev_version()}


@app.post("/api/lesson", response_model=LessonResponse)
def create_lesson(request: LessonRequest) -> LessonResponse:
    try:
        return ai_service.generate_lesson(request, str(uuid.uuid4()))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/lesson/{lesson_id}", response_model=LessonResponse)
def get_lesson(lesson_id: str) -> LessonResponse:
    try:
        return ai_service.get_lesson(lesson_id)
    except RuntimeError as exc:
        if str(exc) == "Lesson not found.":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/evaluate", response_model=EvaluationResponse)
def evaluate_answer(request: EvaluationRequest) -> EvaluationResponse:
    try:
        feedback = ai_service.evaluate_answer(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    saved_labels: list[str] = []
    reminder_key, reminder_label = canonicalize_reminder_category(
        feedback.reminder_key or feedback.reminder_label,
        feedback.reminder_label,
        feedback.reminder_explanation,
        feedback.reminder_wrong_pattern,
        feedback.reminder_correct_pattern,
        feedback.reminder_wrong_focus,
        feedback.reminder_correct_focus,
        request.language,
    )
    example_wrong = (feedback.reminder_wrong_pattern or "").strip()
    example_correct = (feedback.reminder_correct_pattern or "").strip()
    if reminder_key and reminder_label and _pattern_has_sufficient_context(example_wrong, example_correct, reminder_key, request.language):
        default_explanations = {
            "prepositions": "Watch the preposition or linking phrase here; short grammar words often change the meaning.",
            "articles": "Watch the article or determiner here; small noun markers carry important grammar.",
            "pronouns": "Watch which pronoun is used here; the reference or pronoun form changes the sentence.",
            "word_order": "Watch the order of the words here; the structure is arranged differently.",
            "verbs": "Watch the verb form here; the conjugation or verb choice changes with the subject or context.",
            "agreement": "Watch the agreement here; gender, number, or matching forms need to line up.",
            "negation": "Watch the negation here; the sentence needs the right negative structure.",
            "small_words": "Watch the small grammar words here; they are easy to miss but change the structure.",
            "spelling": "Watch the spelling here; this is a recurring orthography pattern worth noticing.",
        }
        example_wrong_focus = (feedback.reminder_wrong_focus or "").strip()
        example_correct_focus = (feedback.reminder_correct_focus or "").strip()
        if example_wrong_focus and example_wrong_focus.lower() not in example_wrong.lower():
            example_wrong_focus = ""
        if example_correct_focus and example_correct_focus.lower() not in example_correct.lower():
            example_correct_focus = ""
        saved_items = record_reminder_hit(
            language=request.language,
            key=reminder_key,
            label=reminder_label,
            explanation=(feedback.reminder_explanation or "").strip() or default_explanations.get(reminder_key, ""),
            target=request.target_sentence,
            answer=request.learner_answer,
            example_wrong=example_wrong,
            example_correct=example_correct,
            example_wrong_focus=example_wrong_focus,
            example_correct_focus=example_correct_focus,
        )
        if any(saved_item.key == reminder_key for saved_item in saved_items):
            feedback.reminder_key = reminder_key
            feedback.reminder_label = reminder_label
            feedback.reminder_wrong_pattern = example_wrong
            feedback.reminder_correct_pattern = example_correct
            feedback.reminder_wrong_focus = example_wrong_focus
            feedback.reminder_correct_focus = example_correct_focus
            saved_labels.append(reminder_label)
    else:
        feedback.reminder_key = ""
        feedback.reminder_label = ""
        feedback.reminder_explanation = ""
        feedback.reminder_wrong_pattern = ""
        feedback.reminder_correct_pattern = ""
        feedback.reminder_wrong_focus = ""
        feedback.reminder_correct_focus = ""
    feedback.reminders_triggered = saved_labels
    return feedback


@app.post("/api/explain-phrase", response_model=PhraseExplainResponse)
def explain_phrase(request: PhraseExplainRequest) -> PhraseExplainResponse:
    try:
        return ai_service.explain_phrase(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/adventure/start", response_model=AdventureStateResponse)
def start_adventure(request: AdventureStartRequest) -> AdventureStateResponse:
    return adventure_service.start_adventure(request)


@app.post("/api/adventure/action", response_model=AdventureStateResponse)
def submit_adventure_action(request: AdventureActionRequest) -> AdventureStateResponse:
    try:
        return adventure_service.submit_action(request)
    except RuntimeError as exc:
        message = str(exc)
        status_code = 404 if message == "Adventure session not found." else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.get("/api/vocab", response_model=SavedVocabResponse)
def get_vocab(language: str = Query(default="french")) -> SavedVocabResponse:
    return SavedVocabResponse(items=load_vocab(language))


@app.post("/api/vocab", response_model=SavedVocabResponse)
def add_vocab(request: SaveVocabRequest) -> SavedVocabResponse:
    return SavedVocabResponse(items=save_vocab_item(request))


@app.get("/api/reminders", response_model=ReminderResponse)
def get_reminders(language: str = Query(default="french")) -> ReminderResponse:
    return ReminderResponse(items=load_reminders(language))


@app.get("/api/story-brain", response_model=StoryBrainResponse)
def get_story_brain(language: str = Query(default="french")) -> StoryBrainResponse:
    return StoryBrainResponse(items=load_story_brain(language))


@app.post("/api/story-brain/complete", response_model=StoryBrainResponse)
def complete_story(request: StoryCompleteRequest) -> StoryBrainResponse:
    entry = ai_service.summarize_completed_story(request)
    items, _ = record_completed_story(entry)
    return StoryBrainResponse(items=[item for item in items if item.language == request.language])


@app.post("/api/story-suggestion", response_model=StorySuggestionResponse)
def suggest_story(request: StorySuggestionRequest) -> StorySuggestionResponse:
    try:
        return ai_service.suggest_story_theme(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/vocab/export")
def export_vocab(language: str = Query(default="french")) -> PlainTextResponse:
    language_label = "french" if language == "french" else "spanish"
    return PlainTextResponse(
        vocab_to_anki_csv(load_vocab(language), language),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{language_label}_story_trainer_anki.csv"'},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/adventure")
def adventure() -> FileResponse:
    return FileResponse(STATIC_DIR / "adventure.html")
