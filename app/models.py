from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DifficultyLevel = Literal["A1", "A2", "B1", "B2", "C1"]


class VocabHint(BaseModel):
    english: str
    french: str
    note: str = ""


class LessonSentence(BaseModel):
    step: int
    english: str
    french: str
    context_note: str = ""
    vocab_hints: list[VocabHint] = Field(default_factory=list)


class LessonRequest(BaseModel):
    difficulty: DifficultyLevel = "A2"
    theme: str = "mythological adventure"
    lesson_type: Literal["story", "dialogue", "film_scene", "auto"] = "story"
    sentence_count: int = Field(default=8, ge=4, le=15)


class LessonResponse(BaseModel):
    lesson_id: str
    title: str
    difficulty: DifficultyLevel
    theme: str
    lesson_type: str
    source: Literal["openai", "fallback"]
    sentences: list[LessonSentence]


class EvaluationRequest(BaseModel):
    english: str
    target_french: str
    learner_answer: str
    difficulty: DifficultyLevel
    context_note: str = ""


class EvaluationResponse(BaseModel):
    is_correct: bool
    correctness_score: int = Field(ge=0, le=100)
    naturalness_score: int = Field(ge=0, le=100)
    accent_issues_only: bool = False
    verdict: str
    learner_normalized: str
    target_normalized: str
    suggested_french: str
    more_common_french: str
    tips: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    reminders_triggered: list[str] = Field(default_factory=list)
    encouraging_note: str = ""
    source: Literal["openai", "fallback"]


class PhraseExplainRequest(BaseModel):
    english_sentence: str
    french_sentence: str
    selected_phrase: str
    difficulty: DifficultyLevel
    vocab_hints: list[VocabHint] = Field(default_factory=list)


class PhraseExplainResponse(BaseModel):
    french_phrase: str
    english_meaning: str
    usage_note: str = ""
    save_note: str = ""
    source: Literal["openai", "fallback"]


class SaveVocabRequest(BaseModel):
    english: str
    french: str
    note: str = ""
    source_sentence: str = ""


class SavedVocabItem(BaseModel):
    english: str
    french: str
    note: str = ""
    source_sentence: str = ""


class SavedVocabResponse(BaseModel):
    items: list[SavedVocabItem]


class ReminderItem(BaseModel):
    key: str
    label: str
    explanation: str
    count: int = 0
    last_target: str = ""
    last_answer: str = ""


class ReminderResponse(BaseModel):
    items: list[ReminderItem]
