from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .adventure_service import AdventureService
from .ai_service import AIService, build_reminder_example, detect_reminder_triggers
from .models import AdventureActionRequest, AdventureStartRequest, AdventureStateResponse, EvaluationRequest, EvaluationResponse, LessonRequest, LessonResponse, PhraseExplainRequest, PhraseExplainResponse, ReminderResponse, SaveVocabRequest, SavedVocabResponse, StoryBrainResponse, StoryCompleteRequest
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
    triggered = detect_reminder_triggers(request, feedback)
    for item in triggered:
        example_wrong = (feedback.reminder_wrong_pattern or "").strip()
        example_correct = (feedback.reminder_correct_pattern or "").strip()
        if not example_wrong or not example_correct:
            example_wrong, example_correct = build_reminder_example(
                request.learner_answer,
                request.target_sentence,
                item["key"],
                request.language,
            )
        example_wrong_focus = (feedback.reminder_wrong_focus or "").strip()
        example_correct_focus = (feedback.reminder_correct_focus or "").strip()
        if example_wrong_focus and example_wrong_focus.lower() not in example_wrong.lower():
            example_wrong_focus = ""
        if example_correct_focus and example_correct_focus.lower() not in example_correct.lower():
            example_correct_focus = ""
        if not example_wrong_focus:
            example_wrong_focus = example_wrong
        if not example_correct_focus:
            example_correct_focus = example_correct
        record_reminder_hit(
            language=request.language,
            key=item["key"],
            label=item["label"],
            explanation=item["explanation"],
            target=request.target_sentence,
            answer=request.learner_answer,
            example_wrong=example_wrong,
            example_correct=example_correct,
            example_wrong_focus=example_wrong_focus,
            example_correct_focus=example_correct_focus,
        )
    feedback.reminders_triggered = [item["label"] for item in triggered]
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
