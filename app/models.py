from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


DifficultyLevel = Literal["A1", "A2", "B1", "B2", "C1"]
LanguageCode = Literal["french", "spanish"]


class VocabHint(BaseModel):
    english: str
    french: str
    display_french: str = ""
    note: str = ""


class LessonSentence(BaseModel):
    step: int
    english: str
    french: str
    context_note: str = ""
    vocab_hints: list[VocabHint] = Field(default_factory=list)


class LessonRequest(BaseModel):
    language: LanguageCode = "french"
    difficulty: DifficultyLevel = "A2"
    theme: str = "mythological adventure"
    lesson_type: Literal["story", "dialogue", "film_scene", "auto"] = "story"
    sentence_count: int = Field(default=8, ge=4, le=15)


class LessonResponse(BaseModel):
    lesson_id: str
    language: LanguageCode = "french"
    title: str
    difficulty: DifficultyLevel
    theme: str
    lesson_type: str
    source: Literal["openai"]
    requested_sentence_count: int
    available_sentence_count: int
    is_complete: bool
    status: Literal["generating", "ready", "failed"] = "ready"
    error_message: str = ""
    sentences: list[LessonSentence]


class EvaluationRequest(BaseModel):
    language: LanguageCode = "french"
    english: str
    target_sentence: str = Field(validation_alias=AliasChoices("target_sentence", "target_french"))
    learner_answer: str
    difficulty: DifficultyLevel
    context_note: str = ""
    vocab_hints: list[VocabHint] = Field(default_factory=list)


class EvaluationResponse(BaseModel):
    is_correct: bool
    correctness_score: int = Field(ge=0, le=100)
    naturalness_score: int = Field(ge=0, le=100)
    verdict: str
    learner_normalized: str
    target_normalized: str
    accepted_learner_sentence: str = Field(default="", validation_alias=AliasChoices("accepted_learner_sentence", "accepted_learner_french"))
    suggested_sentence: str = Field(validation_alias=AliasChoices("suggested_sentence", "suggested_french"))
    more_common_sentence: str = Field(validation_alias=AliasChoices("more_common_sentence", "more_common_french"))
    tips: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    learner_token_labels: list[Literal["correct", "acceptable", "wrong"]] = Field(default_factory=list)
    reminders_triggered: list[str] = Field(default_factory=list)
    encouraging_note: str = ""
    source: Literal["openai"]


class PhraseExplainRequest(BaseModel):
    language: LanguageCode = "french"
    english_sentence: str
    target_sentence: str = Field(validation_alias=AliasChoices("target_sentence", "french_sentence"))
    selected_text: str = Field(validation_alias=AliasChoices("selected_text", "selected_phrase"))
    difficulty: DifficultyLevel
    vocab_hints: list[VocabHint] = Field(default_factory=list)


class PhraseExplainResponse(BaseModel):
    language: LanguageCode = "french"
    selected_text: str = Field(validation_alias=AliasChoices("selected_text", "french_phrase"))
    english_meaning: str
    usage_note: str = ""
    save_note: str = ""
    source: Literal["dictionary"]


class SaveVocabRequest(BaseModel):
    language: LanguageCode = "french"
    english: str
    french: str
    note: str = ""
    source_sentence: str = ""


class SavedVocabItem(BaseModel):
    language: LanguageCode = "french"
    english: str
    french: str
    note: str = ""
    source_sentence: str = ""


class SavedVocabResponse(BaseModel):
    items: list[SavedVocabItem]


class ReminderItem(BaseModel):
    language: LanguageCode = "french"
    key: str
    label: str
    explanation: str
    count: int = 0
    last_target: str = ""
    last_answer: str = ""


class ReminderResponse(BaseModel):
    items: list[ReminderItem]


class AdventureStartRequest(BaseModel):
    difficulty: DifficultyLevel = "A2"
    theme: str = "lost festival lanterns"
    setting: str = "rainy seaside town"
    player_name: str = "Camille"


class AdventureActionRequest(BaseModel):
    session_id: str
    learner_french: str


class AdventureCharacter(BaseModel):
    name: str
    role: str
    mood: str = ""
    note: str = ""


class AdventureTask(BaseModel):
    title: str
    description: str
    status: Literal["active", "complete"] = "active"


class AdventureScene(BaseModel):
    location_name: str
    location_description: str
    visual_motif: str
    ambience: str
    objective: str
    player_prompt: str
    npc_name: str
    npc_role: str
    npc_message_french: str
    npc_message_english: str = ""


class AdventureFeedback(BaseModel):
    accepted: bool
    score: int = Field(ge=0, le=100)
    correction_french: str
    teacher_note: str
    encouragement: str = ""


class AdventureStateResponse(BaseModel):
    session_id: str
    title: str
    difficulty: DifficultyLevel
    theme: str
    setting: str
    turn: int
    source: Literal["openai", "fallback"]
    scene: AdventureScene
    characters: list[AdventureCharacter] = Field(default_factory=list)
    tasks: list[AdventureTask] = Field(default_factory=list)
    inventory: list[str] = Field(default_factory=list)
    transcript: list[str] = Field(default_factory=list)
    brain_markdown: str = ""
    feedback: AdventureFeedback | None = None
