from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from html import unescape
from typing import Any

from openai import OpenAI

from .models import EvaluationRequest, EvaluationResponse, LessonRequest, LessonResponse, LessonSentence, PhraseExplainRequest, PhraseExplainResponse


def normalize_french(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("'", "").replace("’", "")
    decomposed = unicodedata.normalize("NFD", lowered)
    no_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in no_accents)
    return " ".join(cleaned.split())


def strip_html(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", text)
    return " ".join(unescape(without_tags).split())


def tokenize_french_context(text: str) -> list[str]:
    lowered = text.lower().replace("’", "'")
    lowered = re.sub(r"([a-zà-ÿ])'([a-zà-ÿ])", r"\1 \2", lowered)
    decomposed = unicodedata.normalize("NFD", lowered)
    no_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9\s']", " ", no_accents)
    return [token for token in cleaned.split() if token]


def lookup_wiktionary_french_entries(phrase: str) -> list[dict[str, Any]]:
    url = "https://en.wiktionary.org/api/rest_v1/page/definition/" + urllib.parse.quote(phrase)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    return payload.get("fr", [])


def extract_french_lemma(definition_html: str) -> str | None:
    match = re.search(r'/wiki/([^"#]+)#French', definition_html)
    if not match:
        return None
    return urllib.parse.unquote(match.group(1))


def choose_best_french_entry(entries: list[dict[str, Any]], phrase: str, sentence: str) -> dict[str, Any] | None:
    if not entries:
        return None
    if len(entries) == 1:
        return entries[0]

    tokens = tokenize_french_context(sentence)
    phrase_tokens = tokenize_french_context(phrase)
    subject_pronouns = {"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles"}
    auxiliaries = {"ai", "as", "a", "avons", "avez", "ont", "suis", "es", "est", "sommes", "etes", "êtes", "sont", "avais", "avait"}
    articles = {"le", "la", "les", "un", "une", "des", "du", "de", "d", "ce", "cet", "cette", "ces", "mon", "ton", "son", "notre", "votre", "leur"}

    start_index = None
    for index in range(len(tokens) - len(phrase_tokens) + 1):
        if tokens[index:index + len(phrase_tokens)] == phrase_tokens:
            start_index = index
            break

    prev_token = tokens[start_index - 1] if start_index is not None and start_index > 0 else ""
    next_token = tokens[start_index + len(phrase_tokens)] if start_index is not None and start_index + len(phrase_tokens) < len(tokens) else ""
    copulas = {"suis", "es", "est", "sommes", "etes", "êtes", "sont", "etais", "étais", "etait", "était"}
    location_preps = {"a", "à", "en", "dans", "chez", "sur", "sous", "devant", "derriere", "derrière", "pres", "près"}
    object_like_determiners = {"le", "la", "les", "un", "une", "des", "mon", "ton", "son", "notre", "votre", "leur", "ce", "cet", "cette", "ces"}
    scored_entries: list[tuple[int, dict[str, Any]]] = []

    for entry in entries:
        pos = entry.get("partOfSpeech", "")
        definition_html = entry.get("definitions", [{}])[0].get("definition", "")
        lemma = normalize_french(extract_french_lemma(definition_html) or "")
        score = 0

        if pos == "Verb":
            score += 3
        if pos == "Verb" and prev_token in subject_pronouns:
            score += 5
        if pos == "Participle" and prev_token in auxiliaries:
            score += 7
        if pos == "Preposition" and next_token in articles and prev_token not in subject_pronouns:
            score += 5
        if pos == "Noun" and prev_token in articles:
            score += 6
        if pos == "Adjective" and prev_token in copulas:
            score += 6
        if pos == "Verb" and next_token in object_like_determiners and prev_token in subject_pronouns:
            score += 2
        if pos == "Verb" and next_token in location_preps and prev_token in subject_pronouns:
            score += 2

        phrase_normalized = normalize_french(phrase)
        if phrase_normalized == "suis":
            if lemma == "etre" and next_token in location_preps.union({"un", "une", "des", "tres", "très"}):
                score += 6
            if lemma == "suivre" and next_token in object_like_determiners.union({"moi", "toi", "lui", "elle", "eux"}):
                score += 6
        if phrase_normalized == "entre":
            if lemma == "entrer" and prev_token in subject_pronouns:
                score += 7
            if lemma == "entre" and next_token in articles and prev_token not in subject_pronouns:
                score += 6
        if phrase_normalized == "ferme":
            if lemma == "fermer" and prev_token in subject_pronouns:
                score += 6
            if pos == "Adjective" and prev_token in copulas:
                score += 7
            if pos == "Noun" and prev_token in articles:
                score += 5
        if phrase_normalized in {"porte", "marche", "reste", "compte", "note", "sort"}:
            if pos == "Verb" and prev_token in subject_pronouns:
                score += 5
            if pos == "Noun" and prev_token in articles:
                score += 5

        scored_entries.append((score, entry))

    scored_entries.sort(key=lambda item: item[0], reverse=True)
    return scored_entries[0][1]


def lookup_wiktionary_french_definition(phrase: str, sentence: str) -> tuple[str, str] | None:
    french_entries = lookup_wiktionary_french_entries(phrase)
    if not french_entries:
        return None

    entry = choose_best_french_entry(french_entries, phrase, sentence)
    if entry is None:
        return None

    definitions = entry.get("definitions", [])
    if not definitions:
        return None

    first_definition_html = definitions[0].get("definition", "")
    first_definition = strip_html(first_definition_html)
    if not first_definition:
        return None

    part_of_speech = entry.get("partOfSpeech", "")
    lemma = extract_french_lemma(first_definition_html)

    if lemma and part_of_speech in {"Verb", "Participle"}:
        lemma_entries = lookup_wiktionary_french_entries(lemma)
        lemma_entry = choose_best_french_entry(lemma_entries, lemma, sentence)
        if lemma_entry is not None:
            lemma_definitions = lemma_entry.get("definitions", [])
            if lemma_definitions:
                lemma_meaning = strip_html(lemma_definitions[0].get("definition", ""))
                if lemma_meaning:
                    if part_of_speech == "Verb":
                        return lemma_meaning, f"Verb form of {lemma}."
                    return lemma_meaning, f"Participle form of {lemma}."

    usage_note = f"{part_of_speech}." if part_of_speech else ""
    return first_definition, usage_note


def detect_reminder_triggers(request: EvaluationRequest, feedback: EvaluationResponse) -> list[dict[str, str]]:
    learner = normalize_french(request.learner_answer)
    target = normalize_french(request.target_french)
    triggers: list[dict[str, str]] = []

    if "entre dans" in target and "entre dans" not in learner and "entre " in learner:
        triggers.append(
            {
                "key": "entrer_dans_location",
                "label": "Use 'dans' after entrer",
                "explanation": "In French, entering a place is usually phrased with 'entrer dans ...', as in 'j'entre dans un cafe'.",
            }
        )

    if not feedback.is_correct and " de " in target and " de " not in learner and " du " not in learner:
        triggers.append(
            {
                "key": "missing_small_link_word",
                "label": "Watch the small linking words",
                "explanation": "Short words like 'de', 'dans', 'a', and articles often carry the grammar. They are easy to miss but matter a lot.",
            }
        )

    unique: dict[str, dict[str, str]] = {}
    for item in triggers:
        unique[item["key"]] = item
    return list(unique.values())


class AIService:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.lesson_model = os.getenv("OPENAI_LESSON_MODEL", "gpt-5")
        self.eval_model = os.getenv("OPENAI_EVAL_MODEL", "gpt-5")

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def generate_lesson(self, request: LessonRequest, lesson_id: str) -> LessonResponse:
        if self.enabled:
            try:
                return self._generate_lesson_openai(request, lesson_id)
            except Exception:
                pass
        return self._generate_lesson_fallback(request, lesson_id)

    def evaluate_answer(self, request: EvaluationRequest) -> EvaluationResponse:
        if self.enabled:
            try:
                return self._evaluate_answer_openai(request)
            except Exception:
                pass
        return self._evaluate_answer_fallback(request)

    def explain_phrase(self, request: PhraseExplainRequest) -> PhraseExplainResponse:
        if self.enabled:
            try:
                return self._explain_phrase_openai(request)
            except Exception:
                pass
        return self._explain_phrase_fallback(request)

    def _generate_lesson_openai(self, request: LessonRequest, lesson_id: str) -> LessonResponse:
        schema = {
            "name": "lesson_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "sentences": {
                        "type": "array",
                        "minItems": request.sentence_count,
                        "maxItems": request.sentence_count,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "step": {"type": "integer"},
                                "english": {"type": "string"},
                                "french": {"type": "string"},
                                "context_note": {"type": "string"},
                                "vocab_hints": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "english": {"type": "string"},
                                            "french": {"type": "string"},
                                            "note": {"type": "string"},
                                        },
                                        "required": ["english", "french", "note"],
                                    },
                                },
                            },
                            "required": ["step", "english", "french", "context_note", "vocab_hints"],
                        },
                    },
                },
                "required": ["title", "sentences"],
            },
        }

        response = self.client.responses.create(
            model=self.lesson_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You create high-quality French learning material. "
                        "Return a sequence of connected English prompts with target French translations. "
                        "Keep the sentences tightly connected as one story or dialogue, not random unrelated lines. "
                        "Match CEFR level exactly. "
                        "Use natural modern French. "
                        "Always include proper French accents in the target French and vocab hints. "
                        "For each sentence, include only 0 to 3 useful vocab hints for unusual or blocking words."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create a {request.lesson_type} lesson at {request.difficulty} level "
                        f"with theme '{request.theme}'. "
                        f"Make exactly {request.sentence_count} sequential sentences. "
                        "The English should be the learner-facing prompt. "
                        "The French should be a natural target answer. "
                        "Prefer everyday French unless the theme requires special vocabulary."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )

        payload = json.loads(response.output_text)
        sentences = [LessonSentence(**item) for item in payload["sentences"]]
        return LessonResponse(
            lesson_id=lesson_id,
            title=payload["title"],
            difficulty=request.difficulty,
            theme=request.theme,
            lesson_type=request.lesson_type,
            source="openai",
            sentences=sentences,
        )

    def _evaluate_answer_openai(self, request: EvaluationRequest) -> EvaluationResponse:
        schema = {
            "name": "translation_feedback",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "is_correct": {"type": "boolean"},
                    "correctness_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "naturalness_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "accent_issues_only": {"type": "boolean"},
                    "verdict": {"type": "string"},
                    "suggested_french": {"type": "string"},
                    "more_common_french": {"type": "string"},
                    "tips": {"type": "array", "items": {"type": "string"}},
                    "mistakes": {"type": "array", "items": {"type": "string"}},
                    "encouraging_note": {"type": "string"},
                },
                "required": [
                    "is_correct",
                    "correctness_score",
                    "naturalness_score",
                    "accent_issues_only",
                    "verdict",
                    "suggested_french",
                    "more_common_french",
                    "tips",
                    "mistakes",
                    "encouraging_note",
                ],
            },
        }

        response = self.client.responses.create(
            model=self.eval_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise but encouraging French tutor. "
                        "Evaluate a learner's French translation of an English sentence. "
                        "Treat missing accents as acceptable if the sentence is otherwise correct, but mention them. "
                        "Accept valid paraphrases. "
                        "Be especially alert to cases where the learner's answer is understandable and correct, "
                        "but a more idiomatic or more common French wording exists. "
                        "Keep tips concise and practical."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Difficulty: {request.difficulty}\n"
                        f"English prompt: {request.english}\n"
                        f"Target French: {request.target_french}\n"
                        f"Context note: {request.context_note}\n"
                        f"Learner answer: {request.learner_answer}\n"
                        "Judge meaning, grammar, and naturalness."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )

        payload = json.loads(response.output_text)
        return EvaluationResponse(
            learner_normalized=normalize_french(request.learner_answer),
            target_normalized=normalize_french(request.target_french),
            reminders_triggered=[],
            source="openai",
            **payload,
        )

    def _explain_phrase_openai(self, request: PhraseExplainRequest) -> PhraseExplainResponse:
        schema = {
            "name": "phrase_explanation",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "english_meaning": {"type": "string"},
                    "usage_note": {"type": "string"},
                    "save_note": {"type": "string"},
                },
                "required": ["english_meaning", "usage_note", "save_note"],
            },
        }

        hint_text = "; ".join(f"{hint.french} = {hint.english}" for hint in request.vocab_hints)
        response = self.client.responses.create(
            model=self.eval_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You explain French words and short phrases for learners. "
                        "Keep explanations concise, practical, and beginner-friendly. "
                        "If the phrase is part of a larger expression, explain that clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"English sentence: {request.english_sentence}\n"
                        f"French sentence: {request.french_sentence}\n"
                        f"Selected phrase: {request.selected_phrase}\n"
                        f"Difficulty: {request.difficulty}\n"
                        f"Known hints: {hint_text}\n"
                        "Return the meaning, a short usage note, and a short flashcard note."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )
        payload = json.loads(response.output_text)
        return PhraseExplainResponse(
            french_phrase=request.selected_phrase,
            source="openai",
            **payload,
        )

    def _generate_lesson_fallback(self, request: LessonRequest, lesson_id: str) -> LessonResponse:
        fallback_lessons: dict[str, dict[str, Any]] = {
            "A1": {
                "title": "A Stranger at the Cafe",
                "sentences": [
                    {
                        "step": 1,
                        "english": "I enter a small cafe near the station.",
                        "french": "J'entre dans un petit café près de la gare.",
                        "context_note": "Simple present narration.",
                        "vocab_hints": [{"english": "station", "french": "gare", "note": "train station"}],
                    },
                    {
                        "step": 2,
                        "english": "A woman smiles and says hello to me.",
                        "french": "Une femme me sourit et me dit bonjour.",
                        "context_note": "Indirect object pronoun with a common greeting.",
                        "vocab_hints": [],
                    },
                    {
                        "step": 3,
                        "english": "I ask for a coffee and some bread.",
                        "french": "Je demande un café et du pain.",
                        "context_note": "Basic food ordering.",
                        "vocab_hints": [],
                    },
                    {
                        "step": 4,
                        "english": "She tells me that the bread is still warm.",
                        "french": "Elle me dit que le pain est encore chaud.",
                        "context_note": "Common adjective placement.",
                        "vocab_hints": [{"english": "warm", "french": "chaud", "note": "still warm"}],
                    },
                    {
                        "step": 5,
                        "english": "I sit by the window and look at the rain.",
                        "french": "Je m'assois près de la fenêtre et je regarde la pluie.",
                        "context_note": "Two linked present-tense actions.",
                        "vocab_hints": [{"english": "window", "french": "fenêtre", "note": "accent often omitted on keyboards"}],
                    },
                    {
                        "step": 6,
                        "english": "A man outside waves to the waiter.",
                        "french": "Un homme dehors fait signe au serveur.",
                        "context_note": "Natural French for waving to someone.",
                        "vocab_hints": [{"english": "waiter", "french": "serveur", "note": ""}],
                    },
                    {
                        "step": 7,
                        "english": "The woman laughs because the man is her brother.",
                        "french": "La femme rit parce que l'homme est son frère.",
                        "context_note": "Very common family vocabulary.",
                        "vocab_hints": [],
                    },
                    {
                        "step": 8,
                        "english": "Before I leave, she gives me the name of a good museum.",
                        "french": "Avant de partir, elle me donne le nom d'un bon musée.",
                        "context_note": "Infinitive after 'avant de'.",
                        "vocab_hints": [{"english": "museum", "french": "musée", "note": "accent optional for typing in this app"}],
                    },
                ],
            },
            "B1": {
                "title": "The Minotaur in the Metro",
                "sentences": [
                    {
                        "step": 1,
                        "english": "On my way home, I see a man in an old bronze mask on the metro.",
                        "french": "En rentrant chez moi, je vois un homme avec un vieux masque en bronze dans le métro.",
                        "context_note": "Natural B1 narration with a fronted phrase.",
                        "vocab_hints": [{"english": "bronze", "french": "bronze", "note": "same word in both languages"}],
                    },
                    {
                        "step": 2,
                        "english": "He tells me that he is looking for the modern entrance to the labyrinth.",
                        "french": "Il me dit qu'il cherche l'entrée moderne du labyrinthe.",
                        "context_note": "Reported speech in the present.",
                        "vocab_hints": [{"english": "labyrinth", "french": "labyrinthe", "note": ""}],
                    },
                    {
                        "step": 3,
                        "english": "At first, I think he is joking, but his voice is completely serious.",
                        "french": "Au début, je pense qu'il plaisante, mais sa voix est tout à fait sérieuse.",
                        "context_note": "Contrast with 'mais'.",
                        "vocab_hints": [],
                    },
                    {
                        "step": 4,
                        "english": "He explains that myths do not disappear; they simply change neighborhoods.",
                        "french": "Il explique que les mythes ne disparaissent pas ; ils changent simplement de quartier.",
                        "context_note": "Literary but still natural phrasing.",
                        "vocab_hints": [{"english": "neighborhood", "french": "quartier", "note": ""}],
                    },
                    {
                        "step": 5,
                        "english": "When the train stops, he asks me to follow him without asking any questions.",
                        "french": "Quand le train s'arrête, il me demande de le suivre sans poser de questions.",
                        "context_note": "Infinitive structures after 'demander de'.",
                        "vocab_hints": [],
                    },
                    {
                        "step": 6,
                        "english": "We walk through a maintenance tunnel that smells of dust and sea water.",
                        "french": "Nous traversons un tunnel de maintenance qui sent la poussière et l'eau de mer.",
                        "context_note": "Concrete sensory description.",
                        "vocab_hints": [{"english": "maintenance tunnel", "french": "tunnel de maintenance", "note": ""}],
                    },
                    {
                        "step": 7,
                        "english": "At the end, a bright vending machine stands where a sacred gate should be.",
                        "french": "Au bout, un distributeur lumineux se dresse à l'endroit où devrait se trouver une porte sacrée.",
                        "context_note": "More idiomatic than a literal word-for-word translation.",
                        "vocab_hints": [{"english": "vending machine", "french": "distributeur", "note": "often 'distributeur automatique'"}],
                    },
                    {
                        "step": 8,
                        "english": "The masked man sighs and says the gods have accepted terrible interior design.",
                        "french": "L'homme masqué soupire et dit que les dieux ont accepté un décor intérieur épouvantable.",
                        "context_note": "Humorous concluding line.",
                        "vocab_hints": [{"english": "interior design", "french": "decor interieur", "note": "more natural than a literal calque"}],
                    },
                ],
            },
        }

        selected = fallback_lessons["B1" if request.difficulty in {"B1", "B2", "C1"} else "A1"]
        sentences = [LessonSentence(**item) for item in selected["sentences"][: request.sentence_count]]
        return LessonResponse(
            lesson_id=lesson_id,
            title=selected["title"],
            difficulty=request.difficulty,
            theme=request.theme,
            lesson_type=request.lesson_type,
            source="fallback",
            sentences=sentences,
        )

    def _evaluate_answer_fallback(self, request: EvaluationRequest) -> EvaluationResponse:
        learner_normalized = normalize_french(request.learner_answer)
        target_normalized = normalize_french(request.target_french)
        exact_match = learner_normalized == target_normalized
        similarity = int(SequenceMatcher(None, learner_normalized, target_normalized).ratio() * 100)
        reminder_triggers = detect_reminder_triggers(
            request,
            EvaluationResponse(
                is_correct=False,
                correctness_score=0,
                naturalness_score=0,
                accent_issues_only=False,
                verdict="",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_french=request.target_french,
                more_common_french=request.target_french,
                tips=[],
                mistakes=[],
                reminders_triggered=[],
                encouraging_note="",
                source="fallback",
            ),
        )

        if exact_match:
            return EvaluationResponse(
                is_correct=True,
                correctness_score=100,
                naturalness_score=90,
                accent_issues_only=False,
                verdict="Correct and natural.",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_french=request.target_french,
                more_common_french=request.target_french,
                tips=["Nice work. This matches the target meaning very closely."],
                mistakes=[],
                reminders_triggered=[],
                encouraging_note="You can move on confidently.",
                source="fallback",
            )

        if reminder_triggers:
            return EvaluationResponse(
                is_correct=False,
                correctness_score=max(60, similarity - 10),
                naturalness_score=max(55, similarity - 15),
                accent_issues_only=False,
                verdict="Close, but an important grammar word is missing.",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_french=request.target_french,
                more_common_french=request.target_french,
                tips=[
                    "You are close on the main meaning.",
                    "French often needs a small linking word here: compare your answer with the suggested version carefully.",
                ],
                mistakes=[item["explanation"] for item in reminder_triggers],
                reminders_triggered=[],
                encouraging_note="This is exactly the kind of repeatable pattern the reminder list is meant to catch.",
                source="fallback",
            )

        if similarity >= 82:
            return EvaluationResponse(
                is_correct=True,
                correctness_score=88,
                naturalness_score=78,
                accent_issues_only=False,
                verdict="Probably correct, but the wording could be smoother.",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_french=request.target_french,
                more_common_french=request.target_french,
                tips=[
                    "Your answer is close in meaning.",
                    "Compare your word order with the suggested French.",
                    "If you skipped accents, that is acceptable here, but notice them for review.",
                ],
                mistakes=["Some wording is less idiomatic than the target sentence."],
                reminders_triggered=[],
                encouraging_note="This is a solid attempt. Focus on the most natural phrasing now.",
                source="fallback",
            )

        return EvaluationResponse(
            is_correct=False,
            correctness_score=max(35, similarity),
            naturalness_score=max(30, similarity - 10),
            accent_issues_only=False,
            verdict="Not quite right yet.",
            learner_normalized=learner_normalized,
            target_normalized=target_normalized,
            suggested_french=request.target_french,
            more_common_french=request.target_french,
            tips=[
                "Check the core verb and the small grammar words.",
                "Use the suggested answer as a model, then try the next sentence quickly.",
            ],
            mistakes=["The meaning or structure differs noticeably from the target sentence."],
            reminders_triggered=[],
            encouraging_note="The important part is staying in the flow and learning from the comparison.",
            source="fallback",
        )

    def _explain_phrase_fallback(self, request: PhraseExplainRequest) -> PhraseExplainResponse:
        selected_normalized = normalize_french(request.selected_phrase)
        common_phrases = {
            "pres de": {
                "english_meaning": "near / close to",
                "usage_note": "A very common phrase for location: 'près de' means 'near' or 'close to'.",
            },
            "tout a fait": {
                "english_meaning": "completely / quite",
                "usage_note": "Common intensifier meaning 'completely' or 'quite', depending on context.",
            },
            "au bout": {
                "english_meaning": "at the end",
                "usage_note": "Common location phrase meaning 'at the end'.",
            },
            "eau de mer": {
                "english_meaning": "sea water",
                "usage_note": "Fixed noun phrase meaning 'sea water'.",
            },
        }

        if selected_normalized in common_phrases:
            phrase_data = common_phrases[selected_normalized]
            return PhraseExplainResponse(
                french_phrase=request.selected_phrase,
                english_meaning=phrase_data["english_meaning"],
                usage_note=phrase_data["usage_note"],
                save_note=f"From: {request.english_sentence}",
                source="fallback",
            )

        wiktionary_result = lookup_wiktionary_french_definition(request.selected_phrase, request.french_sentence)
        if wiktionary_result is not None:
            english_meaning, usage_note = wiktionary_result
            return PhraseExplainResponse(
                french_phrase=request.selected_phrase,
                english_meaning=english_meaning,
                usage_note=usage_note,
                save_note=f"From: {request.english_sentence}",
                source="fallback",
            )

        for hint in request.vocab_hints:
            if normalize_french(hint.french) == selected_normalized:
                return PhraseExplainResponse(
                    french_phrase=request.selected_phrase,
                    english_meaning=hint.english,
                    usage_note=hint.note or "Useful vocabulary from this sentence.",
                    save_note=f"From: {request.english_sentence}",
                    source="fallback",
                )

        phrase = request.selected_phrase.strip()
        return PhraseExplainResponse(
            french_phrase=phrase,
            english_meaning=f"Meaning of '{phrase}' in this sentence",
            usage_note="No custom hint was available, so treat this as a sentence-specific lookup target.",
            save_note=f"From: {request.english_sentence}",
            source="fallback",
        )
