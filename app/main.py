from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .ai_service import AIService, detect_reminder_triggers
from .models import EvaluationRequest, EvaluationResponse, LessonRequest, LessonResponse, PhraseExplainRequest, PhraseExplainResponse, ReminderResponse, SaveVocabRequest, SavedVocabResponse
from .storage import load_reminders, load_vocab, record_reminder_hit, save_vocab_item, vocab_to_anki_csv


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict[str, object]:
    return {
        "openai_enabled": ai_service.enabled,
        "difficulties": ["A1", "A2", "B1", "B2", "C1"],
        "lesson_types": ["story", "dialogue", "film_scene", "auto"],
    }


@app.post("/api/lesson", response_model=LessonResponse)
def create_lesson(request: LessonRequest) -> LessonResponse:
    return ai_service.generate_lesson(request, str(uuid.uuid4()))


@app.post("/api/evaluate", response_model=EvaluationResponse)
def evaluate_answer(request: EvaluationRequest) -> EvaluationResponse:
    feedback = ai_service.evaluate_answer(request)
    triggered = detect_reminder_triggers(request, feedback)
    for item in triggered:
        record_reminder_hit(
            key=item["key"],
            label=item["label"],
            explanation=item["explanation"],
            target=request.target_french,
            answer=request.learner_answer,
        )
    feedback.reminders_triggered = [item["label"] for item in triggered]
    return feedback


@app.post("/api/explain-phrase", response_model=PhraseExplainResponse)
def explain_phrase(request: PhraseExplainRequest) -> PhraseExplainResponse:
    return ai_service.explain_phrase(request)


@app.get("/api/vocab", response_model=SavedVocabResponse)
def get_vocab() -> SavedVocabResponse:
    return SavedVocabResponse(items=load_vocab())


@app.post("/api/vocab", response_model=SavedVocabResponse)
def add_vocab(request: SaveVocabRequest) -> SavedVocabResponse:
    return SavedVocabResponse(items=save_vocab_item(request))


@app.get("/api/reminders", response_model=ReminderResponse)
def get_reminders() -> ReminderResponse:
    return ReminderResponse(items=load_reminders())


@app.get("/api/vocab/export")
def export_vocab() -> PlainTextResponse:
    return PlainTextResponse(
        vocab_to_anki_csv(load_vocab()),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="french_story_trainer_anki.csv"'},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
