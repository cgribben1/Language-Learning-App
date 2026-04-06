from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, UTC
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from collections import Counter
from difflib import SequenceMatcher
from html import unescape
from threading import Lock
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, BadRequestError, OpenAI, RateLimitError

from .models import EvaluationRequest, EvaluationResponse, LessonRequest, LessonResponse, LessonSentence, PhraseExplainRequest, PhraseExplainResponse, StoryCompleteRequest, StoryMemoryEntry, StorySuggestionRequest, StorySuggestionResponse, VocabHint
from .storage import build_story_memory_guidance, load_phrase_dictionary

try:
    import winreg
except ImportError:
    winreg = None


def _normalize_orthography_base(text: str) -> str:
    lowered = unicodedata.normalize("NFKC", (text or "").casefold().strip())
    for mark in ("'", "’", "‘", "`", "´", "ʼ", "ʹ", "ʾ", "â€™", "Ã¢â‚¬â„¢"):
        lowered = lowered.replace(mark, "")
    return lowered


def normalize_french(text: str) -> str:
    lowered = _normalize_orthography_base(text)
    lowered = lowered.replace("'", "").replace("’", "")
    decomposed = unicodedata.normalize("NFD", lowered)
    no_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in no_accents)
    return " ".join(cleaned.split())


def load_openai_api_key() -> str | None:
    env_value = os.getenv("OPENAI_API_KEY")
    if env_value:
        return env_value

    if os.name == "nt" and winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                stored_value, _ = winreg.QueryValueEx(key, "OPENAI_API_KEY")
                if stored_value:
                    return stored_value
        except OSError:
            return None

    return None


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


def normalize_french_keep_accents(text: str) -> str:
    lowered = text.lower().strip().replace("â€™", "'")
    lowered = lowered.replace("'", "")
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return " ".join(cleaned.split())


def polish_learner_french(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    if not re.search(r"[.!?…]$", cleaned):
        cleaned += "."
    return cleaned


FRENCH_FUNCTION_WORDS = {
    "je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "m", "t", "s", "le", "la", "les", "l", "un", "une", "des",
    "du", "de", "d", "au", "aux", "ce", "cet", "cette", "ces", "mon", "ton", "son",
    "notre", "votre", "leur", "mes", "tes", "ses", "nos", "vos", "leurs", "y", "en",
    "ne", "n", "pas", "plus", "jamais", "rien", "personne", "que", "qui", "quoi",
    "dont", "ou", "où", "a", "à", "dans", "sur", "sous", "chez", "pour", "par",
    "avec", "sans", "vers", "entre", "avant", "apres", "après", "pendant", "depuis",
    "comme", "mais", "et", "ou", "donc", "car", "ni", "si", "quand", "lorsque",
    "parce", "que", "afin", "est", "suis", "es", "sommes", "etes", "êtes", "sont",
    "ai", "as", "a", "avons", "avez", "ont", "vais", "vas", "va", "allons", "allez",
    "vont", "se", "sa", "son", "c", "ca", "ça",
}

SPANISH_FUNCTION_WORDS = {
    "yo", "tu", "tú", "el", "él", "ella", "usted", "nosotros", "nosotras", "vosotros", "vosotras",
    "ustedes", "ellos", "ellas", "me", "te", "se", "nos", "os", "lo", "la", "los", "las", "le", "les",
    "un", "una", "unos", "unas", "el", "la", "los", "las", "del", "al", "de", "a", "en", "con", "sin",
    "por", "para", "sobre", "bajo", "entre", "antes", "despues", "después", "durante", "desde", "hasta",
    "y", "o", "u", "pero", "porque", "que", "como", "cuando", "mientras", "si", "ya", "todavia", "todavía",
    "hay", "es", "son", "soy", "eres", "somos", "sois", "estoy", "estas", "estás", "esta", "está", "estan",
    "están", "estamos", "voy", "vas", "va", "vamos", "vais", "van", "tengo", "tienes", "tiene", "tenemos",
    "tienen", "hago", "haces", "hace", "hacen",
}

LANGUAGE_NAMES = {
    "french": "French",
    "spanish": "Spanish",
}

FRENCH_ARTICLES = {"un", "une", "des", "le", "la", "les", "du", "de", "de la", "de l", "au", "aux", "ce", "cet", "cette", "ces"}
SPANISH_ARTICLES = {"un", "una", "unos", "unas", "el", "la", "los", "las", "del", "al", "este", "esta", "estos", "estas"}
FRENCH_PREPOSITIONS = {"a", "à", "de", "dans", "en", "sur", "sous", "chez", "pour", "par", "avec", "sans", "vers", "entre", "avant", "apres", "après", "depuis"}
SPANISH_PREPOSITIONS = {"a", "de", "en", "con", "sin", "por", "para", "sobre", "entre", "desde", "hasta"}
FRENCH_PRONOUNS = {"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "me", "te", "se", "le", "la", "les", "lui", "leur", "y", "en"}
SPANISH_PRONOUNS = {"yo", "tu", "tú", "el", "él", "ella", "nosotros", "nosotras", "vosotros", "vosotras", "ellos", "ellas", "me", "te", "se", "lo", "la", "los", "las", "le", "les", "nos", "os"}
FRENCH_NEGATION = {"ne", "n", "pas", "plus", "jamais", "rien", "personne"}
SPANISH_NEGATION = {"no", "nunca", "jamás", "nadie", "nada"}
FRENCH_SUBJECTS = {"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "ce", "cela", "ça", "ca"}
SPANISH_SUBJECTS = {"yo", "tu", "tú", "el", "él", "ella", "usted", "nosotros", "nosotras", "vosotros", "vosotras", "ustedes", "ellos", "ellas", "esto", "eso"}


def counter_overlap(reference_tokens: list[str], candidate_tokens: list[str]) -> tuple[int, int]:
    reference_counts = Counter(reference_tokens)
    candidate_counts = Counter(candidate_tokens)
    matched = sum(min(count, candidate_counts[token]) for token, count in reference_counts.items())
    return matched, sum(reference_counts.values())


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
    target = normalize_french(request.target_sentence)
    dynamic_key, dynamic_label = canonicalize_reminder_category(
        feedback.reminder_key or feedback.reminder_label,
        feedback.reminder_label,
        feedback.reminder_explanation,
        feedback.reminder_wrong_pattern,
        feedback.reminder_correct_pattern,
        feedback.reminder_wrong_focus,
        feedback.reminder_correct_focus,
        request.language,
    )
    default_explanations = {
        "prepositions": "Watch the preposition or linking phrase here; short grammar words often change the meaning.",
        "articles": "Watch the article or determiner here; small noun markers carry important grammar.",
        "pronouns": "Watch which pronoun is used here; the reference or pronoun form changes the sentence.",
        "word_order": "Watch the order of the words here; the French structure is arranged differently.",
        "verbs": "Watch the verb form here; the conjugation or verb choice changes with the subject or context.",
        "agreement": "Watch the agreement here; gender, number, or matching forms need to line up.",
        "negation": "Watch the negation here; the sentence needs the right negative structure.",
        "small_words": "Watch the small grammar words here; they are easy to miss but change the structure.",
        "spelling": "Watch the spelling here; this is a recurring orthography pattern worth noticing.",
    }
    dynamic_explanation = (feedback.reminder_explanation or "").strip() or default_explanations.get(dynamic_key, "")
    if not feedback.is_correct and dynamic_key and dynamic_label:
        return [{
            "key": dynamic_key,
            "label": dynamic_label,
            "explanation": dynamic_explanation,
        }]

    triggers: list[dict[str, str]] = []

    if request.language == "spanish":
        if "entra en" in target and "entra en" not in learner and "entra " in learner:
            triggers.append(
                {
                    "key": "prepositions",
                    "label": "Prepositions",
                    "explanation": "In Spanish, entering a place is often phrased with 'entrar en ...', as in 'entro en un café'.",
                }
            )

        if not feedback.is_correct and " de " in target and " de " not in learner and " del " not in learner:
            triggers.append(
                {
                    "key": "prepositions",
                    "label": "Prepositions",
                    "explanation": "Short words like 'de', 'en', 'a', and articles often carry the grammar. They are easy to miss but matter a lot.",
                }
            )
    else:
        if "entre dans" in target and "entre dans" not in learner and "entre " in learner:
            triggers.append(
                {
                    "key": "prepositions",
                    "label": "Prepositions",
                    "explanation": "In French, entering a place is usually phrased with 'entrer dans ...', as in 'j'entre dans un cafe'.",
                }
            )

        if not feedback.is_correct and " de " in target and " de " not in learner and " du " not in learner:
            triggers.append(
                {
                    "key": "prepositions",
                    "label": "Prepositions",
                    "explanation": "Short words like 'de', 'dans', 'a', and articles often carry the grammar. They are easy to miss but matter a lot.",
                }
            )

    function_swap = find_single_function_word_swap(request.learner_answer, request.target_sentence, request.language)
    if function_swap:
        learner_norm, target_norm, _, _ = function_swap
        prepositions = SPANISH_PREPOSITIONS if request.language == "spanish" else FRENCH_PREPOSITIONS
        if learner_norm in prepositions and target_norm in prepositions:
            triggers.append(
                {
                    "key": "prepositions",
                    "label": "Prepositions",
                    "explanation": "Watch the preposition here; the target uses a different location or linking word.",
                }
            )

    unique: dict[str, dict[str, str]] = {}
    for item in triggers:
        unique[item["key"]] = item
    return list(unique.values())


def normalize_reminder_key(value: str) -> str:
    text = normalize_french(value or "")
    if not text:
        return ""
    key = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return key[:64]


def find_single_function_word_swap(
    learner_answer: str,
    target_sentence: str,
    language: str = "french",
) -> tuple[str, str, str, str] | None:
    learner_tokens = [part for part in re.split(r"\s+", learner_answer.strip()) if part]
    target_tokens = [part for part in re.split(r"\s+", target_sentence.strip()) if part]
    if len(learner_tokens) != len(target_tokens):
        return None

    function_words = SPANISH_FUNCTION_WORDS if language == "spanish" else FRENCH_FUNCTION_WORDS
    mismatches: list[tuple[str, str, str, str]] = []
    for learner_raw, target_raw in zip(learner_tokens, target_tokens):
        learner_norm = normalize_french(learner_raw)
        target_norm = normalize_french(target_raw)
        if learner_norm and target_norm and learner_norm != target_norm:
            mismatches.append((learner_norm, target_norm, learner_raw, target_raw))

    if len(mismatches) != 1:
        return None

    learner_norm, target_norm, learner_raw, target_raw = mismatches[0]
    if learner_norm in function_words and target_norm in function_words:
        return learner_norm, target_norm, learner_raw, target_raw
    return None


def find_single_aligned_token_swap(
    learner_answer: str,
    target_sentence: str,
) -> tuple[str, str, str, str] | None:
    learner_tokens = [part for part in re.split(r"\s+", learner_answer.strip()) if part]
    target_tokens = [part for part in re.split(r"\s+", target_sentence.strip()) if part]
    if len(learner_tokens) != len(target_tokens):
        return None

    mismatches: list[tuple[str, str, str, str]] = []
    for learner_raw, target_raw in zip(learner_tokens, target_tokens):
        learner_norm = normalize_french(learner_raw)
        target_norm = normalize_french(target_raw)
        if learner_norm and target_norm and learner_norm != target_norm:
            mismatches.append((learner_raw, learner_norm, target_raw, target_norm))

    if len(mismatches) == 1:
        return mismatches[0]
    return None


def canonicalize_reminder_category(
    key_or_label: str,
    label: str = "",
    explanation: str = "",
    wrong_pattern: str = "",
    correct_pattern: str = "",
    wrong_focus: str = "",
    correct_focus: str = "",
    language: str = "french",
) -> tuple[str, str]:
    combined_without_key = " ".join(
        part for part in (
            normalize_french(label),
            normalize_french(explanation),
            normalize_french(wrong_pattern),
            normalize_french(correct_pattern),
            normalize_french(wrong_focus),
            normalize_french(correct_focus),
        )
        if part
    )
    combined = " ".join(
        part for part in (
            combined_without_key,
            normalize_reminder_key(key_or_label),
        )
        if part
    )

    category_rules = [
        (("spelling", "orthograph", "misspell", "misspelling", "typo", "cedilla", "accent"), ("spelling", "Spelling")),
        (("preposition", "dans", " en ", "entrer", "entrar", "vers ", "chez ", "pour ", "con ", "sin ", "para ", "sobre "), ("prepositions", "Prepositions")),
        (("article", "determiner", "determiners", "un ", "une ", " le ", " la ", " les ", " du ", " una ", " el ", " los ", " las "), ("articles", "Articles")),
        (("pronoun", "object_pronoun", "clitic", " lui ", " leur ", " lo ", " le ", " la ", " les ", " y ", " en "), ("pronouns", "Pronouns")),
        (("word_order", "literal", "order"), ("word_order", "Word order")),
        (("verb", "conjug", "tense", "etre", "ser", "estar", "va", "vais"), ("verbs", "Verbs")),
        (("agreement", "gender", "number", "plural", "singular", "masculine", "feminine"), ("agreement", "Agreement")),
        (("negation", "ne_pas", "no ", " ne ", " pas ", " nunca ", " jamás ", " jamas "), ("negation", "Negation")),
        (("linking", "small_link_word", "function_word"), ("small_words", "Small words")),
    ]

    for needles, category in category_rules:
        if any(needle in combined_without_key for needle in needles):
            return category

    for needles, category in category_rules:
        if any(needle in combined for needle in needles):
            return category

    normalized_key = normalize_reminder_key(key_or_label or label)
    if normalized_key:
        return normalized_key, (label or normalized_key.replace("_", " ").title())
    return "", ""


def build_reminder_example(answer: str, target: str, category_key: str = "", language: str = "french") -> tuple[str, str]:
    answer_tokens = [token for token in re.split(r"\s+", (answer or "").strip()) if token]
    target_tokens = [token for token in re.split(r"\s+", (target or "").strip()) if token]
    if not answer_tokens or not target_tokens:
        return answer.strip(), target.strip()

    normalized_answer = [normalize_french(token) for token in answer_tokens]
    normalized_target = [normalize_french(token) for token in target_tokens]
    matcher = SequenceMatcher(None, normalized_answer, normalized_target)
    changed_pairs: list[dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed_pairs.append(
            {
                "tag": tag,
                "i1": i1,
                "i2": i2,
                "j1": j1,
                "j2": j2,
                "wrong_tokens": answer_tokens[i1:i2],
                "correct_tokens": target_tokens[j1:j2],
            }
        )

    if not changed_pairs:
        return answer.strip(), target.strip()

    articles = SPANISH_ARTICLES if language == "spanish" else FRENCH_ARTICLES
    prepositions = SPANISH_PREPOSITIONS if language == "spanish" else FRENCH_PREPOSITIONS
    pronouns = SPANISH_PRONOUNS if language == "spanish" else FRENCH_PRONOUNS
    negation = SPANISH_NEGATION if language == "spanish" else FRENCH_NEGATION
    subjects = SPANISH_SUBJECTS if language == "spanish" else FRENCH_SUBJECTS

    def shared_previous_token(pair: dict[str, Any]) -> tuple[str, str]:
        if pair["i1"] > 0 and pair["j1"] > 0:
            prev_wrong = answer_tokens[pair["i1"] - 1].strip()
            prev_correct = target_tokens[pair["j1"] - 1].strip()
            if normalize_french(prev_wrong) == normalize_french(prev_correct):
                return prev_wrong, prev_correct
        return "", ""

    def shared_next_token(pair: dict[str, Any]) -> tuple[str, str]:
        if pair["i2"] < len(answer_tokens) and pair["j2"] < len(target_tokens):
            next_wrong = answer_tokens[pair["i2"]].strip()
            next_correct = target_tokens[pair["j2"]].strip()
            if normalize_french(next_wrong) == normalize_french(next_correct):
                return next_wrong, next_correct
        return "", ""

    def pick_matching_pair(vocabulary: set[str]) -> tuple[str, str] | None:
        for pair in changed_pairs:
            wrong_tokens = pair["wrong_tokens"]
            correct_tokens = pair["correct_tokens"]
            wrong_hits = [token for token in wrong_tokens if normalize_french(token) in vocabulary]
            correct_hits = [token for token in correct_tokens if normalize_french(token) in vocabulary]
            if wrong_hits and correct_hits:
                return " ".join(wrong_hits).strip(), " ".join(correct_hits).strip()
            if wrong_hits:
                return " ".join(wrong_hits).strip(), " ".join(correct_tokens).strip()
            if correct_hits:
                wrong_side = " ".join(wrong_tokens).strip()
                correct_side = " ".join(correct_hits).strip()
                if not wrong_side and pair["i1"] > 0 and pair["j1"] > 0:
                    anchor_wrong = answer_tokens[pair["i1"] - 1]
                    anchor_correct = target_tokens[pair["j1"] - 1]
                    wrong_side = anchor_wrong
                    correct_side = f"{anchor_correct} {correct_side}".strip()
                return wrong_side, correct_side
        return None

    def expand_pair_with_context(
        pair: dict[str, Any],
        wrong_side: str,
        correct_side: str,
        *,
        prefer_next: bool = True,
    ) -> tuple[str, str]:
        wrong_parts = [part for part in wrong_side.split() if part]
        correct_parts = [part for part in correct_side.split() if part]

        prev_wrong, prev_correct = shared_previous_token(pair)
        next_wrong, next_correct = shared_next_token(pair)

        if prefer_next and next_wrong and next_correct:
            wrong_parts.append(next_wrong)
            correct_parts.append(next_correct)

        if (len(wrong_parts) <= 1 or len(correct_parts) <= 1) and prev_wrong and prev_correct:
            wrong_parts.insert(0, prev_wrong)
            correct_parts.insert(0, prev_correct)

        if (len(wrong_parts) <= 1 or len(correct_parts) <= 1) and next_wrong and next_correct and not prefer_next:
            wrong_parts.append(next_wrong)
            correct_parts.append(next_correct)

        if len(wrong_parts) <= 1 and pair["i2"] < len(answer_tokens):
            wrong_parts.append(answer_tokens[pair["i2"]].strip())
        if len(correct_parts) <= 1 and pair["j2"] < len(target_tokens):
            correct_parts.append(target_tokens[pair["j2"]].strip())

        wrong_result = " ".join(wrong_parts).strip()
        correct_result = " ".join(correct_parts).strip()
        return wrong_result or wrong_side, correct_result or correct_side

    def expand_with_subject_context(pair: dict[str, Any]) -> tuple[str, str] | None:
        prev_wrong, prev_correct = shared_previous_token(pair)
        if not prev_wrong or normalize_french(prev_wrong) not in subjects:
            return None

        wrong_parts = [prev_wrong] + [token.strip() for token in pair["wrong_tokens"] if token.strip()]
        correct_parts = [prev_correct] + [token.strip() for token in pair["correct_tokens"] if token.strip()]

        next_wrong, next_correct = shared_next_token(pair)
        if next_wrong and next_correct:
            wrong_parts.append(next_wrong)
            correct_parts.append(next_correct)

        wrong_side = " ".join(wrong_parts).strip()
        correct_side = " ".join(correct_parts).strip()
        if wrong_side and correct_side:
            return wrong_side, correct_side
        return None

    category_key = normalize_reminder_key(category_key)
    if category_key == "articles":
        pair = pick_matching_pair(articles)
        if pair:
            wrong_side, correct_side = pair
            for changed_pair in changed_pairs:
                prev_wrong, prev_correct = shared_previous_token(changed_pair)
                next_wrong, next_correct = shared_next_token(changed_pair)
                wrong_hits = [token for token in changed_pair["wrong_tokens"] if normalize_french(token) in articles]
                correct_hits = [token for token in changed_pair["correct_tokens"] if normalize_french(token) in articles]
                if wrong_hits or correct_hits:
                    if next_wrong and next_correct:
                        return f"{wrong_side} {next_wrong}".strip(), f"{correct_side} {next_correct}".strip()
                    return wrong_side, correct_side
            return wrong_side, correct_side
    if category_key == "prepositions":
        pair = pick_matching_pair(prepositions)
        if pair:
            wrong_side, correct_side = pair
            for changed_pair in changed_pairs:
                wrong_hits = [token for token in changed_pair["wrong_tokens"] if normalize_french(token) in prepositions]
                correct_hits = [token for token in changed_pair["correct_tokens"] if normalize_french(token) in prepositions]
                if wrong_hits or correct_hits:
                    if len(changed_pair["wrong_tokens"]) > len(wrong_hits) and len(changed_pair["correct_tokens"]) > len(correct_hits):
                        wrong_tail = changed_pair["wrong_tokens"][len(wrong_hits):]
                        correct_tail = changed_pair["correct_tokens"][len(correct_hits):]
                        if wrong_tail and correct_tail:
                            return (
                                f"{wrong_side} {' '.join(wrong_tail)}".strip(),
                                f"{correct_side} {' '.join(correct_tail)}".strip(),
                            )
                    return expand_pair_with_context(
                        changed_pair,
                        wrong_side,
                        correct_side,
                        prefer_next=True,
                    )
            return wrong_side, correct_side
    if category_key == "pronouns":
        pair = pick_matching_pair(pronouns)
        if pair:
            return pair
    if category_key == "negation":
        pair = pick_matching_pair(negation)
        if pair:
            return pair
    if category_key == "small_words":
        pair = pick_matching_pair(articles | prepositions | pronouns | negation)
        if pair:
            wrong_side, correct_side = pair
            for changed_pair in changed_pairs:
                wrong_hits = [
                    token for token in changed_pair["wrong_tokens"]
                    if normalize_french(token) in (articles | prepositions | pronouns | negation)
                ]
                correct_hits = [
                    token for token in changed_pair["correct_tokens"]
                    if normalize_french(token) in (articles | prepositions | pronouns | negation)
                ]
                if wrong_hits or correct_hits:
                    if len(changed_pair["wrong_tokens"]) > len(wrong_hits) and len(changed_pair["correct_tokens"]) > len(correct_hits):
                        wrong_tail = changed_pair["wrong_tokens"][len(wrong_hits):]
                        correct_tail = changed_pair["correct_tokens"][len(correct_hits):]
                        if wrong_tail and correct_tail:
                            return (
                                f"{wrong_side} {' '.join(wrong_tail)}".strip(),
                                f"{correct_side} {' '.join(correct_tail)}".strip(),
                            )
                    return expand_pair_with_context(
                        changed_pair,
                        wrong_side,
                        correct_side,
                        prefer_next=True,
                    )
            return wrong_side, correct_side
    if category_key == "verbs":
        for pair in changed_pairs:
            wrong_tokens = pair["wrong_tokens"]
            correct_tokens = pair["correct_tokens"]
            if not wrong_tokens and not correct_tokens:
                continue
            expanded = expand_with_subject_context(pair)
            if expanded:
                return expanded
            if wrong_tokens and correct_tokens:
                return expand_pair_with_context(
                    pair,
                    " ".join(wrong_tokens).strip(),
                    " ".join(correct_tokens).strip(),
                    prefer_next=False,
                )
            expanded = expand_with_subject_context(pair)
            if expanded:
                return expanded

    if category_key == "agreement":
        for pair in changed_pairs:
            expanded = expand_with_subject_context(pair)
            if expanded:
                return expanded

    pair = min(
        changed_pairs,
        key=lambda item: max(len(" ".join(item["wrong_tokens"]).strip()), len(" ".join(item["correct_tokens"]).strip())),
    )
    wrong_tokens = pair["wrong_tokens"]
    correct_tokens = pair["correct_tokens"]
    wrong = " ".join(wrong_tokens).strip() or " ".join(answer_tokens).strip()
    correct = " ".join(correct_tokens).strip() or " ".join(target_tokens).strip()
    return wrong, correct


def localize_reminder_wording(text: str, language: str = "french") -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    replacements_by_language = {
        "french": {
            "be": "être",
        },
        "spanish": {
            "be": "ser/estar",
        },
    }

    replacements = replacements_by_language.get(language, {})
    for english_term, target_term in replacements.items():
        cleaned = re.sub(rf"\b{re.escape(english_term)}\b", target_term, cleaned, flags=re.IGNORECASE)
    return cleaned


def is_accent_feedback(text: str) -> bool:
    normalized = normalize_french(text)
    return any(
        phrase in normalized
        for phrase in (
            "accent",
            "accents",
            "diacritic",
            "diacritics",
            "acute accent",
            "grave accent",
            "circumflex",
            "cedilla",
            "trema",
            "diaeresis",
        )
    )


def is_capitalization_feedback(text: str) -> bool:
    normalized = normalize_french(text)
    return any(
        phrase in normalized
        for phrase in (
            "capitalization",
            "capitalisation",
            "missing capitalization",
            "missing capitalisation",
            "capital letter",
            "capitalize",
            "capitalise",
            "capitalized",
            "capitalised",
            "uppercase",
            "lowercase",
            "majuscule",
            "capitals",
            "proper noun",
            "sentence starts",
        )
    )


def is_punctuation_feedback(text: str) -> bool:
    normalized = normalize_french(text)
    return any(
        phrase in normalized
        for phrase in (
            "punctuation",
            "apostrophe",
            "apostrophes",
            "quote mark",
            "quote marks",
            "quotation mark",
            "quotation marks",
            "comma",
            "period",
            "full stop",
            "question mark",
            "exclamation mark",
            "hyphen",
        )
    )


def is_orthography_only_feedback(text: str) -> bool:
    normalized = normalize_french(text)
    quoted = re.findall(r'["\']([^"\']+)["\']', text)
    normalized_quoted = [normalize_french(item) for item in quoted if normalize_french(item)]
    same_normalized_pair = (
        len(normalized_quoted) >= 2
        and any(
            left == right
            for index, left in enumerate(normalized_quoted)
            for right in normalized_quoted[index + 1:]
        )
    )
    orthography_triggers = (
        "orthography",
        "orthographic",
        "name spelled incorrectly",
        "spelled incorrectly",
        "misspelled",
        "misspelt",
        "proper form",
        "spelling",
        "written form",
        "correct form",
    )
    return same_normalized_pair and any(trigger in normalized for trigger in orthography_triggers)


def is_overly_fussy_style_feedback(text: str) -> bool:
    normalized = " ".join(normalize_french(text).split())
    return any(
        phrase in normalized
        for phrase in (
            "more idiomatic choice",
            "more common choice",
            "slightly more idiomatic choice",
            "slightly more natural",
            "a bit more natural",
            "could be smoother",
            "sounds unusual",
            "consider",
            "you used",
        )
    )


def note_contradicts_canonical_vocab(text: str, canonical_phrases: list[str]) -> bool:
    normalized = normalize_french(text)
    if not any(trigger in normalized for trigger in ("prefer", "word choice", "sounds unusual", "more idiomatic", "more common")):
        return False
    return any(phrase and phrase in normalized for phrase in canonical_phrases)


def note_conflicts_target_structure(text: str, target_sentence: str) -> bool:
    note_normalized = normalize_french(text)
    target_normalized = normalize_french(target_sentence)
    if not note_normalized or not target_normalized:
        return False

    target_tokens = set(tokenize_french_context(target_sentence))
    anchored_after_match = re.search(r"\bafter ['\"]?([a-zà-ÿ]+)['\"]?", note_normalized)
    if anchored_after_match:
        anchor = normalize_french(anchored_after_match.group(1))
        if anchor and anchor not in target_tokens:
            return True

    anchored_before_match = re.search(r"\bbefore ['\"]?([a-zà-ÿ]+)['\"]?", note_normalized)
    if anchored_before_match:
        anchor = normalize_french(anchored_before_match.group(1))
        if anchor and anchor not in target_tokens:
            return True

    for function_word in ("chez", "dans", "a", "à", "de", "du", "des", "au", "aux"):
        if function_word in note_normalized and function_word not in target_tokens and f" {function_word} " not in target_normalized:
            if any(trigger in note_normalized for trigger in ("after", "before", "use", "add", "article")):
                return True

    return False


ENGLISH_SIGNAL_WORDS = {
    "the", "a", "an", "and", "or", "but", "with", "without", "near", "in", "on", "under", "over",
    "to", "from", "of", "for", "is", "are", "was", "were", "be", "have", "has", "had", "do", "does",
    "go", "goes", "come", "comes", "find", "finds", "see", "sees", "take", "takes", "small", "old",
    "young", "boy", "girl", "hero", "temple", "mountain", "sea", "task", "home", "light", "lamp",
}

FRENCH_SIGNAL_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "dans", "sur", "sous", "avec", "sans", "près",
    "pres", "pour", "par", "et", "ou", "mais", "est", "sont", "je", "tu", "il", "elle", "nous", "vous",
    "ils", "elles", "mon", "ma", "mes", "petit", "petite", "grand", "grande", "jeune", "garcon", "garçon",
    "heros", "héros", "mer", "montagne", "maison", "lumiere", "lumière", "temple", "sort", "entre",
}
SPANISH_SIGNAL_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "en", "con", "sin", "por",
    "para", "sobre", "pero", "y", "o", "es", "son", "yo", "tu", "tú", "el", "él", "ella", "nosotros",
    "vosotros", "ustedes", "ellos", "ellas", "pequeno", "pequeño", "pequena", "pequeña", "joven", "nino",
    "niño", "nina", "niña", "heroe", "héroe", "mar", "montana", "montaña", "casa", "luz", "lampara",
    "lámpara", "templo", "sale", "entra",
}


class AIService:
    def __init__(self) -> None:
        api_key = load_openai_api_key()
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.lesson_model = os.getenv("OPENAI_LESSON_MODEL", "gpt-5-mini")
        self.eval_model = os.getenv("OPENAI_EVAL_MODEL", "gpt-5-mini")
        self.lesson_reasoning_effort = os.getenv("OPENAI_LESSON_REASONING_EFFORT", "minimal")
        self.eval_reasoning_effort = os.getenv("OPENAI_EVAL_REASONING_EFFORT", "minimal")
        self.lesson_max_output_tokens = int(os.getenv("OPENAI_LESSON_MAX_OUTPUT_TOKENS", "1200"))
        self.eval_max_output_tokens = int(os.getenv("OPENAI_EVAL_MAX_OUTPUT_TOKENS", "520"))
        self.explain_max_output_tokens = int(os.getenv("OPENAI_EXPLAIN_MAX_OUTPUT_TOKENS", "220"))
        self.lesson_jobs: dict[str, dict[str, Any]] = {}
        self.lesson_jobs_lock = Lock()
        self.lesson_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="storytime-lessons")
        self.phrase_dictionaries = {
            language: {
                normalize_french(key): value
                for key, value in load_phrase_dictionary(language).items()
            }
            for language in ("french", "spanish")
        }
        self.verb_base_forms = {
            "suis": "être",
            "es": "être",
            "est": "être",
            "sommes": "être",
            "êtes": "être",
            "etes": "être",
            "sont": "être",
            "ai": "avoir",
            "as": "avoir",
            "a": "avoir",
            "avons": "avoir",
            "avez": "avoir",
            "ont": "avoir",
            "vais": "aller",
            "vas": "aller",
            "va": "aller",
            "allons": "aller",
            "allez": "aller",
            "vont": "aller",
            "viens": "venir",
            "vient": "venir",
            "venons": "venir",
            "venez": "venir",
            "viennent": "venir",
            "fais": "faire",
            "fait": "faire",
            "faisons": "faire",
            "faites": "faire",
            "font": "faire",
            "peux": "pouvoir",
            "peut": "pouvoir",
            "pouvons": "pouvoir",
            "pouvez": "pouvoir",
            "peuvent": "pouvoir",
            "veux": "vouloir",
            "veut": "vouloir",
            "voulons": "vouloir",
            "voulez": "vouloir",
            "veulent": "vouloir",
            "dois": "devoir",
            "doit": "devoir",
            "devons": "devoir",
            "devez": "devoir",
            "doivent": "devoir",
            "sais": "savoir",
            "sait": "savoir",
            "savons": "savoir",
            "savez": "savoir",
            "savent": "savoir",
            "prends": "prendre",
            "prend": "prendre",
            "prenons": "prendre",
            "prenez": "prendre",
            "prennent": "prendre",
            "parle": "parler",
            "parles": "parler",
            "parlons": "parler",
            "parlez": "parler",
            "parlent": "parler",
            "regarde": "regarder",
            "regardes": "regarder",
            "regardons": "regarder",
            "regardez": "regarder",
            "regardent": "regarder",
            "comprends": "comprendre",
            "comprend": "comprendre",
            "comprenons": "comprendre",
            "comprenez": "comprendre",
            "comprennent": "comprendre",
            "entre": "entrer",
            "entres": "entrer",
            "entrons": "entrer",
            "entrez": "entrer",
            "entrent": "entrer",
            "reste": "rester",
            "restes": "rester",
            "restons": "rester",
            "restez": "rester",
            "restent": "rester",
        }

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError(
                "OpenAI API access is required. Configure OPENAI_API_KEY and make sure the server can reach the internet."
            )

    def generate_lesson(self, request: LessonRequest, lesson_id: str) -> LessonResponse:
        self._require_enabled()
        try:
            return self._generate_lesson_with_background_continuation(request, lesson_id)
        except Exception as exc:
            raise RuntimeError(self._format_openai_error("lesson generation", exc)) from exc

    def get_lesson(self, lesson_id: str) -> LessonResponse:
        with self.lesson_jobs_lock:
            job = self.lesson_jobs.get(lesson_id)
        if job is None:
            raise RuntimeError("Lesson not found.")
        self._resolve_lesson_job(job)
        return self._build_lesson_response(job)

    def evaluate_answer(self, request: EvaluationRequest) -> EvaluationResponse:
        self._require_enabled()
        try:
            return self._evaluate_answer_openai(request)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(self._format_openai_error("answer evaluation", exc)) from exc

    def explain_phrase(self, request: PhraseExplainRequest) -> PhraseExplainResponse:
        try:
            return self._explain_phrase_local(request)
        except Exception as exc:
            raise RuntimeError(
                "Phrase explanation failed while looking up the local dictionary."
            ) from exc

    def _difficulty_guidance(self, difficulty: str) -> str:
        guidance = {
            "A1": (
                "Target a true beginner level. Use very short, concrete, high-frequency sentences only. "
                "Prefer present tense almost all the time. Keep to one clause per sentence wherever possible. "
                "Use very common verbs such as etre, avoir, aller, faire, vouloir, pouvoir, aimer, voir, venir, parler, and prendre. "
                "Use very common everyday nouns only. Avoid literary wording, abstract vocabulary, idioms, metaphor, passive voice, and unusual set phrases. "
                "Avoid relative clauses, long subordinate clauses, conditionals, and tense backshifts. "
                "If in doubt, make the French simpler, shorter, and more repetitive."
            ),
            "A2": (
                "Target a cautious elementary level. Use short, clear, everyday sentences with mostly common vocabulary. "
                "You may use simple past or near-future references, but syntax must stay easy to parse. "
                "Prefer one main idea per sentence. Keep connectors basic, such as et, mais, puis, parce que, and quand. "
                "Avoid dense phrasing, rare idioms, literary language, and long nested clauses."
            ),
            "B1": (
                "Target an intermediate but still accessible level. Use natural connected sentences with a moderate range of tenses and slightly richer vocabulary, "
                "but keep everything practical, readable, and clearly teachable. "
                "Do not drift into advanced literary or highly idiomatic phrasing."
            ),
            "B2": (
                "Target an upper-intermediate level. Use more nuanced, idiomatic, and detailed language, with richer transitions and more natural phrasing, "
                "while still keeping the lesson teachable and not overly ornate."
            ),
            "C1": (
                "Target an advanced level. Use fluent, precise, and sophisticated language with natural complexity, "
                "while remaining coherent, teachable, and not unnecessarily obscure."
            ),
        }
        return guidance[difficulty]

    def _language_name(self, language: str) -> str:
        return LANGUAGE_NAMES.get(language, "French")

    def _target_signal_words(self, language: str) -> set[str]:
        return SPANISH_SIGNAL_WORDS if language == "spanish" else FRENCH_SIGNAL_WORDS

    def _function_words(self, language: str) -> set[str]:
        return SPANISH_FUNCTION_WORDS if language == "spanish" else FRENCH_FUNCTION_WORDS

    def _difficulty_guidance_for_language(self, difficulty: str, language: str) -> str:
        if language != "spanish":
            return self._difficulty_guidance(difficulty)

        guidance = {
            "A1": (
                "Target a true beginner level. Use very short, concrete, high-frequency sentences only. "
                "Prefer present tense almost all the time. Keep to one clause per sentence wherever possible. "
                "Use very common verbs such as ser, estar, tener, ir, hacer, querer, poder, gustar, ver, venir, hablar, and tomar. "
                "Use very common everyday nouns only. Avoid literary wording, abstract vocabulary, idioms, metaphor, passive voice, and unusual set phrases. "
                "Avoid relative clauses, long subordinate clauses, conditionals, and tense backshifts. "
                "If in doubt, make the Spanish simpler, shorter, and more repetitive."
            ),
            "A2": (
                "Target a cautious elementary level. Use short, clear, everyday sentences with mostly common vocabulary. "
                "You may use simple past or near-future references, but syntax must stay easy to parse. "
                "Prefer one main idea per sentence. Keep connectors basic, such as y, pero, luego, porque, and cuando. "
                "Avoid dense phrasing, rare idioms, literary language, and long nested clauses."
            ),
            "B1": (
                "Target an intermediate but still accessible level. Use natural connected sentences with a moderate range of tenses and slightly richer vocabulary, "
                "but keep everything practical, readable, and clearly teachable. "
                "Do not drift into advanced literary or highly idiomatic phrasing."
            ),
            "B2": (
                "Target an upper-intermediate level. Use more nuanced, idiomatic, and detailed language, with richer transitions and more natural phrasing, "
                "while still keeping the lesson teachable and not overly ornate."
            ),
            "C1": (
                "Target an advanced level. Use fluent, precise, and sophisticated language with natural complexity, "
                "while remaining coherent, teachable, and not unnecessarily obscure."
            ),
        }
        return guidance[difficulty]

    def _difficulty_guardrails(self, difficulty: str, language: str = "french") -> str:
        guardrails = {
            "A1": (
                "A1 hard limits:\n"
                "- Average French sentence length should feel short and beginner-friendly.\n"
                "- Most sentences should be understandable with school-level everyday vocabulary.\n"
                "- Do not rely on imparfait, conditionnel, subjonctif, or complex reported speech.\n"
                "- Do not use advanced connectors such as cependant, pourtant, toutefois, tandis que, or heavy clause chaining.\n"
                "- The learner should not need advanced grammar knowledge to produce a reasonable answer."
            ),
            "A2": (
                "A2 hard limits:\n"
                "- Keep the wording clearly easier than a typical B1 textbook passage.\n"
                "- Limited use of past or future is fine, but keep the sentence architecture simple.\n"
                "- Do not overload any one sentence with several grammar challenges at once."
            ),
            "B1": (
                "B1 hard limits:\n"
                "- Natural variation is good, but keep the lesson comfortably below advanced literary French.\n"
                "- Each sentence should still be translatable without specialist vocabulary."
            ),
            "B2": (
                "B2 hard limits:\n"
                "- Richer phrasing is welcome, but do not make the sentences so dense that they feel C1 by default."
            ),
            "C1": (
                "C1 hard limits:\n"
                "- Advanced should mean fluent and precise, not obscure or unnecessarily difficult."
            ),
        }
        if language != "spanish":
            return guardrails[difficulty]

        localized = {
            "A1": (
                "A1 hard limits:\n"
                "- Average Spanish sentence length should feel short and beginner-friendly.\n"
                "- Most sentences should be understandable with school-level everyday vocabulary.\n"
                "- Do not rely on the subjunctive, complex conditional structures, or dense reported speech.\n"
                "- Do not use advanced connectors or heavy clause chaining.\n"
                "- The learner should not need advanced grammar knowledge to produce a reasonable answer."
            ),
            "A2": (
                "A2 hard limits:\n"
                "- Keep the wording clearly easier than a typical B1 textbook passage.\n"
                "- Limited use of past or future is fine, but keep the sentence architecture simple.\n"
                "- Do not overload any one sentence with several grammar challenges at once."
            ),
            "B1": guardrails["B1"].replace("French", "Spanish"),
            "B2": guardrails["B2"],
            "C1": guardrails["C1"],
        }
        return localized[difficulty]

    def _lesson_type_guidance(self, lesson_type: str, theme: str) -> str:
        if lesson_type == "story":
            return (
                "This MUST be a story. Every sentence must advance narrated events. "
                "Do not turn it into a dialogue. "
                f"Make the story visibly about '{theme}'. "
                f"{self._story_source_guidance(theme)}"
            )
        if lesson_type == "dialogue":
            return (
                "This MUST be a dialogue. Every sentence must be spoken by a character. "
                "Alternate speakers consistently, and prefix every English and French sentence with speaker labels. "
                "Do not switch into narration. "
                f"Make the conversation visibly about '{theme}'."
            )
        if lesson_type == "film_scene":
            return (
                "This MUST feel like a film scene. Keep one scene, one dramatic situation, and cinematic visual detail throughout. "
                "You may mix spoken lines and scene beats, but the whole lesson must still feel like the same scene. "
                f"Make the scene visibly about '{theme}'."
            )
        return (
            "Choose exactly one format that best fits the theme: story, dialogue, or film scene. "
            "Once chosen, stay in that format for the whole lesson. "
            f"Make the chosen format visibly about '{theme}'."
        )

    def _story_source_guidance(self, theme: str) -> str:
        lowered = theme.lower()
        known_story_cues = {
            "myth",
            "legend",
            "folktale",
            "fairy tale",
            "fairytale",
            "epic",
            "odyssey",
            "iliad",
            "greek",
            "roman",
            "norse",
            "arthur",
            "arthurian",
            "camelot",
            "shakespeare",
            "bible",
            "biblical",
            "fable",
            "homer",
            "trojan",
            "hercules",
            "achilles",
            "odysseus",
            "ulysses",
            "theseus",
            "minotaur",
            "medusa",
            "perseus",
            "orpheus",
            "pandora",
            "icarus",
            "atlantis",
            "labyrinth",
        }
        if any(cue in lowered for cue in known_story_cues):
            return (
                "Because this theme points to an existing narrative tradition, base the lesson on a real, recognizable story or episode that already exists, "
                "rather than inventing a generic placeholder plot. "
                "For example, a Greek myth theme should clearly echo a specific myth such as Theseus and the Minotaur, Perseus and Medusa, Orpheus, Icarus, or another real myth. "
                "Keep it simplified to the requested CEFR level, but the underlying plot should still be identifiable."
            )
        return (
            "If the theme clearly points to a well-known existing story, legend, myth, or tale, prefer adapting that recognizable source instead of inventing a generic placeholder plot. "
            "If it does not point to a known narrative, create an original story that still feels specific rather than generic."
        )

    def _resolve_fallback_lesson_type(self, request: LessonRequest) -> str:
        if request.lesson_type != "auto":
            return request.lesson_type

        theme = request.theme.lower()
        if any(word in theme for word in {"coffee", "cafe", "restaurant", "interview", "meeting", "shop", "hotel", "date"}):
            return "dialogue"
        if any(word in theme for word in {"mystery", "film", "cinema", "thriller", "heist", "monster", "myth", "labyrinth"}):
            return "film_scene"
        return "story"

    def _supports_reasoning_controls(self, model: str) -> bool:
        lowered = model.lower()
        return lowered.startswith("gpt-5") or lowered.startswith("o")

    def _response_create_options(
        self,
        *,
        model: str,
        max_output_tokens: int,
        reasoning_effort: str | None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "model": model,
            "max_output_tokens": max_output_tokens,
        }
        if reasoning_effort and self._supports_reasoning_controls(model):
            options["reasoning"] = {"effort": reasoning_effort}
        return options

    def _responses_create_with_retry(self, *, retries: int = 2, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return self.client.responses.create(**kwargs)
            except RateLimitError as exc:
                last_error = exc
                error_body = getattr(exc, "body", {}) or {}
                error_code = ((error_body.get("error") or {}).get("code")) if isinstance(error_body, dict) else None
                if error_code == "insufficient_quota" or attempt >= retries:
                    raise
            except BadRequestError:
                raise
            except (APIConnectionError, APITimeoutError) as exc:
                last_error = exc
                if attempt >= retries:
                    raise
            except APIError as exc:
                last_error = exc
                status_code = getattr(exc, "status_code", None)
                if status_code and status_code < 500 and status_code != 429:
                    raise
                if attempt >= retries:
                    raise

            time.sleep(0.6 * (attempt + 1))

        if last_error is not None:
            raise last_error
        raise RuntimeError("OpenAI request failed unexpectedly.")

    def _format_openai_error(self, action: str, exc: Exception) -> str:
        if isinstance(exc, RateLimitError):
            error_body = getattr(exc, "body", {}) or {}
            error_code = ((error_body.get("error") or {}).get("code")) if isinstance(error_body, dict) else None
            if error_code == "insufficient_quota":
                return (
                    f"{action.capitalize()} failed because the OpenAI API quota has been exceeded. "
                    "Check billing and usage on platform.openai.com."
                )
            return (
                f"{action.capitalize()} was rate-limited by OpenAI. "
                "Please wait a moment and try again."
            )

        if isinstance(exc, BadRequestError):
            return (
                f"{action.capitalize()} failed because the current OpenAI model or request format was rejected. "
                "Check the configured model name and request settings."
            )

        if isinstance(exc, APITimeoutError):
            return f"{action.capitalize()} timed out while waiting for OpenAI. Please try again."

        if isinstance(exc, APIConnectionError):
            return f"{action.capitalize()} failed because the server could not reach OpenAI. Check the internet connection and try again."

        if isinstance(exc, APIError):
            return f"{action.capitalize()} failed because OpenAI returned a temporary server error. Please try again."

        if isinstance(exc, json.JSONDecodeError):
            return (
                f"{action.capitalize()} failed because the model returned an invalid structured response. "
                "Please try again."
            )

        return (
            f"{action.capitalize()} failed while calling OpenAI. "
            "Check the API key, internet connection, and model configuration."
        )

    def _score_answer_locally(self, request: EvaluationRequest) -> tuple[int, bool, bool]:
        learner_normalized = normalize_french(request.learner_answer)
        target_normalized = normalize_french(request.target_sentence)
        learner_tokens = learner_normalized.split()
        target_tokens = target_normalized.split()
        function_words = self._function_words(request.language)

        if not learner_tokens:
            return 0, False, False

        target_content_tokens = [token for token in target_tokens if token not in function_words]
        learner_content_tokens = [token for token in learner_tokens if token not in function_words]
        target_function_tokens = [token for token in target_tokens if token in function_words]
        learner_function_tokens = [token for token in learner_tokens if token in function_words]

        content_matched, content_total = counter_overlap(target_content_tokens, learner_content_tokens)
        function_matched, function_total = counter_overlap(target_function_tokens, learner_function_tokens)
        token_matched, token_total = counter_overlap(target_tokens, learner_tokens)

        content_ratio = content_matched / content_total if content_total else 1.0
        function_ratio = function_matched / function_total if function_total else 1.0
        token_ratio = token_matched / token_total if token_total else 1.0
        sequence_ratio = SequenceMatcher(None, learner_normalized, target_normalized).ratio()

        score = (
            45 * content_ratio +
            20 * function_ratio +
            20 * token_ratio +
            15 * sequence_ratio
        )

        missing_critical = [
            token for token in target_function_tokens
            if token in {"de", "du", "des", "dans", "a", "à", "au", "aux", "ne", "pas", "y", "en"}
            and token not in learner_function_tokens
        ]
        if request.language == "spanish":
            critical_function_words = {"de", "del", "a", "al", "en", "se", "lo", "la"}
            missing_critical = [
                token for token in target_function_tokens
                if token in critical_function_words
                and token not in learner_function_tokens
            ]
        score -= min(18, len(missing_critical) * 6)
        score -= min(24, self._count_local_contraction_mismatches(request) * 12)

        if learner_normalized == target_normalized:
            score = max(score, 96)

        if content_ratio < 0.55 and function_ratio < 0.7:
            score = min(score, 58)
        elif content_ratio < 0.7:
            score = min(score, 72)

        score = int(max(0, min(100, round(score))))
        is_correct = learner_normalized == target_normalized or score >= 85
        return score, is_correct

    def _count_local_contraction_mismatches(self, request: EvaluationRequest) -> int:
        learner_tokens = [normalize_french(token) for token in re.split(r"\s+", request.learner_answer.strip()) if token]
        target_tokens = [normalize_french(token) for token in re.split(r"\s+", request.target_sentence.strip()) if token]
        mismatch_count = 0

        contraction_expectations = (
            {
                "al": {("a", "el")},
                "del": {("de", "el")},
            }
            if request.language == "spanish"
            else {
                "au": {("a", "la"), ("a", "le"), ("a", "les")},
                "aux": {("a", "les"), ("a", "des")},
                "du": {("de", "la"), ("de", "le"), ("de", "les")},
            }
        )

        for index, token in enumerate(target_tokens[:-1]):
            expected_pairs = contraction_expectations.get(token)
            if not expected_pairs:
                continue

            next_target = target_tokens[index + 1]
            for learner_index in range(len(learner_tokens) - 2):
                learner_pair = (learner_tokens[learner_index], learner_tokens[learner_index + 1])
                learner_next = learner_tokens[learner_index + 2]
                if learner_next == next_target and learner_pair in expected_pairs:
                    mismatch_count += 1
                    break

        return mismatch_count

    def _is_orthography_equivalent(self, learner_answer: str, target_sentence: str) -> bool:
        return normalize_french(learner_answer) == normalize_french(target_sentence)

    def _sanitize_feedback_payload(self, payload: dict[str, Any], language: str = "french") -> dict[str, Any]:
        cleaned = dict(payload)
        cleaned["reminder_key"] = normalize_reminder_key(cleaned.get("reminder_key", ""))
        cleaned["reminder_label"] = localize_reminder_wording(cleaned.get("reminder_label", ""), language)
        cleaned["reminder_explanation"] = localize_reminder_wording(cleaned.get("reminder_explanation", ""), language)
        cleaned["reminder_wrong_pattern"] = str(cleaned.get("reminder_wrong_pattern", "") or "").strip()
        cleaned["reminder_correct_pattern"] = str(cleaned.get("reminder_correct_pattern", "") or "").strip()
        cleaned["reminder_wrong_focus"] = str(cleaned.get("reminder_wrong_focus", "") or "").strip()
        cleaned["reminder_correct_focus"] = str(cleaned.get("reminder_correct_focus", "") or "").strip()
        cleaned["tips"] = [
            tip
            for tip in cleaned.get("tips", [])
            if not is_accent_feedback(tip)
            and not is_capitalization_feedback(tip)
            and not is_punctuation_feedback(tip)
            and not is_orthography_only_feedback(tip)
        ]
        cleaned["mistakes"] = [
            mistake
            for mistake in cleaned.get("mistakes", [])
            if not is_accent_feedback(mistake)
            and not is_capitalization_feedback(mistake)
            and not is_punctuation_feedback(mistake)
            and not is_orthography_only_feedback(mistake)
        ]

        if (
            is_accent_feedback(cleaned.get("verdict", ""))
            or is_capitalization_feedback(cleaned.get("verdict", ""))
            or is_punctuation_feedback(cleaned.get("verdict", ""))
            or is_orthography_only_feedback(cleaned.get("verdict", ""))
        ):
            cleaned["verdict"] = "Correct and natural."
        if (
            is_accent_feedback(cleaned.get("encouraging_note", ""))
            or is_capitalization_feedback(cleaned.get("encouraging_note", ""))
            or is_punctuation_feedback(cleaned.get("encouraging_note", ""))
            or is_orthography_only_feedback(cleaned.get("encouraging_note", ""))
        ):
            cleaned["encouraging_note"] = ""

        if not cleaned["reminder_key"] or not cleaned["reminder_label"]:
            cleaned["reminder_key"] = ""
            cleaned["reminder_label"] = ""
            cleaned["reminder_explanation"] = ""
            cleaned["reminder_wrong_pattern"] = ""
            cleaned["reminder_correct_pattern"] = ""
            cleaned["reminder_wrong_focus"] = ""
            cleaned["reminder_correct_focus"] = ""

        return cleaned

    def _sanitize_learner_display_tokens(
        self,
        tokens: Any,
        learner_answer: str,
        target_sentence: str = "",
        learner_token_labels: list[str] | None = None,
    ) -> list[dict[str, str]]:
        if not isinstance(tokens, list):
            return []

        allowed_statuses = {"correct", "acceptable", "wrong", "missing", "neutral"}
        cleaned: list[dict[str, str]] = []
        for token in tokens:
            if not isinstance(token, dict):
                continue
            text = str(token.get("text", "") or "").strip()
            status = str(token.get("status", "") or "").strip().lower()
            if not text or status not in allowed_statuses:
                continue
            cleaned.append({"text": text, "status": status})

        learner_tokens = [part for part in re.split(r"\s+", learner_answer.strip()) if part]
        submitted_tokens = [token for token in cleaned if token["status"] != "missing"]
        if learner_tokens and len(submitted_tokens) != len(learner_tokens):
            return []

        if learner_tokens:
            for index, learner_token in enumerate(learner_tokens):
                if normalize_french(submitted_tokens[index]["text"]) != normalize_french(learner_token):
                    return []

        return cleaned

    def _sanitize_token_labels(self, labels: Any, learner_answer: str, target_sentence: str = "") -> list[str]:
        learner_tokens = [part for part in re.split(r"\s+", learner_answer.strip()) if part]
        raw_labels = labels if isinstance(labels, list) else []
        cleaned_labels = [
            label for label in raw_labels
            if label in {"correct", "acceptable", "wrong"}
        ]
        if len(cleaned_labels) == len(learner_tokens):
            return cleaned_labels
        return []

    def _build_fallback_token_labels(
        self,
        learner_answer: str,
        target_sentence: str,
        *,
        is_correct: bool,
    ) -> list[str]:
        learner_tokens = [part for part in re.split(r"\s+", learner_answer.strip()) if part]
        if not learner_tokens:
            return []

        learner_normalized = [normalize_french(token) for token in learner_tokens]
        target_tokens = [part for part in re.split(r"\s+", target_sentence.strip()) if part]
        target_normalized = [normalize_french(token) for token in target_tokens]
        target_counts = Counter(token for token in target_normalized if token)

        labels: list[str] = []
        for index, token in enumerate(learner_normalized):
            if not token:
                labels.append("wrong")
                continue
            target_token = target_normalized[index] if index < len(target_normalized) else ""
            if token != target_token and (
                token in self._function_words("spanish") or token in self._function_words("french")
                or target_token in self._function_words("spanish") or target_token in self._function_words("french")
            ):
                labels.append("wrong")
                continue
            if target_counts.get(token, 0) > 0:
                target_counts[token] -= 1
                labels.append("correct")
                continue
            labels.append("correct" if is_correct else "wrong")
        return labels

    def _build_fallback_display_tokens(
        self,
        learner_answer: str,
        learner_token_labels: list[str] | None = None,
    ) -> list[dict[str, str]]:
        learner_tokens = [part for part in re.split(r"\s+", learner_answer.strip()) if part]
        labels = learner_token_labels if isinstance(learner_token_labels, list) else []
        if len(labels) != len(learner_tokens):
            labels = ["neutral" for _ in learner_tokens]
        return [
            {
                "text": token,
                "status": label if label in {"correct", "acceptable", "wrong"} else "neutral",
            }
            for token, label in zip(learner_tokens, labels)
        ]

    def _enforce_learner_display_tokens(
        self,
        payload: dict[str, Any],
        request: EvaluationRequest,
    ) -> list[dict[str, str]]:
        learner_tokens = [part for part in re.split(r"\s+", request.learner_answer.strip()) if part]
        if not learner_tokens:
            return payload.get("learner_display_tokens", [])

        corrected_sentence = (
            str(payload.get("suggested_sentence", "") or "").strip()
            or request.target_sentence
        )
        corrected_tokens = [part for part in re.split(r"\s+", corrected_sentence.strip()) if part]
        if not corrected_tokens:
            return payload.get("learner_display_tokens", [])

        learner_norm = [normalize_french(token) for token in learner_tokens]
        corrected_norm = [normalize_french(token) for token in corrected_tokens]

        existing_display = payload.get("learner_display_tokens")
        submitted_display = [
            token for token in existing_display
            if isinstance(token, dict) and str(token.get("status", "")).lower() != "missing"
        ] if isinstance(existing_display, list) else []

        submitted_statuses: list[str] = []
        if len(submitted_display) == len(learner_tokens):
            for token in submitted_display:
                status = str(token.get("status", "neutral") or "neutral").lower()
                submitted_statuses.append(status if status in {"correct", "acceptable", "wrong", "neutral"} else "neutral")
        else:
            raw_labels = payload.get("learner_token_labels")
            if isinstance(raw_labels, list) and len(raw_labels) == len(learner_tokens):
                submitted_statuses = [
                    label if label in {"correct", "acceptable", "wrong"} else "neutral"
                    for label in raw_labels
                ]
            else:
                submitted_statuses = ["neutral" for _ in learner_tokens]

        rebuilt: list[dict[str, str]] = []
        matcher = SequenceMatcher(None, learner_norm, corrected_norm)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for offset in range(i2 - i1):
                    rebuilt.append({
                        "text": learner_tokens[i1 + offset],
                        "status": "correct",
                    })
                continue

            if tag in {"replace", "delete"}:
                for index in range(i1, i2):
                    rebuilt.append({
                        "text": learner_tokens[index],
                        "status": submitted_statuses[index] if index < len(submitted_statuses) else "wrong",
                    })

            if tag == "insert" and j2 > j1:
                for index in range(j1, j2):
                    rebuilt.append({
                        "text": corrected_tokens[index],
                        "status": "missing",
                    })

        return rebuilt or payload.get("learner_display_tokens", [])

    def _ensure_minimal_specific_feedback(
        self,
        payload: dict[str, Any],
        request: EvaluationRequest,
        *,
        is_correct: bool,
    ) -> dict[str, Any]:
        if is_correct:
            single_swap = find_single_aligned_token_swap(
                request.learner_answer,
                request.target_sentence,
            )
            if single_swap:
                learner_raw, learner_norm, target_raw, target_norm = single_swap
                if learner_norm != target_norm:
                    return {
                        **payload,
                        "mistakes": [f'Use "{target_raw}" here, not "{learner_raw}".'],
                        "tips": [],
                    }
            function_swap = find_single_function_word_swap(
                request.learner_answer,
                request.target_sentence,
                request.language,
            )
            if function_swap:
                _, _, learner_raw, target_raw = function_swap
                return {
                    **payload,
                    "mistakes": [f'Use "{target_raw}" here, not "{learner_raw}".'],
                    "tips": [],
                }
            return payload
        if payload.get("tips") or payload.get("mistakes"):
            return payload

        contraction_note = self._build_local_contraction_note(request)
        if contraction_note:
            return {
                **payload,
                "mistakes": [contraction_note],
            }

        learner_tokens = [part for part in re.split(r"\s+", request.learner_answer.strip()) if part]
        target_tokens = [part for part in re.split(r"\s+", request.target_sentence.strip()) if part]
        learner_normalized = [normalize_french(token) for token in learner_tokens]
        target_normalized = [normalize_french(token) for token in target_tokens]

        if len(learner_normalized) == len(target_normalized):
            mismatches = [
                (learner_raw, learner_norm, target_raw, target_norm)
                for learner_raw, learner_norm, target_raw, target_norm in zip(
                    learner_tokens,
                    learner_normalized,
                    target_tokens,
                    target_normalized,
                )
                if learner_norm and target_norm and learner_norm != target_norm
            ]
            if len(mismatches) == 1:
                learner_raw, learner_norm, target_raw, target_norm = mismatches[0]
                if target_norm in self._function_words(request.language) or learner_norm in self._function_words(request.language):
                    return {
                        **payload,
                        "mistakes": [f'Use "{target_raw}" here, not "{learner_raw}".'],
                    }
                return {
                    **payload,
                    "mistakes": [f'Use "{target_raw}" here.'],
                }

        return payload

    def _build_local_contraction_note(self, request: EvaluationRequest) -> str:
        learner_raw_tokens = [part for part in re.split(r"\s+", request.learner_answer.strip()) if part]
        target_raw_tokens = [part for part in re.split(r"\s+", request.target_sentence.strip()) if part]
        learner_tokens = [normalize_french(token) for token in learner_raw_tokens]
        target_tokens = [normalize_french(token) for token in target_raw_tokens]

        contraction_expectations = (
            {
                "al": {("a", "el")},
                "del": {("de", "el")},
            }
            if request.language == "spanish"
            else {
                "au": {("a", "la"), ("a", "le"), ("a", "les")},
                "aux": {("a", "les"), ("a", "des")},
                "du": {("de", "la"), ("de", "le"), ("de", "les")},
            }
        )

        for index, token in enumerate(target_tokens[:-1]):
            expected_pairs = contraction_expectations.get(token)
            if not expected_pairs or index + 1 >= len(target_raw_tokens):
                continue

            target_phrase_raw = f"{target_raw_tokens[index]} {target_raw_tokens[index + 1]}"
            next_target = target_tokens[index + 1]

            for learner_index in range(len(learner_tokens) - 2):
                learner_pair = (learner_tokens[learner_index], learner_tokens[learner_index + 1])
                learner_next = learner_tokens[learner_index + 2]
                if learner_next == next_target and learner_pair in expected_pairs:
                    if token == "al":
                        return f'Use "{target_phrase_raw}" here; "a + el" becomes "al".'
                    if token == "del":
                        return f'Use "{target_phrase_raw}" here; "de + el" becomes "del".'
                    if token == "au":
                        return f'Use "{target_phrase_raw}" here; "à + le/la/les" contracts differently.'
                    if token == "aux":
                        return f'Use "{target_phrase_raw}" here; "à + les" becomes "aux".'
                    if token == "du":
                        return f'Use "{target_phrase_raw}" here; "de + le" becomes "du".'

        return ""

    def _apply_required_construction_guard(
        self,
        payload: dict[str, Any],
        request: EvaluationRequest,
        *,
        correctness_score: int,
        is_correct: bool,
    ) -> tuple[dict[str, Any], int, bool]:
        issue_present = bool(payload.get("has_required_construction_issue"))
        note = (payload.get("required_construction_note") or "").strip()

        if not issue_present:
            return payload, correctness_score, is_correct

        if not note:
            note = self._build_local_contraction_note(request) or 'Use the target construction here.'

        cleaned = {
            **payload,
            "meaning_equivalent": False,
            "accepted_learner_sentence": "",
            "mistakes": [note],
            "tips": [],
        }
        return cleaned, min(correctness_score, 79), False

    def _remove_fussy_style_feedback(
        self,
        payload: dict[str, Any],
        *,
        correctness_score: int,
        is_correct: bool,
    ) -> dict[str, Any]:
        accepted_learner_sentence = (payload.get("accepted_learner_sentence") or "").strip()
        should_strip = accepted_learner_sentence or (is_correct and correctness_score >= 85)
        if not should_strip:
            return payload

        cleaned = dict(payload)
        cleaned["tips"] = [tip for tip in cleaned.get("tips", []) if not is_overly_fussy_style_feedback(tip)]
        cleaned["mistakes"] = [mistake for mistake in cleaned.get("mistakes", []) if not is_overly_fussy_style_feedback(mistake)]

        if is_overly_fussy_style_feedback(cleaned.get("verdict", "")):
            cleaned["verdict"] = "Correct and natural."
        return cleaned

    def _remove_canonical_vocab_contradictions(
        self,
        payload: dict[str, Any],
        request: EvaluationRequest,
    ) -> dict[str, Any]:
        canonical_phrases = [
            normalize_french(request.target_sentence),
            *[normalize_french(hint.french) for hint in request.vocab_hints],
        ]
        canonical_phrases = [phrase for phrase in canonical_phrases if phrase]

        cleaned = dict(payload)
        cleaned["tips"] = [
            tip for tip in cleaned.get("tips", [])
            if not note_contradicts_canonical_vocab(tip, canonical_phrases)
            and not note_conflicts_target_structure(tip, request.target_sentence)
        ]
        cleaned["mistakes"] = [
            mistake for mistake in cleaned.get("mistakes", [])
            if not note_contradicts_canonical_vocab(mistake, canonical_phrases)
            and not note_conflicts_target_structure(mistake, request.target_sentence)
        ]
        return cleaned

    def _infer_noun_article(self, sentence_text: str, hint_text: str, language: str = "french") -> str | None:
        sentence_tokens = tokenize_french_context(sentence_text)
        hint_tokens = tokenize_french_context(hint_text)
        if not sentence_tokens or not hint_tokens:
            return None

        if language == "spanish":
            masculine_determiners = {"un", "el", "del", "al", "este", "ese", "aquel", "mi", "tu", "su", "nuestro", "vuestro"}
            feminine_determiners = {"una", "la", "esta", "esa", "aquella", "mi", "tu", "su", "nuestra", "vuestra"}
            neutral_skip = {
                "de", "los", "las", "mis", "tus", "sus", "estos", "estas", "esos", "esas", "aquellos", "aquellas",
                "pequeno", "pequeño", "pequena", "pequeña", "pequenos", "pequeños", "pequenas", "pequeñas",
                "grande", "grandes", "bueno", "buena", "buenos", "buenas", "viejo", "vieja", "viejos", "viejas",
                "joven", "jovenes", "jóvenes", "otro", "otra", "otros", "otras",
            }
        else:
            masculine_determiners = {
                "un", "le", "du", "au", "ce", "cet", "mon", "ton", "son", "notre", "votre", "leur"
            }
            feminine_determiners = {
                "une", "la", "cette", "ma", "ta", "sa", "notre", "votre", "leur"
            }
            neutral_skip = {
                "de", "d", "des", "les", "mes", "tes", "ses", "ces", "quelques", "plusieurs",
                "petit", "petite", "petits", "petites", "grand", "grande", "grands", "grandes",
                "bon", "bonne", "bons", "bonnes", "vieux", "vieille", "vieux", "vieilles",
                "jeune", "jeunes", "beau", "belle", "beaux", "belles", "nouveau", "nouvelle",
                "nouveaux", "nouvelles", "mauvais", "mauvaise", "mauvaises", "chaud", "chaude",
                "chauds", "chaudes", "ancien", "ancienne", "anciens", "anciennes", "autre", "autres",
            }

        for index in range(len(sentence_tokens) - len(hint_tokens) + 1):
            if sentence_tokens[index:index + len(hint_tokens)] != hint_tokens:
                continue

            for back in range(1, 4):
                look_index = index - back
                if look_index < 0:
                    break
                token = sentence_tokens[look_index]
                if token in masculine_determiners:
                    return "un"
                if token in feminine_determiners:
                    return "une"
                if token not in neutral_skip:
                    break

        return None

    def _apply_local_hint_display_rules(self, sentences: list[LessonSentence], language: str = "french") -> list[LessonSentence]:
        for sentence in sentences:
            updated_hints: list[VocabHint] = []
            for hint in sentence.vocab_hints:
                display_french = (hint.display_french or "").strip()
                inferred_article = self._infer_noun_article(sentence.french, hint.french, language)

                if inferred_article and (not display_french or display_french == hint.french):
                    updated_hints.append(
                        VocabHint(
                            english=hint.english,
                            french=hint.french,
                            display_french=f"{inferred_article} {hint.french}",
                            note=hint.note,
                        )
                    )
                else:
                    updated_hints.append(
                        VocabHint(
                            english=hint.english,
                            french=hint.french,
                            display_french=display_french or hint.french,
                            note=hint.note,
                        )
                    )
            sentence.vocab_hints = updated_hints

        return sentences

    def _enrich_vocab_hints(self, sentences: list[LessonSentence], difficulty: str, language: str = "french") -> list[LessonSentence]:
        if not self.client or not any(sentence.vocab_hints for sentence in sentences):
            return self._apply_local_hint_display_rules(sentences, language)

        schema = {
            "name": "vocab_hint_display_enrichment",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sentences": {
                        "type": "array",
                        "minItems": len(sentences),
                        "maxItems": len(sentences),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "step": {"type": "integer"},
                                "vocab_hints": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "english": {"type": "string"},
                                            "french": {"type": "string"},
                                            "display_french": {"type": "string"},
                                        },
                                        "required": ["english", "french", "display_french"],
                                    },
                                },
                            },
                            "required": ["step", "vocab_hints"],
                        },
                    }
                },
                "required": ["sentences"],
            },
        }

        sentence_payload = [
            {
                "step": sentence.step,
                "english": sentence.english,
                "french": sentence.french,
                "vocab_hints": [
                    {
                        "english": hint.english,
                        "french": hint.french,
                        "display_french": hint.display_french or hint.french,
                    }
                    for hint in sentence.vocab_hints
                ],
            }
            for sentence in sentences
        ]

        try:
            response = self._responses_create_with_retry(
                **self._response_create_options(
                    model=self.eval_model,
                    max_output_tokens=max(320, min(self.eval_max_output_tokens + 220, 700)),
                    reasoning_effort=self.eval_reasoning_effort,
                ),
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You normalize the display of French vocabulary hints for a learner app. "
                            "Keep the english and french fields exactly unchanged. "
                            "Rewrite only the display_french field. "
                            "For nouns, display_french must use the indefinite article plus the noun, for example 'une gare' or 'un musée'. "
                            "For adjectives, if masculine and feminine forms are different, display_french must show both forms, for example 'grand / grande'. "
                            "For adjectives whose forms are the same, keep just the French form. "
                            "For verbs and other parts of speech, keep display_french equal to the French form. "
                            "Do not add explanations, typing advice, accent notes, or English words into display_french. "
                            "Return one sentence entry for every input sentence, even if it has no hints."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Difficulty: {difficulty}\n"
                            f"Sentences and hints to enrich:\n{json.dumps(sentence_payload, ensure_ascii=False)}"
                        ),
                    },
                ],
                text={"format": {"type": "json_schema", **schema}},
            )
            payload = json.loads(response.output_text)
        except Exception:
            return self._apply_local_hint_display_rules(sentences, language)

        hints_by_step = {
            item["step"]: item.get("vocab_hints", [])
            for item in payload.get("sentences", [])
            if isinstance(item, dict)
        }

        enriched_sentences: list[LessonSentence] = []
        for sentence in sentences:
            enriched_hints = hints_by_step.get(sentence.step)
            if enriched_hints is None:
                enriched_sentences.append(sentence)
                continue

            try:
                sentence.vocab_hints = [VocabHint(**hint) for hint in enriched_hints]
            except Exception:
                pass
            enriched_sentences.append(sentence)

        return self._apply_local_hint_display_rules(enriched_sentences, language)

    def _align_sentence_pairs(self, sentences: list[LessonSentence], difficulty: str, language: str = "french") -> list[LessonSentence]:
        if not self.client or not sentences:
            return sentences

        schema = {
            "name": "lesson_pair_alignment",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sentences": self._lesson_sentence_schema(len(sentences), len(sentences)),
                },
                "required": ["sentences"],
            },
        }

        payload_sentences = [
            {
                "step": sentence.step,
                "english": sentence.english,
                "french": sentence.french,
                "context_note": sentence.context_note,
                "vocab_hints": [
                    {
                        "english": hint.english,
                        "french": hint.french,
                        "note": hint.note,
                    }
                    for hint in sentence.vocab_hints
                ],
            }
            for sentence in sentences
        ]

        try:
            response = self._responses_create_with_retry(
                **self._response_create_options(
                    model=self.lesson_model,
                    max_output_tokens=max(520, min(self.lesson_max_output_tokens, 1200)),
                    reasoning_effort=self.lesson_reasoning_effort,
                ),
                input=[
                    {
                        "role": "system",
                        "content": (
                            f"You verify alignment between learner-facing English prompts and their target {self._language_name(language)} answers. "
                            f"Your job is to repair any mismatch between the English prompt and the {self._language_name(language)} target answer. "
                            "The english field must be clear natural English only. "
                            f"The french field must be clear natural {self._language_name(language)} only. "
                            "Revise whichever field is wrong or weaker, but prefer the smallest change that produces a clean, fully aligned pair. "
                            f"If the English and {self._language_name(language)} do not match exactly in meaning, fix the pair so they do. "
                            "Be strict about hidden meaning details: if one side includes an extra object, location detail, relationship, or descriptive phrase, the other side must include it too. "
                            "Do not accept 'close enough' alignment. The learner should be able to translate the English prompt into the French answer without surprise. "
                            "Do not drop or add meaning-bearing details such as articles, number, negation, possession, size words, color words, or other modifiers. "
                            "Do not let a broad location phrase in English drift into a more specific French phrase, or vice versa. "
                            "For example, 'He sees Medusa in the mirror' must align with 'Il voit Méduse dans le miroir', while 'Il voit Méduse dans le reflet du miroir' must align with 'He sees Medusa in the reflection of the mirror'. "
                            "Likewise, if the French says 'sur l'île', the English should reflect 'on the island', not a broader or different location relation. "
                            "If the English says 'a' or 'the', do not let the French drift to a different article meaning. "
                            "If the English includes an adjective like 'small', 'old', or 'red', the French must preserve it. "
                            "If the French includes a meaning detail that the English is missing, add it to the English. "
                            "If the English includes a meaning detail that the French is missing, add it to the French. "
                            "If one side is in the wrong language, translate it into the correct language while preserving meaning. "
                            "Prefer minimal edits once the pair is fully aligned. "
                            "Keep the French natural and teachable. "
                            "Keep the English simple, direct, and learner-friendly. "
                            "Keep context_note concise and aligned with the final French. "
                            "Keep vocab_hints aligned with the final French wording. Remove or revise any hint that no longer matches. "
                            "Return the same number of sentences you received."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Difficulty: {difficulty}\n"
                            f"Sentence pairs to align:\n{json.dumps(payload_sentences, ensure_ascii=False)}"
                        ),
                    },
                ],
                text={"format": {"type": "json_schema", **schema}},
            )
            payload = json.loads(response.output_text)
            aligned = [LessonSentence(**item) for item in payload["sentences"]]
            for original, revised in zip(sentences, aligned, strict=False):
                revised.step = original.step
                if self._looks_like_target_language_text(revised.english, language) and self._looks_like_english_text(original.english):
                    revised.english = original.english
                if self._looks_like_english_text(revised.french) and self._looks_like_target_language_text(original.french, language):
                    revised.french = original.french
            return aligned
        except Exception:
            return sentences

    def _language_signal_score(self, text: str, signal_words: set[str]) -> int:
        normalized = normalize_french(text)
        tokens = normalized.split()
        score = sum(1 for token in tokens if token in signal_words)
        return score

    def _looks_like_target_language_text(self, text: str, language: str = "french") -> bool:
        lowered = text.lower()
        accent_bonus = 2 if re.search(r"[Ã Ã¢Ã§Ã©Ã¨ÃªÃ«Ã®Ã¯Ã´Ã»Ã¹Ã¼Ã¿Å“Ã¦Ã¡Ã­Ã³ÃºÃ±]", lowered) else 0
        apostrophe_bonus = 1 if language == "french" and re.search(r"\b[cdjlmnstqu]['â€™]", lowered) else 0
        target_score = self._language_signal_score(text, self._target_signal_words(language)) + accent_bonus + apostrophe_bonus
        english_score = self._language_signal_score(text, ENGLISH_SIGNAL_WORDS)
        return target_score >= max(2, english_score + 1)

    def _looks_like_french_text(self, text: str) -> bool:
        lowered = text.lower()
        accent_bonus = 2 if re.search(r"[àâçéèêëîïôûùüÿœæ]", lowered) else 0
        apostrophe_bonus = 1 if re.search(r"\b[cdjlmnstqu]['’]", lowered) else 0
        french_score = self._language_signal_score(text, FRENCH_SIGNAL_WORDS) + accent_bonus + apostrophe_bonus
        english_score = self._language_signal_score(text, ENGLISH_SIGNAL_WORDS)
        return french_score >= max(2, english_score + 1)

    def _looks_like_english_text(self, text: str) -> bool:
        english_score = self._language_signal_score(text, ENGLISH_SIGNAL_WORDS)
        french_score = self._language_signal_score(text, FRENCH_SIGNAL_WORDS)
        return english_score >= max(2, french_score + 1)

    def _repair_sentence_language_roles(self, sentences: list[LessonSentence], language: str = "french") -> list[LessonSentence]:
        repaired: list[LessonSentence] = []
        for sentence in sentences:
            english = (sentence.english or "").strip()
            french = (sentence.french or "").strip()

            if english and french and self._looks_like_target_language_text(english, language) and self._looks_like_english_text(french):
                sentence.english, sentence.french = french, english

            repaired.append(sentence)

        return repaired

    def _sanitize_lesson_title(self, title: str, theme: str) -> str:
        cleaned = (title or "").strip()
        cleaned = re.sub(r"\b(?:A1|A2|B1|B2|C1|C2)\b\s*[:-]?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\(\s*(?:A1|A2|B1|B2|C1|C2)\s*\)", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -:")
        if not cleaned:
            cleaned = theme.strip().title() or "Story"
        return cleaned

    def _lesson_system_prompt(self, language: str = "french") -> str:
        language_name = self._language_name(language)
        adjective_example = (
            "For adjective hints, the note should include both forms, such as 'adjective: masculine alto, feminine alta'. "
            if language == "spanish"
            else "For adjective hints, the note should include both forms, such as 'adjective: masculine grand, feminine grande'. "
        )
        return (
            f"You create high-quality {language_name} learning material. "
            "You must obey every user configuration exactly; none of them are optional suggestions. "
            f"Return connected English prompts with target {language_name} translations. "
            "The output must be one continuous lesson, not disconnected sentences. "
            "When story memory is supplied, treat freshness as a hard constraint, not a soft preference. "
            "You must compare the planned lesson against the supplied completed-story memory and avoid repeating the same basic story shape, setting, conflict, tone, or vocabulary domain. "
            "If an idea overlaps too closely with recent memory, discard it and choose a materially different one before writing. "
            "Match CEFR level exactly. "
            f"Use natural modern {language_name}. "
            "The lesson title must be in English. "
            "The lesson title must not include any CEFR or difficulty label such as A1, A2, B1, B2, C1, beginner, intermediate, or advanced. "
            f"Always include proper {language_name} accents in the target sentence and vocab hints. "
            "For each sentence, include 0 to 4 useful vocab hints for unusual, blocking, or non-obvious words. "
            "Be generous when a sentence contains multiple genuinely difficult words or phrases. "
            f"In each vocab hint, the 'english' field must be an English gloss, the 'french' field must be the {language_name} word or phrase, and the 'note' field must be written in English. "
            "For noun hints, the note should include grammatical gender, such as 'noun, masculine' or 'noun, feminine'. "
            + adjective_example +
            "For other parts of speech, keep the note short and useful only if it helps the learner. "
            "If the requested lesson type is dialogue, every line must visibly remain dialogue. "
            "If the requested lesson type is story, every line must visibly remain narration. "
            "If the requested lesson type is story, the lesson must have a real narrative arc with a beginning, development, and a meaningful ending. "
            "Do not produce stories that are just a list of related actions; something should happen, change, be revealed, be solved, or reach a clear stopping point by the end. "
            "When the requested theme points to a known myth, legend, fairy tale, historical episode, literary world, or other recognizable narrative tradition, prefer adapting a real canonical story, episode, or character situation from that tradition rather than inventing a merely style-adjacent plot. "
            "If the requested lesson type is film_scene, every line must feel cinematic and stay in the same scene. "
            "Do not ignore the theme. The theme must be obvious in the title and throughout the lesson."
        )

    def _lesson_constraints(self, request: LessonRequest) -> str:
        language_name = self._language_name(request.language)
        constraints = (
            "Create one lesson using these non-negotiable settings:\n"
            f"- Language: {language_name}\n"
            f"- Difficulty: {request.difficulty}\n"
            f"- Theme: {request.theme}\n"
            f"- Lesson type: {request.lesson_type}\n"
            f"- Sentence count: exactly {request.sentence_count}\n\n"
            "Hard constraints:\n"
            f"- {self._difficulty_guidance_for_language(request.difficulty, request.language)}\n"
            f"- {self._difficulty_guardrails(request.difficulty, request.language)}\n"
            f"- {self._lesson_type_guidance(request.lesson_type, request.theme)}\n"
            f"- The lesson title must reflect the theme '{request.theme}' and MUST be written in English.\n"
            "- The lesson title must not include the difficulty level or any CEFR tag.\n"
            f"- Produce exactly {request.sentence_count} sentences, no more and no fewer.\n"
            "- The English field must be the learner-facing prompt.\n"
            f"- The French field must contain the natural target {language_name} answer for that exact English prompt.\n"
            "- In every vocab hint, the english gloss and note must be written in English only.\n"
            f"- In every vocab hint, the french field must contain the {language_name} word or phrase only.\n"
            "- For noun hints, the note must include gender in English.\n"
            "- For adjective hints, the note must include both masculine and feminine forms.\n"
            f"- If the requested level is low, choose simpler {language_name} even if that makes the lesson less stylistically rich.\n"
            "- Every sentence must connect logically to the one before it.\n"
            "- Avoid generic filler. Make the theme obvious in the wording, setting, and actions.\n"
            "- For story mode, if the theme points to a known existing narrative world or tradition, adapt a recognizable canonical story, episode, or character situation from it whenever reasonably possible.\n"
            "- For story mode, do not default to an original story that merely imitates the theme's style if a real well-known source story would fit the request.\n"
            "- For story mode, the lesson must tell a story with a setup, a development, and a clear ending or payoff.\n"
            "- For story mode, the final sentence must feel like a genuine ending: it should resolve something, reveal something important, complete an action, or leave the story at a meaningful stopping point.\n"
            "- For story mode, avoid flat sequences where characters simply do one thing after another with no consequence, twist, goal, or resolution.\n"
            "- If story memory is supplied, the new lesson must feel like a genuinely fresh story compared with those entries, not a renamed variation of one of them.\n"
            "- If using dialogue, keep speaker labels consistent in both languages.\n"
            "- If using a film scene, keep the same setting and dramatic situation throughout.\n"
            f"- If a sentence contains two or more genuinely difficult {language_name} words or phrases, include hints for more than one of them instead of only choosing a single hint."
        )
        memory_guidance = build_story_memory_guidance(request.language)
        if memory_guidance:
            constraints += f"\n\n{memory_guidance}"
        return constraints

    def summarize_completed_story(self, request: StoryCompleteRequest) -> StoryMemoryEntry:
        if not request.sentences:
            raise RuntimeError("Cannot summarize an empty story.")
        if not self.enabled:
            return self._fallback_story_memory_entry(request)

        sentence_pairs = "\n".join(
            (
                f"Step {sentence.step} English: {sentence.english}\n"
                f"Step {sentence.step} {self._language_name(request.language)}: {sentence.french}"
            )
            for sentence in request.sentences
        )
        schema = {
            "name": "story_memory_summary",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "one_line_summary": {"type": "string"},
                    "synopsis": {"type": "string"},
                    "setting": {"type": "string"},
                    "tone": {"type": "string"},
                    "plot_beats": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                    "vocab_domains": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                    "grammar_focuses": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                    "freshness_note": {"type": "string"},
                },
                "required": [
                    "one_line_summary",
                    "synopsis",
                    "setting",
                    "tone",
                    "plot_beats",
                    "vocab_domains",
                    "grammar_focuses",
                    "freshness_note",
                ],
            },
        }

        try:
            response = self._responses_create_with_retry(
                **self._response_create_options(
                    model=self.lesson_model,
                    max_output_tokens=520,
                    reasoning_effort="low",
                ),
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize completed language-learning stories for future novelty control. "
                            "Return compact, concrete metadata describing what this story was about so future stories can avoid repeating it. "
                            "Be specific about setting, plot beats, vocabulary domains, and grammar focus. "
                            "Write everything in English. "
                            "Keep one_line_summary to one sentence. "
                            "Keep synopsis to 1-2 short sentences. "
                            "Plot beats should be broad narrative beats, not sentence-level paraphrases. "
                            "Vocab domains should be broad lexical fields like mythology, weather, travel, family, emotions, magic, food, movement, place words. "
                            "Grammar focuses should be broad learner-relevant areas like prepositions, negation, agreement, articles, common verbs, past tense, pronouns, or word order. "
                            "freshness_note should say what a future story should avoid repeating."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Language: {self._language_name(request.language)}\n"
                            f"Title: {request.title}\n"
                            f"Theme: {request.theme}\n"
                            f"Difficulty: {request.difficulty}\n"
                            f"Lesson type: {request.lesson_type}\n\n"
                            f"Story sentences:\n{sentence_pairs}"
                        ),
                    },
                ],
                text={"format": {"type": "json_schema", **schema}},
            )
            payload = json.loads(response.output_text)
            return StoryMemoryEntry(
                lesson_id=request.lesson_id,
                language=request.language,
                title=request.title,
                theme=request.theme,
                difficulty=request.difficulty,
                lesson_type=request.lesson_type,
                completed_at=datetime.now(UTC).isoformat(),
                one_line_summary=payload["one_line_summary"].strip(),
                synopsis=payload["synopsis"].strip(),
                setting=payload["setting"].strip(),
                tone=payload["tone"].strip(),
                plot_beats=[item.strip() for item in payload["plot_beats"] if item.strip()],
                vocab_domains=[item.strip() for item in payload["vocab_domains"] if item.strip()],
                grammar_focuses=[item.strip() for item in payload["grammar_focuses"] if item.strip()],
                freshness_note=payload["freshness_note"].strip(),
            )
        except Exception:
            return self._fallback_story_memory_entry(request)

    def _fallback_story_memory_entry(self, request: StoryCompleteRequest) -> StoryMemoryEntry:
        english_sentences = [sentence.english.strip() for sentence in request.sentences if sentence.english.strip()]
        synopsis = " ".join(english_sentences[:2]).strip() or request.theme
        one_line = synopsis if len(synopsis) <= 160 else synopsis[:157].rstrip() + "..."
        plot_beats = english_sentences[:3] if english_sentences else [request.theme]
        return StoryMemoryEntry(
            lesson_id=request.lesson_id,
            language=request.language,
            title=request.title,
            theme=request.theme,
            difficulty=request.difficulty,
            lesson_type=request.lesson_type,
            completed_at=datetime.now(UTC).isoformat(),
            one_line_summary=one_line,
            synopsis=one_line,
            setting=request.theme,
            tone="Not specified",
            plot_beats=plot_beats,
            vocab_domains=[request.theme],
            grammar_focuses=["General lesson review"],
            freshness_note=f"Avoid repeating the same setup as '{request.title}'.",
        )

    def suggest_story_theme(self, request: StorySuggestionRequest) -> StorySuggestionResponse:
        memory_guidance = build_story_memory_guidance(request.language)
        if not self.enabled:
            return self._fallback_story_suggestion(request, memory_guidance)

        schema = {
            "name": "story_suggestion",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "suggestion": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["suggestion", "rationale"],
            },
        }

        prompt_bits = [
            f"Language: {self._language_name(request.language)}",
            f"Difficulty: {request.difficulty}",
            f"Lesson type: {request.lesson_type}",
        ]
        if request.current_theme.strip():
            prompt_bits.append(f"Current theme in the input box: {request.current_theme.strip()}")
        if memory_guidance:
            prompt_bits.append("")
            prompt_bits.append(memory_guidance)

        try:
            response = self._responses_create_with_retry(
                **self._response_create_options(
                    model=self.lesson_model,
                    max_output_tokens=220,
                    reasoning_effort="low",
                ),
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You suggest fresh language-learning story themes. "
                            "Return one concise theme idea only, suitable for dropping directly into a theme input box. "
                            "The suggestion should be specific enough to inspire a vivid lesson, but short enough to fit in a compact form field. "
                            "Avoid repeating recent plots, settings, and vocabulary domains from the supplied memory. "
                            "Write the suggestion in English. "
                            "Keep it under 8 words when possible. "
                            "The rationale should be one short English sentence explaining why it feels fresh compared with recent stories."
                        ),
                    },
                    {
                        "role": "user",
                        "content": "\n".join(prompt_bits),
                    },
                ],
                text={"format": {"type": "json_schema", **schema}},
            )
            payload = json.loads(response.output_text)
            return StorySuggestionResponse(
                suggestion=payload["suggestion"].strip(),
                rationale=payload["rationale"].strip(),
            )
        except Exception:
            return self._fallback_story_suggestion(request, memory_guidance)

    def _fallback_story_suggestion(self, request: StorySuggestionRequest, memory_guidance: str = "") -> StorySuggestionResponse:
        language_label = "French" if request.language == "french" else "Spanish"
        lesson_type = request.lesson_type if request.lesson_type != "auto" else "story"
        memory_text = memory_guidance.lower()
        candidates = [
            "midnight train mystery",
            "storm lantern festival",
            "museum after closing",
            "marketplace mix-up",
            "lost map by the sea",
            "winter mountain rescue",
            "deserted cinema rehearsal",
            "garden maze secret",
            "moonlit bridge encounter",
            "library code puzzle",
        ]
        if "myth" in memory_text or "greek" in memory_text:
            candidates = [item for item in candidates if "maze" not in item and "map" not in item] + ["clockmaker in the rain"]
        if request.lesson_type == "dialogue":
            candidates = [
                "market negotiation gone wrong",
                "late train platform conversation",
                "cafe misunderstanding at dusk",
                "museum guard and visitor",
                "hotel check-in mix-up",
            ]
        elif request.lesson_type == "film_scene":
            candidates = [
                "rooftop chase at midnight",
                "silent station reunion",
                "rainy street handoff",
                "backstage panic before opening",
                "harbor lookout at dawn",
            ]
        suggestion = candidates[0]
        return StorySuggestionResponse(
            suggestion=suggestion,
            rationale=f"A fresh {language_label.lower()} {lesson_type} idea chosen to steer away from your recent completed stories.",
        )

    def _lesson_sentence_schema(self, min_items: int, max_items: int) -> dict[str, Any]:
        return {
            "type": "array",
            "minItems": min_items,
            "maxItems": max_items,
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
                        "maxItems": 4,
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
        }

    def _build_lesson_response(self, job: dict[str, Any]) -> LessonResponse:
        sentences = [LessonSentence(**sentence.model_dump()) if isinstance(sentence, LessonSentence) else LessonSentence(**sentence) for sentence in job["sentences"]]
        requested_count = job["request"].sentence_count
        return LessonResponse(
            lesson_id=job["lesson_id"],
            language=job["request"].language,
            title=job["title"],
            difficulty=job["request"].difficulty,
            theme=job["request"].theme,
            lesson_type=job["request"].lesson_type,
            source="openai",
            requested_sentence_count=requested_count,
            available_sentence_count=len(sentences),
            is_complete=job["status"] == "ready" and len(sentences) >= requested_count,
            status=job["status"],
            error_message=job["error_message"],
            sentences=sentences,
        )

    def _resolve_lesson_job(self, job: dict[str, Any]) -> None:
        future: Future[LessonSentence] | None = job.get("future")
        if future is None or job["status"] != "generating" or not future.done():
            return

        try:
            next_sentence = future.result()
        except Exception as exc:
            job["status"] = "failed"
            job["error_message"] = (
                "The lesson started, but the next sentence failed to generate. "
                "Please try generating a new lesson."
            )
            job["future"] = None
            job["background_exception"] = exc
            return

        job["sentences"].append(next_sentence)
        job["error_message"] = ""
        job["future"] = None
        self._schedule_next_lesson_sentence(job)

    def _generate_lesson_with_background_continuation(self, request: LessonRequest, lesson_id: str) -> LessonResponse:
        title, first_sentence = self._generate_lesson_openai_initial(request)
        job: dict[str, Any] = {
            "lesson_id": lesson_id,
            "request": request,
            "title": title,
            "sentences": [first_sentence],
            "status": "generating",
            "error_message": "",
            "future": None,
        }

        self._schedule_next_lesson_sentence(job)

        with self.lesson_jobs_lock:
            self.lesson_jobs[lesson_id] = job
        return self._build_lesson_response(job)

    def _schedule_next_lesson_sentence(self, job: dict[str, Any]) -> None:
        request: LessonRequest = job["request"]
        if len(job["sentences"]) >= request.sentence_count:
            job["status"] = "ready"
            job["future"] = None
            return

        title: str = job["title"]
        existing_sentences = [
            LessonSentence(**sentence.model_dump()) if isinstance(sentence, LessonSentence) else LessonSentence(**sentence)
            for sentence in job["sentences"]
        ]
        job["status"] = "generating"
        job["future"] = self.lesson_executor.submit(
            self._generate_lesson_openai_next_sentence,
            request,
            title,
            existing_sentences,
        )

    def _generate_lesson_openai_initial(self, request: LessonRequest) -> tuple[str, LessonSentence]:
        schema = {
            "name": "lesson_first_step",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "sentence": self._lesson_sentence_schema(1, 1)["items"],
                },
                "required": ["title", "sentence"],
            },
        }

        response = self._responses_create_with_retry(
            **self._response_create_options(
                model=self.lesson_model,
                max_output_tokens=max(320, min(self.lesson_max_output_tokens, 520)),
                reasoning_effort=self.lesson_reasoning_effort,
            ),
            input=[
                {"role": "system", "content": self._lesson_system_prompt(request.language)},
                {
                    "role": "user",
                    "content": (
                        f"{self._lesson_constraints(request)}\n\n"
                        "Return only the lesson title and sentence 1 for now.\n"
                        "Sentence 1 must feel like a strong opening and leave room for the lesson to continue naturally.\n"
                        "The sentence.step value must be exactly 1."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )

        payload = json.loads(response.output_text)
        first_sentence = LessonSentence(**payload["sentence"])
        first_sentence.step = 1
        first_sentence = self._repair_sentence_language_roles([first_sentence], request.language)[0]
        first_sentence = self._align_sentence_pairs([first_sentence], request.difficulty, request.language)[0]
        first_sentence = self._enrich_vocab_hints([first_sentence], request.difficulty, request.language)[0]
        return self._sanitize_lesson_title(payload["title"], request.theme), first_sentence

    def _generate_lesson_openai_remaining(
        self,
        request: LessonRequest,
        title: str,
        first_sentence: LessonSentence,
    ) -> list[LessonSentence]:
        remaining_count = request.sentence_count - 1
        schema = {
            "name": "lesson_remaining_steps",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sentences": self._lesson_sentence_schema(remaining_count, remaining_count),
                },
                "required": ["sentences"],
            },
        }

        response = self._responses_create_with_retry(
            **self._response_create_options(
                model=self.lesson_model,
                max_output_tokens=self.lesson_max_output_tokens,
                reasoning_effort=self.lesson_reasoning_effort,
            ),
            input=[
                {"role": "system", "content": self._lesson_system_prompt(request.language)},
                {
                    "role": "user",
                    "content": (
                        f"{self._lesson_constraints(request)}\n\n"
                        f"The lesson title is already fixed as: {title}\n"
                        "Sentence 1 has already been shown to the learner. Continue from it without rewriting it.\n"
                        f"Sentence 1 English: {first_sentence.english}\n"
                        f"Sentence 1 French: {first_sentence.french}\n"
                        f"Sentence 1 context note: {first_sentence.context_note}\n\n"
                        f"Return exactly the remaining {remaining_count} sentences only.\n"
                        f"The next sentence must start at step 2 and the last must end at step {request.sentence_count}.\n"
                        "Keep the same characters, situation, tone, and format. Do not reset the scene or conversation."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )

        payload = json.loads(response.output_text)
        sentences = [LessonSentence(**item) for item in payload["sentences"]]
        for step, sentence in enumerate(sentences, start=2):
            sentence.step = step
        sentences = self._repair_sentence_language_roles(sentences, request.language)
        sentences = self._align_sentence_pairs(sentences, request.difficulty, request.language)
        return self._enrich_vocab_hints(sentences, request.difficulty, request.language)

    def _generate_lesson_openai_next_sentence(
        self,
        request: LessonRequest,
        title: str,
        existing_sentences: list[LessonSentence],
    ) -> LessonSentence:
        next_step = len(existing_sentences) + 1
        schema = {
            "name": "lesson_next_step",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sentence": self._lesson_sentence_schema(1, 1)["items"],
                },
                "required": ["sentence"],
            },
        }

        prior_summary = "\n".join(
            (
                f"Sentence {sentence.step} English: {sentence.english}\n"
                f"Sentence {sentence.step} {self._language_name(request.language)}: {sentence.french}\n"
                f"Sentence {sentence.step} context note: {sentence.context_note}"
            )
            for sentence in existing_sentences
        )

        response = self._responses_create_with_retry(
            **self._response_create_options(
                model=self.lesson_model,
                max_output_tokens=max(320, min(self.lesson_max_output_tokens, 520)),
                reasoning_effort=self.lesson_reasoning_effort,
            ),
            input=[
                {"role": "system", "content": self._lesson_system_prompt(request.language)},
                {
                    "role": "user",
                    "content": (
                        f"{self._lesson_constraints(request)}\n\n"
                        f"The lesson title is already fixed as: {title}\n"
                        f"Sentences 1 to {len(existing_sentences)} have already been shown to the learner. Continue from them without rewriting them.\n\n"
                        f"{prior_summary}\n\n"
                        f"Return exactly sentence {next_step} only.\n"
                        f"The sentence.step value must be exactly {next_step}.\n"
                        "This new sentence must continue the same characters, situation, tone, and format naturally.\n"
                        "Do not recap the whole story. Do not jump ahead abruptly. Just write the immediate next beat."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )

        payload = json.loads(response.output_text)
        next_sentence = LessonSentence(**payload["sentence"])
        next_sentence.step = next_step
        next_sentence = self._repair_sentence_language_roles([next_sentence], request.language)[0]
        next_sentence = self._align_sentence_pairs([next_sentence], request.difficulty, request.language)[0]
        next_sentence = self._enrich_vocab_hints([next_sentence], request.difficulty, request.language)[0]
        return next_sentence

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
            **self._response_create_options(
                model=self.lesson_model,
                max_output_tokens=self.lesson_max_output_tokens,
                reasoning_effort=self.lesson_reasoning_effort,
            ),
            input=[
                {
                    "role": "system",
                    "content": (
                        "You create high-quality French learning material. "
                        "You must obey every user configuration exactly; none of them are optional suggestions. "
                        "Return a sequence of connected English prompts with target French translations. "
                        "The output must be one continuous lesson, not disconnected sentences. "
                        "Match CEFR level exactly. "
                        "Use natural modern French. "
                        "Always include proper French accents in the target French and vocab hints. "
                        "For each sentence, include only 0 to 3 useful vocab hints for unusual or blocking words. "
                        "If the requested lesson type is dialogue, every line must visibly remain dialogue. "
                        "If the requested lesson type is story, every line must visibly remain narration. "
                        "If the requested lesson type is film_scene, every line must feel cinematic and stay in the same scene. "
                        "Do not ignore the theme. The theme must be obvious in the title and throughout the lesson."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Create one lesson using these non-negotiable settings:\n"
                        f"- Difficulty: {request.difficulty}\n"
                        f"- Theme: {request.theme}\n"
                        f"- Lesson type: {request.lesson_type}\n"
                        f"- Sentence count: exactly {request.sentence_count}\n\n"
                        "Hard constraints:\n"
                        f"- {self._difficulty_guidance(request.difficulty)}\n"
                        f"- {self._lesson_type_guidance(request.lesson_type, request.theme)}\n"
                        f"- The lesson title must reflect the theme '{request.theme}'.\n"
                        f"- Produce exactly {request.sentence_count} sentences, no more and no fewer.\n"
                        "- The English field must be the learner-facing prompt.\n"
                        "- The French field must be the natural target answer for that exact English prompt.\n"
                        "- Every sentence must connect logically to the one before it.\n"
                        "- Avoid generic filler. Make the theme obvious in the wording, setting, and actions.\n"
                        "- If using dialogue, keep speaker labels consistent in both languages.\n"
                        "- If using a film scene, keep the same setting and dramatic situation throughout."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )

        payload = json.loads(response.output_text)
        sentences = [LessonSentence(**item) for item in payload["sentences"]]
        sentences = self._repair_sentence_language_roles(sentences, request.language)
        sentences = self._align_sentence_pairs(sentences, request.difficulty, request.language)
        sentences = self._enrich_vocab_hints(sentences, request.difficulty, request.language)
        return LessonResponse(
            lesson_id=lesson_id,
            language=request.language,
            title=self._sanitize_lesson_title(payload["title"], request.theme),
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
                    "meaning_equivalent": {"type": "boolean"},
                    "has_required_construction_issue": {"type": "boolean"},
                    "required_construction_note": {"type": "string"},
                    "reminder_key": {"type": "string"},
                    "reminder_label": {"type": "string"},
                    "reminder_explanation": {"type": "string"},
                    "reminder_wrong_pattern": {"type": "string"},
                    "reminder_correct_pattern": {"type": "string"},
                    "reminder_wrong_focus": {"type": "string"},
                    "reminder_correct_focus": {"type": "string"},
                    "model_is_correct": {"type": "boolean"},
                    "model_correctness_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "verdict": {"type": "string"},
                    "accepted_learner_sentence": {"type": "string"},
                    "suggested_sentence": {"type": "string"},
                    "more_common_sentence": {"type": "string"},
                    "tips": {"type": "array", "items": {"type": "string"}},
                    "mistakes": {"type": "array", "items": {"type": "string"}},
                    "learner_token_labels": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["correct", "acceptable", "wrong"]},
                    },
                    "learner_display_tokens": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "text": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["correct", "acceptable", "wrong", "missing", "neutral"],
                                },
                            },
                            "required": ["text", "status"],
                        },
                    },
                    "encouraging_note": {"type": "string"},
                },
                "required": [
                    "meaning_equivalent",
                    "has_required_construction_issue",
                    "required_construction_note",
                    "reminder_key",
                    "reminder_label",
                    "reminder_explanation",
                    "reminder_wrong_pattern",
                    "reminder_correct_pattern",
                    "reminder_wrong_focus",
                    "reminder_correct_focus",
                    "model_is_correct",
                    "model_correctness_score",
                    "verdict",
                    "accepted_learner_sentence",
                    "suggested_sentence",
                    "more_common_sentence",
                    "tips",
                    "mistakes",
                    "learner_token_labels",
                    "learner_display_tokens",
                    "encouraging_note",
                ],
            },
        }

        payload = None
        last_output_text = ""
        for attempt in range(2):
            response = self._responses_create_with_retry(
                **self._response_create_options(
                    model=self.eval_model,
                    max_output_tokens=max(520, min(self.eval_max_output_tokens + (120 if attempt else 0), 760)),
                    reasoning_effort=self.eval_reasoning_effort,
                ),
                input=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a precise but encouraging {self._language_name(request.language)} tutor. "
                            f"Evaluate a learner's {self._language_name(request.language)} translation of an English sentence. "
                            f"Do not treat the supplied target {self._language_name(request.language)} sentence as the only acceptable wording. "
                            "Use it as a meaning-and-lesson reference, not as a mandatory token sequence. "
                            "The English prompt is the ultimate meaning authority. "
                            "If the supplied target sentence accidentally omits a meaning-bearing detail that is present in the English prompt, do not inherit that omission. "
                            "In that case, suggested_sentence and learner_display_tokens should still reflect the full English meaning. "
                            "First decide what the learner was trying to say and whether that wording is acceptable. "
                            "Treat missing accents as fully acceptable if the sentence is otherwise correct, and do not mention missing accents in the feedback. "
                            "This includes cedillas such as 'c' versus 'ç'. "
                            "Treat capitalization differences in the learner's input as fully acceptable and do not mention capitalization in the feedback. "
                            "Ignore uppercase versus lowercase completely, including in names and sentence starts. "
                            "Do not tell the learner to capitalize anything. "
                            "Treat punctuation differences in the learner's input as fully acceptable unless they change meaning. "
                            "Do not mention apostrophes, punctuation, quote style, commas, or sentence-final punctuation in feedback. "
                            "Ignore orthography-only differences other than genuine spelling mistakes. "
                            "Never give a note that is only about accents, punctuation, capitalization, or the accented form of a proper name. "
                            "If a learner writes an unaccented form like 'Thesee' for 'Thésée', treat that as acceptable orthography, not as an error. "
                            "If the learner answer differs from the target only by accents, capitalization, apostrophes, or punctuation, treat it as fully correct. "
                            "Do not reduce correctness, naturalness, or confidence for those differences. "
                            "In that case, return no corrective tips or mistakes, use a fully positive verdict, and label the learner tokens as correct. "
                            "Accept valid paraphrases. "
                            "The learner does not need to use the exact same vocabulary as the target or the vocab hints. "
                            "If the learner uses a different but valid synonym or paraphrase that preserves the same meaning, treat it as correct in meaning. "
                            "If the learner uses a less common but still natural wording, accept it and preserve it. "
                            "Do not criticize a learner just for choosing a different valid word than the vocab hint suggested. "
                            "However, if the target uses a required French construction, contraction, or fixed phrase and the learner breaks it, do not mark the answer as meaning-equivalent. "
                            "Examples include mandatory contractions like au, aux, du, and fixed constructions like en espèces. "
                            "When that happens, set has_required_construction_issue to true and write one short English note in required_construction_note explaining the needed target construction. "
                            "When there is no such issue, set has_required_construction_issue to false and required_construction_note to an empty string. "
                            f"If the learner uses a different but fully acceptable {self._language_name(request.language)} wording, set accepted_learner_sentence to a polished version of the learner's own wording with proper accents and punctuation. "
                            "If the learner's wording is not acceptable as the displayed answer, set accepted_learner_sentence to an empty string. "
                            "Treat suggested_sentence as the main sentence that will be shown to the learner in the feedback UI. "
                            "Set suggested_sentence to the minimally corrected version of the learner's answer. "
                            "Preserve as much of the learner's valid wording and phrasing as possible in suggested_sentence; only change what truly needs correcting. "
                            "Do not simply copy the canonical target sentence into suggested_sentence unless that really is the minimal natural correction. "
                            "If the learner used a valid but less common verb or phrase, keep that valid wording in suggested_sentence rather than replacing it with a preferred synonym. "
                            "Use more_common_sentence only for an optional more standard alternative, not as the main visible correction. "
                            "For example, if 'construisent' is acceptable and you merely prefer 'fabriquent', keep 'construisent' in suggested_sentence and put 'fabriquent' only in more_common_sentence if you mention it at all. "
                            "Set more_common_sentence only when there is a distinctly more standard or lesson-aligned wording that is still worth showing; otherwise repeat suggested_sentence. "
                            "All visible outputs must be internally consistent: learner_display_tokens, mistakes/tips, suggested_sentence, more_common_sentence, and any reminder pattern must all describe the same actual correction. "
                            "Token-level colouring must stay consistent with the corrected sentence you return. "
                            "If a learner token is still acceptable and survives unchanged into suggested_sentence, do not mark that token as wrong. "
                            "If a learner token is replaced by a different corrected token in suggested_sentence, do not mark the learner token as correct. "
                            "A genuine spelling mistake or wrong word that changes to a different corrected token must be marked wrong or, if truly borderline, acceptable, but never correct. "
                            "For example, if the learner writes 'citte' and the corrected sentence uses 'cité', then 'citte' must not be green. "
                            "Only mark the actual changed token or phrase as wrong. "
                            "For example, if the learner writes 'un wagon vide avec une lumiere single' and your correction is 'un wagon vide avec une seule lumière', then 'wagon' and 'vide' should stay correct; only the bad local phrase around 'single' should be wrong. "
                            "Do not spread the wrong marking leftward or rightward onto neighboring words that remain valid in the correction. "
                            "If the learner made a repeatable kind of mistake that would be useful to track over time, return a reminder_key, reminder_label, reminder_explanation, reminder_wrong_pattern, reminder_correct_pattern, reminder_wrong_focus, and reminder_correct_focus. "
                            "Only do this for broad recurring patterns, not one-off lexical choices tied to a specific sentence. Return at most one reminder pattern. "
                            "Be conservative. If there is any real doubt about whether the learner produced a genuine repeatable grammar or usage pattern, return no reminder pattern at all. "
                            "Prefer broad category buckets rather than narrow micro-categories. "
                            "Good reminder buckets include Prepositions, Articles, Pronouns, Word order, Verbs, Agreement, Negation, Small words, and Spelling. "
                            "Choose the single best category. Distinguish carefully between spelling, conjugation, agreement, article choice, and preposition choice. "
                            "Make reminder_key short, stable, and snake_case, like prepositions, verbs, word_order, or spelling. "
                            "Make reminder_label broad and learner-friendly, ideally matching one of those bucket-style categories. "
                            "Do not make reminder_label too narrow or sentence-specific. "
                            "Use reminder_explanation only as a short internal summary of the pattern; the app may choose not to display it directly. "
                            "For reminder_wrong_pattern and reminder_correct_pattern, write the generalized wrong form and the generalized corrected form in the target language itself, not in English. "
                            "They must include enough context to make the linguistic pattern fully clear. "
                            "Keep the essential subject, noun, article, preposition, pronoun, or governing phrase whenever needed. "
                            "The pattern should be understandable and teachable on its own, without needing to see the original sentence. "
                            "Do not over-compress the pattern down to just the changed word if that loses the grammar context. "
                            "For verbs, keep the subject when it matters for the conjugation. "
                            "For articles or agreement, keep the noun when that is what makes the pattern meaningful. "
                            "For prepositions, keep the governing word or phrase that licenses the preposition. "
                            "Never return a bare conjugation fragment like 'vais' -> 'va' when the subject is what makes the pattern meaningful; prefer 'Thésée vais' -> 'Thésée va' or 'je vais' -> 'il va' style context as appropriate. "
                            "In general, if the changed word would be ambiguous on its own, expand the pattern until the grammatical role is obvious. "
                            "Good examples are 'il ont des' -> 'il a des', 'j'achete de la pain' -> 'j'achete du pain', and 'entrer la maison' -> 'entrer dans la maison'. "
                            "Do not return vague fragments like 'a' -> 'en' if fuller context is needed to understand the pattern. "
                            "Bad examples are fragments like 'vais' -> 'va' when 'Thésée vais' -> 'Thésée va' would make the pattern clearer. "
                            "Do not create reminder patterns for nonsense, off-topic, placeholder, joke, or low-effort answers such as random words, greetings, or unrelated text. "
                            "Do not turn a whole wrong sentence into a reminder pattern unless there is one clear localized grammar or usage pattern inside it. "
                            "For reminder_wrong_focus and reminder_correct_focus, return just the key part inside those patterns that should be visually emphasized, such as 'de la' -> 'du', 'ont' -> 'a', or 'dans' -> 'en'. "
                            "Each focus string must appear verbatim inside its corresponding pattern string. "
                            "If there is no useful repeatable pattern, set reminder_key, reminder_label, reminder_explanation, reminder_wrong_pattern, reminder_correct_pattern, reminder_wrong_focus, and reminder_correct_focus to empty strings. "
                            "Only raise naturalness or idiomaticity issues when the learner's wording sounds clearly awkward, noticeably non-native, or distinctly less natural than standard everyday French. "
                            "Do not nitpick between two clearly natural, common phrasings that mean the same thing. "
                            "If the learner's French is already natural, do not offer a tiny stylistic swap as correction. "
                            "Prefer under-correcting to over-correcting on small style differences. "
                            f"Treat the target {self._language_name(request.language)} and supplied vocab hints as canonical lesson language. "
                            f"Do not criticize, replace, or second-guess vocabulary that appears in the target {self._language_name(request.language)} or vocab hints unless it is genuinely ungrammatical. "
                            "Write every feedback field in English only, including the verdict, tips, mistakes, and encouraging note. "
                            "Do not write any feedback notes in French unless you are quoting a French example sentence or phrase. "
                            "Do not mention missing accents, accent marks, or diacritics anywhere in the feedback. "
                            "Be very concise. "
                            "Verdict must be short, ideally 2 to 9 words. "
                            "Each tip or mistake must be a single short sentence, ideally under 12 words. "
                            "Prefer clear issues over long explanations. "
                            "Do not repeat the same correction in both tips and mistakes. "
                            "If article, gender, or one small grammar word is the issue, mention it once only. "
                            "Do not produce two notes that restate the same problem in different words. "
                            "It is fine to return multiple notes when they cover distinct issues. "
                            "Do not return two notes that point to the same underlying correction with different wording. "
                            "If several comments would all be fixed by the same corrected word or phrase, return only one of them. "
                            "Never give two lexical notes about the same target word or phrase. "
                            f"Anchor every correction to the target {self._language_name(request.language)}, not to an incorrect learner phrase. "
                            "Do not invent grammar patterns from the learner's wrong wording if those patterns are absent from the target sentence. "
                            "If the learner response is mostly unusable or unrelated, prefer no reminder pattern over a bad one. "
                            "Also return learner_token_labels for the learner answer tokens split by spaces. "
                            "Return exactly one label per learner token, in order. "
                            "Also return learner_display_tokens for exactly how the learner answer should be shown in the feedback UI. "
                            "Each learner_display_tokens item must have text and status. "
                            "Keep the learner's submitted tokens in their original order for submitted words. "
                            "Localize error marking as tightly as possible. "
                            "If only one word or short phrase is wrong, mark only that word or phrase as wrong, and keep the surrounding correct continuation tokens as correct. "
                            "Do not let a local error cause the whole remaining tail of the sentence to become wrong. "
                            "For example, if the learner wrote 'sur la mer' where 'au-dessus de la mer' is needed, mark the incorrect local span as wrong, but keep later tokens like 'et', 'le', 'heros', 'est', and 'content' as correct if they are otherwise fine. "
                            "Likewise, if the learner wrote 'ils appliquent le cire sur les ailes' and your correction is 'ils appliquent de la cire sur les ailes', the wrong marking should stay on the local article phrase around 'le cire'; later tokens like 'sur', 'les', and 'ailes' should remain correct if they still fit the corrected sentence. "
                            "Use 'wrong' only for the actual incorrect token or phrase, not for nearby words that are acceptable on their own. "
                            "Only insert a token with status 'missing' when a target word was truly omitted and there was no recognizable learner attempt at it nearby. "
                            "If the learner attempted the word but got it wrong, keep the learner's attempted token with status 'wrong' instead of inserting a missing token. "
                            "For example, if the learner wrote an article attempt like 'la' or 'une' in the relevant slot, do not also invent an omitted article token. "
                            "If there are no genuine omissions, learner_display_tokens should just cover the learner's submitted tokens. "
                            "If the learner clearly attempts a target word with the wrong inflection, spelling, or agreement, treat it as an attempted wrong token, not as an omitted word. "
                            "For example, a close attempt like 'vais' for 'va' is not an omission of 'va'. "
                            "Never treat a target word as omitted when the learner has already made a recognizable attempt at that same word nearby. "
                            "Do not mark a word as omitted if the learner used a valid synonym or alternate phrasing instead. "
                            "But if a meaning-bearing word is genuinely absent and there was no attempt at it, you should insert it into learner_display_tokens with status 'missing' at the exact place where it belongs. "
                            "For example, if the learner writes 'un homme veut voler a une ile lointaine' and the intended correction is 'un jeune homme veut voler vers une île lointaine', then learner_display_tokens should include a missing token for 'jeune' before 'homme', while the submitted token 'a' should remain as a wrong attempted token rather than causing the rest of the sentence tail to be marked wrong. "
                            "Likewise, if the English prompt says 'a young hero' but the supplied target sentence mistakenly says only 'un héros', you should still treat 'jeune' as part of the intended meaning and include it as missing if the learner omitted it. "
                            "Likewise, if the learner writes 'un homme construisent des ailes a voler sur l'ile' and the intended correction is 'un jeune homme construit des ailes pour voler vers l'île', then learner_display_tokens should still include a missing token for 'jeune' before 'homme'. "
                            "In that case, do not skip the missing adjective just because there are other errors elsewhere in the sentence. "
                            "Likewise, if the learner writes 'un berger rencontre Apollon au bord de la mer' and the intended correction is 'un jeune berger rencontre Apollon au bord de la mer', then learner_display_tokens must include a missing token for 'jeune' before 'berger'. "
                            "In that case, the later phrase 'rencontre Apollon au bord de la mer' should remain correct, because it survives unchanged into the correction. "
                            "Do not let a single missing adjective near the start of the sentence cause the whole remaining tail to become wrong. "
                            "When the correction only inserts one missing word and leaves a later phrase unchanged, keep that unchanged later phrase marked correct in learner_display_tokens. "
                            "Use 'correct' for tokens that are right as written. "
                            "Use 'acceptable' sparingly, only when a token is clearly acceptable but noticeably not the target phrasing. "
                            "Use 'wrong' for incorrect tokens. "
                            "If the learner answer is valid overall, prefer 'correct' unless marking a token as merely 'acceptable' would genuinely help the learner. "
                            "Do not overuse 'acceptable' for ordinary synonyms or simple valid rephrasings. "
                            "For example, if a simpler verb still preserves the meaning naturally, prefer 'correct' rather than 'acceptable'. "
                            "Do not mark genuinely wrong tokens as acceptable. "
                            "Return model_is_correct as your overall pass/fail judgment for the learner answer. "
                            "Return model_correctness_score as your own 0-100 overall accuracy judgment, taking meaning, grammar, and omissions into account. "
                            "Calibrate this score proportionally. "
                            "If the learner preserves most of the sentence correctly and the problem is one localized article, adjective, spelling, agreement, or word-choice issue, do not score it as harshly as a meaning-level failure. "
                            "Reserve very low scores for answers with major meaning problems, several independent errors, or badly broken grammar. "
                            "If the sentence is mostly right and only one short phrase needs correction, the score should usually stay noticeably above the low-60s range. "
                            "For example, if the learner writes a sentence that is otherwise correct but uses 'ors' where 'dorées' is needed, treat that as a localized lexical/agreement issue rather than a broad failure of the whole sentence. "
                            "Keep the encouraging note very short, or leave it empty if unnecessary. "
                            "Keep tips concise and practical. "
                            "The backend will lightly sanity-check your structure, but you own the actual marking decisions."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Difficulty: {request.difficulty}\n"
                            f"English prompt: {request.english}\n"
                            f"Target {self._language_name(request.language)}: {request.target_sentence}\n"
                            f"Context note: {request.context_note}\n"
                            f"Canonical vocab hints: {', '.join(f'{hint.french} = {hint.english}' for hint in request.vocab_hints) or 'None'}\n"
                            f"Learner answer: {request.learner_answer}\n"
                            f"Learner tokens (split by spaces): {json.dumps([part for part in re.split(r'\\s+', request.learner_answer.strip()) if part], ensure_ascii=False)}\n"
                            "Judge meaning, grammar, and naturalness."
                        ),
                    },
                ],
                text={"format": {"type": "json_schema", **schema}},
            )
            last_output_text = response.output_text or ""
            try:
                payload = json.loads(response.output_text)
                break
            except json.JSONDecodeError:
                if attempt == 1:
                    snippet = " ".join(last_output_text.split())
                    if len(snippet) > 1200:
                        snippet = snippet[:1200] + "...[truncated]"
                    raise RuntimeError(
                        "Answer evaluation failed because the model returned an invalid structured response. "
                        f"Raw model output: {snippet}"
                    )
                time.sleep(0.35)

        if payload is None:
            raise RuntimeError("Answer evaluation failed to return structured JSON.")
        payload = self._sanitize_feedback_payload(payload, request.language)
        learner_normalized = normalize_french(request.learner_answer)
        target_normalized = normalize_french(request.target_sentence)
        model_is_correct = bool(payload.pop("model_is_correct", False))
        model_correctness_score = int(payload.pop("model_correctness_score", 0) or 0)
        model_correctness_score = max(0, min(100, model_correctness_score))
        orthography_equivalent = self._is_orthography_equivalent(
            request.learner_answer,
            request.target_sentence,
        )
        correctness_score = model_correctness_score
        is_correct = model_is_correct
        if orthography_equivalent:
            payload = {
                **payload,
                "meaning_equivalent": True,
                "verdict": "Correct and natural.",
                "accepted_learner_sentence": polish_learner_french(request.learner_answer),
                "suggested_sentence": request.target_sentence,
                "more_common_sentence": request.target_sentence,
                "tips": [],
                "mistakes": [],
                "learner_token_labels": ["correct" for token in re.split(r"\s+", request.learner_answer.strip()) if token],
                "learner_display_tokens": [
                    {"text": token, "status": "correct"}
                    for token in re.split(r"\s+", request.learner_answer.strip()) if token
                ],
                "encouraging_note": "",
            }
            correctness_score = 100
            is_correct = True
        elif payload.get("has_required_construction_issue"):
            payload["accepted_learner_sentence"] = ""
            is_correct = False
            correctness_score = min(correctness_score, 84)

        if payload.get("meaning_equivalent") and not payload.get("has_required_construction_issue"):
            correctness_score = max(correctness_score, 90 if is_correct else correctness_score)
        if is_correct and not (payload.get("accepted_learner_sentence") or "").strip():
            payload["accepted_learner_sentence"] = polish_learner_french(request.learner_answer)
        accepted_learner_normalized = normalize_french(payload.get("accepted_learner_sentence", ""))
        if accepted_learner_normalized and accepted_learner_normalized == learner_normalized:
            payload = {
                **payload,
                "meaning_equivalent": True,
                "verdict": "Correct and natural.",
                "tips": [],
                "mistakes": [],
                "learner_token_labels": ["correct" for token in re.split(r"\s+", request.learner_answer.strip()) if token],
                "learner_display_tokens": [
                    {"text": token, "status": "correct"}
                    for token in re.split(r"\s+", request.learner_answer.strip()) if token
                ],
                "encouraging_note": "",
            }
            correctness_score = max(correctness_score, 96)
            is_correct = True
        if not payload.get("meaning_equivalent") and not is_correct:
            payload["accepted_learner_sentence"] = ""
        payload["learner_token_labels"] = self._sanitize_token_labels(
            payload.get("learner_token_labels"),
            request.learner_answer,
            request.target_sentence,
        ) or self._build_fallback_token_labels(
            request.learner_answer,
            request.target_sentence,
            is_correct=is_correct,
        )
        payload["learner_display_tokens"] = self._sanitize_learner_display_tokens(
            payload.get("learner_display_tokens"),
            request.learner_answer,
            request.target_sentence,
            payload.get("learner_token_labels"),
        ) or self._build_fallback_display_tokens(
            request.learner_answer,
            payload.get("learner_token_labels"),
        )
        payload["learner_display_tokens"] = self._enforce_learner_display_tokens(payload, request)
        return EvaluationResponse(
            is_correct=is_correct,
            correctness_score=correctness_score,
            learner_normalized=normalize_french(request.learner_answer),
            target_normalized=normalize_french(request.target_sentence),
            reminders_triggered=[],
            source="openai",
            **payload,
        )

    def _lookup_phrase_entry(self, phrase: str, language: str = "french") -> dict[str, str] | None:
        normalized = normalize_french(phrase)
        if not normalized:
            return None
        phrase_dictionary = self.phrase_dictionaries.get(language, {})
        if normalized in phrase_dictionary:
            return phrase_dictionary[normalized]

        lemma = self.verb_base_forms.get(normalized)
        if lemma and normalize_french(lemma) in phrase_dictionary:
            entry = phrase_dictionary[normalize_french(lemma)]
            return {
                "english_meaning": entry["english_meaning"],
                "usage_note": f"{entry['usage_note']} This form comes from '{lemma}'.",
            }

        if normalized.endswith("s") and normalized[:-1] in phrase_dictionary:
            return phrase_dictionary[normalized[:-1]]

        return None

    def _explain_phrase_local(self, request: PhraseExplainRequest) -> PhraseExplainResponse:
        selected_normalized = normalize_french(request.selected_text)

        for hint in request.vocab_hints:
            if normalize_french(hint.french) == selected_normalized:
                return PhraseExplainResponse(
                    language=request.language,
                    selected_text=request.selected_text,
                    english_meaning=hint.english,
                    usage_note=hint.note or "Useful vocabulary from this sentence.",
                    save_note=f"From: {request.english_sentence}",
                    source="dictionary",
                )

        dictionary_entry = self._lookup_phrase_entry(request.selected_text, request.language)
        if dictionary_entry is not None:
            return PhraseExplainResponse(
                language=request.language,
                selected_text=request.selected_text,
                english_meaning=dictionary_entry["english_meaning"],
                usage_note=dictionary_entry.get("usage_note", ""),
                save_note=f"From: {request.english_sentence}",
                source="dictionary",
            )

        phrase_tokens = tokenize_french_context(request.selected_text)
        if len(phrase_tokens) > 1:
            token_entries = [self._lookup_phrase_entry(token, request.language) for token in phrase_tokens]
            known_tokens = [entry["english_meaning"] for entry in token_entries if entry is not None]
            if known_tokens:
                return PhraseExplainResponse(
                    language=request.language,
                    selected_text=request.selected_text,
                    english_meaning=" / ".join(known_tokens),
                    usage_note="Combined from the local dictionary because this exact phrase was not stored yet.",
                    save_note=f"From: {request.english_sentence}",
                    source="dictionary",
                )

        return PhraseExplainResponse(
            language=request.language,
            selected_text=request.selected_text,
            english_meaning=f"Sentence-specific meaning of '{request.selected_text}'",
            usage_note="No exact entry was found in the local dictionary yet, so use the surrounding sentence for context.",
            save_note=f"From: {request.english_sentence}",
            source="dictionary",
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
            **self._response_create_options(
                model=self.eval_model,
                max_output_tokens=self.explain_max_output_tokens,
                reasoning_effort=self.eval_reasoning_effort,
            ),
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
                        f"Target sentence: {request.target_sentence}\n"
                        f"Selected text: {request.selected_text}\n"
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
            language=request.language,
            selected_text=request.selected_text,
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

    def _generate_lesson_fallback_strict(self, request: LessonRequest, lesson_id: str) -> LessonResponse:
        fallback_type = self._resolve_fallback_lesson_type(request)
        level_key = "B1" if request.difficulty in {"B1", "B2", "C1"} else "A1"
        theme = request.theme
        fallback_lessons: dict[str, dict[str, dict[str, Any]]] = {
            "story": {
                "A1": {
                    "title": f"{theme.title()} Story",
                    "sentences": [
                        {"step": 1, "english": f"I arrive at a place connected to {theme}.", "french": f"J'arrive dans un endroit lié à {theme}.", "context_note": "Simple present narration tied directly to the chosen theme.", "vocab_hints": []},
                        {"step": 2, "english": "I notice one important detail right away.", "french": "Je remarque tout de suite un détail important.", "context_note": "Simple observation in sequence.", "vocab_hints": []},
                        {"step": 3, "english": "A person comes over and speaks to me.", "french": "Une personne s'approche et me parle.", "context_note": "Basic sequential action.", "vocab_hints": []},
                        {"step": 4, "english": f"We talk about {theme}.", "french": f"Nous parlons de {theme}.", "context_note": "Theme is stated explicitly so it cannot be ignored.", "vocab_hints": []},
                        {"step": 5, "english": "I ask a simple question.", "french": "Je pose une question simple.", "context_note": "Common present-tense action.", "vocab_hints": []},
                        {"step": 6, "english": "The answer changes what I want to do next.", "french": "La réponse change ce que je veux faire ensuite.", "context_note": "Cause and effect in simple language.", "vocab_hints": []},
                        {"step": 7, "english": "I make a decision and move forward.", "french": "Je prends une décision et j'avance.", "context_note": "Simple concluding action.", "vocab_hints": []},
                        {"step": 8, "english": "At the end, the situation feels clearer.", "french": "À la fin, la situation semble plus claire.", "context_note": "Natural closing line.", "vocab_hints": []},
                    ],
                },
                "B1": {
                    "title": f"The {theme.title()} Mystery",
                    "sentences": [
                        {"step": 1, "english": f"On my way home, I get pulled into something connected to {theme}.", "french": f"En rentrant chez moi, je me retrouve mêlé à quelque chose lié à {theme}.", "context_note": "B1 narration with a fronted phrase and explicit theme anchoring.", "vocab_hints": []},
                        {"step": 2, "english": "At first, I think it is ordinary, but one detail feels wrong.", "french": "Au début, je pense que c'est ordinaire, mais un détail me semble bizarre.", "context_note": "Contrast and reaction.", "vocab_hints": []},
                        {"step": 3, "english": "Someone explains part of the situation, but not enough.", "french": "Quelqu'un m'explique une partie de la situation, mais pas assez.", "context_note": "Partial explanation keeps the sequence moving.", "vocab_hints": []},
                        {"step": 4, "english": f"The more we discuss {theme}, the stranger the situation becomes.", "french": f"Plus nous discutons de {theme}, plus la situation devient étrange.", "context_note": "Comparative structure tied to theme.", "vocab_hints": []},
                        {"step": 5, "english": "I follow the lead because I want to understand what is happening.", "french": "Je suis cette piste parce que je veux comprendre ce qui se passe.", "context_note": "Natural motivation and continuation.", "vocab_hints": []},
                        {"step": 6, "english": "What I discover changes the meaning of the earlier clues.", "french": "Ce que je découvre change le sens des indices précédents.", "context_note": "Cause and reinterpretation.", "vocab_hints": []},
                        {"step": 7, "english": "For a moment, I hesitate, because the answer is more serious than I expected.", "french": "Pendant un instant, j'hésite, parce que la réponse est plus grave que je ne l'imaginais.", "context_note": "B1 hesitation and emotional reaction.", "vocab_hints": []},
                        {"step": 8, "english": "In the end, I leave with a completely different view of the whole event.", "french": "Finalement, je repars avec une vision complètement différente de tout l'événement.", "context_note": "Reflective ending.", "vocab_hints": []},
                    ],
                },
            },
            "dialogue": {
                "A1": {
                    "title": f"{theme.title()} Conversation",
                    "sentences": [
                        {"step": 1, "english": f"Anna: Hello. Are you here for {theme}?", "french": f"Anna : Bonjour. Tu es là pour {theme} ?", "context_note": "Dialogue format with explicit speaker labels.", "vocab_hints": []},
                        {"step": 2, "english": "Lucas: Yes, but I do not know what to do first.", "french": "Lucas : Oui, mais je ne sais pas quoi faire d'abord.", "context_note": "Reply from the second speaker.", "vocab_hints": []},
                        {"step": 3, "english": "Anna: Start here. It is easy.", "french": "Anna : Commence ici. C'est facile.", "context_note": "Short A1 instruction in dialogue form.", "vocab_hints": []},
                        {"step": 4, "english": f"Lucas: Good. Can you explain this part about {theme}?", "french": f"Lucas : D'accord. Tu peux expliquer cette partie sur {theme} ?", "context_note": "Theme is repeated inside the conversation.", "vocab_hints": []},
                        {"step": 5, "english": "Anna: Of course. Watch me first.", "french": "Anna : Bien sûr. Regarde-moi d'abord.", "context_note": "Short spoken instruction.", "vocab_hints": []},
                        {"step": 6, "english": "Lucas: That helps a lot. Thank you.", "french": "Lucas : Ça m'aide beaucoup. Merci.", "context_note": "Simple spoken reaction.", "vocab_hints": []},
                        {"step": 7, "english": "Anna: No problem. Now try it yourself.", "french": "Anna : Pas de problème. Maintenant, essaie tout seul.", "context_note": "Encouraging spoken line.", "vocab_hints": []},
                        {"step": 8, "english": "Lucas: I think I understand now.", "french": "Lucas : Je crois que je comprends maintenant.", "context_note": "Dialogue ending.", "vocab_hints": []},
                    ],
                },
                "B1": {
                    "title": f"{theme.title()} Exchange",
                    "sentences": [
                        {"step": 1, "english": f"Maya: So this is what everyone meant when they talked about {theme}.", "french": f"Maya : Donc, c'est de cela que tout le monde parlait à propos de {theme}.", "context_note": "Dialogue opening with explicit thematic anchor.", "vocab_hints": []},
                        {"step": 2, "english": "Noah: Yes, although it looks much stranger in real life than I expected.", "french": "Noah : Oui, même si cela paraît beaucoup plus étrange en vrai que je ne l'imaginais.", "context_note": "Natural B1 spoken response.", "vocab_hints": []},
                        {"step": 3, "english": "Maya: Do you think we should trust what we were told?", "french": "Maya : Tu crois qu'on devrait croire ce qu'on nous a dit ?", "context_note": "Question in natural spoken French.", "vocab_hints": []},
                        {"step": 4, "english": f"Noah: Not completely. The details about {theme} do not fit together.", "french": f"Noah : Pas complètement. Les détails sur {theme} ne vont pas ensemble.", "context_note": "Theme remains explicit and central.", "vocab_hints": []},
                        {"step": 5, "english": "Maya: Then we need one clear answer before we go any further.", "french": "Maya : Alors, il nous faut une réponse claire avant d'aller plus loin.", "context_note": "Spoken planning line.", "vocab_hints": []},
                        {"step": 6, "english": "Noah: Fine. Ask the question, and I will watch their reaction.", "french": "Noah : D'accord. Pose la question, et je regarderai leur réaction.", "context_note": "Future action in dialogue format.", "vocab_hints": []},
                        {"step": 7, "english": "Maya: If they hesitate, we will know they are hiding something.", "french": "Maya : S'ils hésitent, nous saurons qu'ils cachent quelque chose.", "context_note": "Conditional structure in spoken form.", "vocab_hints": []},
                        {"step": 8, "english": "Noah: In that case, we leave immediately.", "french": "Noah : Dans ce cas-là, on part tout de suite.", "context_note": "Tense ending in dialogue form.", "vocab_hints": []},
                    ],
                },
            },
            "film_scene": {
                "A1": {
                    "title": f"{theme.title()} Scene",
                    "sentences": [
                        {"step": 1, "english": f"The room is quiet, and everything points to {theme}.", "french": f"La pièce est calme, et tout fait penser à {theme}.", "context_note": "Simple cinematic setup tied to theme.", "vocab_hints": []},
                        {"step": 2, "english": "A door opens slowly behind me.", "french": "Une porte s'ouvre lentement derrière moi.", "context_note": "Visual scene beat.", "vocab_hints": []},
                        {"step": 3, "english": "Someone whispers my name.", "french": "Quelqu'un murmure mon nom.", "context_note": "Short dramatic beat.", "vocab_hints": []},
                        {"step": 4, "english": f"I turn around and see the real sign of {theme}.", "french": f"Je me retourne et je vois le vrai signe de {theme}.", "context_note": "Theme appears inside the scene action.", "vocab_hints": []},
                        {"step": 5, "english": "For one second, nobody moves.", "french": "Pendant une seconde, personne ne bouge.", "context_note": "Suspenseful stillness.", "vocab_hints": []},
                        {"step": 6, "english": "Then the light changes, and the scene feels different.", "french": "Puis la lumière change, et la scène semble différente.", "context_note": "Visual change inside same scene.", "vocab_hints": []},
                        {"step": 7, "english": "I take one step forward.", "french": "Je fais un pas en avant.", "context_note": "Simple dramatic action.", "vocab_hints": []},
                        {"step": 8, "english": "The camera would stop here, just before the answer.", "french": "La caméra s'arrêterait ici, juste avant la réponse.", "context_note": "Film-scene ending beat.", "vocab_hints": []},
                    ],
                },
                "B1": {
                    "title": f"{theme.title()} Opening Scene",
                    "sentences": [
                        {"step": 1, "english": f"The scene opens on a place shaped by {theme}, but nobody explains it out loud.", "french": f"La scène s'ouvre sur un lieu marqué par {theme}, mais personne ne l'explique à voix haute.", "context_note": "Cinematic opening with explicit theme anchor.", "vocab_hints": []},
                        {"step": 2, "english": "A small movement in the background immediately changes the mood.", "french": "Un petit mouvement en arrière-plan change immédiatement l'ambiance.", "context_note": "Visual shift inside a film scene.", "vocab_hints": []},
                        {"step": 3, "english": "The main character notices it, but pretends to stay calm.", "french": "Le personnage principal le remarque, mais fait semblant de rester calme.", "context_note": "Visual action and internal tension.", "vocab_hints": []},
                        {"step": 4, "english": f"What follows makes {theme} feel larger and more dangerous than before.", "french": f"Ce qui suit donne à {theme} une dimension plus vaste et plus dangereuse qu'avant.", "context_note": "Theme remains central to the cinematic beat.", "vocab_hints": []},
                        {"step": 5, "english": "A single line of dialogue reveals that someone already knows the truth.", "french": "Une seule réplique révèle que quelqu'un connaît déjà la vérité.", "context_note": "Film-scene style revelation.", "vocab_hints": []},
                        {"step": 6, "english": "The camera would linger on the silence that follows.", "french": "La caméra s'attarderait sur le silence qui suit.", "context_note": "Explicitly cinematic phrasing.", "vocab_hints": []},
                        {"step": 7, "english": "By then, the audience understands the danger, even if the characters do not.", "french": "À ce moment-là, le public comprend le danger, même si les personnages ne le comprennent pas encore.", "context_note": "Cinematic irony and tension.", "vocab_hints": []},
                        {"step": 8, "english": "The scene ends just before the decisive move.", "french": "La scène se termine juste avant le geste décisif.", "context_note": "Strong scene ending.", "vocab_hints": []},
                    ],
                },
            },
        }

        selected = fallback_lessons[fallback_type][level_key]
        sentences = [LessonSentence(**item) for item in selected["sentences"][: request.sentence_count]]
        return LessonResponse(
            lesson_id=lesson_id,
            title=selected["title"],
            difficulty=request.difficulty,
            theme=request.theme,
            lesson_type=fallback_type if request.lesson_type == "auto" else request.lesson_type,
            source="fallback",
            sentences=sentences,
        )

    def _evaluate_answer_fallback(self, request: EvaluationRequest) -> EvaluationResponse:
        learner_normalized = normalize_french(request.learner_answer)
        target_normalized = normalize_french(request.target_sentence)
        exact_match = learner_normalized == target_normalized
        similarity = int(SequenceMatcher(None, learner_normalized, target_normalized).ratio() * 100)
        reminder_triggers = detect_reminder_triggers(
            request,
            EvaluationResponse(
                is_correct=False,
                correctness_score=0,
                verdict="",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_sentence=request.target_sentence,
                more_common_sentence=request.target_sentence,
                tips=[],
                mistakes=[],
                learner_token_labels=[],
                reminders_triggered=[],
                encouraging_note="",
                source="fallback",
            ),
        )

        if exact_match:
            return EvaluationResponse(
                is_correct=True,
                correctness_score=100,
                verdict="Correct and natural.",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_sentence=request.target_sentence,
                more_common_sentence=request.target_sentence,
                tips=["Nice work. This matches the target meaning very closely."],
                mistakes=[],
                learner_token_labels=self._build_fallback_token_labels(
                    request.learner_answer,
                    request.target_sentence,
                    is_correct=True,
                ),
                reminders_triggered=[],
                encouraging_note="You can move on confidently.",
                source="fallback",
            )

        if reminder_triggers:
            return EvaluationResponse(
                is_correct=False,
                correctness_score=max(60, similarity - 10),
                verdict="Close, but an important grammar word is missing.",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_sentence=request.target_sentence,
                more_common_sentence=request.target_sentence,
                tips=[
                    "You are close on the main meaning.",
                    "French often needs a small linking word here: compare your answer with the suggested version carefully.",
                ],
                mistakes=[item["explanation"] for item in reminder_triggers],
                learner_token_labels=self._build_fallback_token_labels(
                    request.learner_answer,
                    request.target_sentence,
                    is_correct=False,
                ),
                reminders_triggered=[],
                encouraging_note="This is exactly the kind of repeatable pattern the reminder list is meant to catch.",
                source="fallback",
            )

        if similarity >= 82:
            return EvaluationResponse(
                is_correct=True,
                correctness_score=88,
                verdict="Probably correct, but the wording could be smoother.",
                learner_normalized=learner_normalized,
                target_normalized=target_normalized,
                suggested_sentence=request.target_sentence,
                more_common_sentence=request.target_sentence,
                tips=[
                    "Your answer is close in meaning.",
                    "Compare your word order with the suggested French.",
                ],
                mistakes=["Some wording is less idiomatic than the target sentence."],
                learner_token_labels=self._build_fallback_token_labels(
                    request.learner_answer,
                    request.target_sentence,
                    is_correct=True,
                ),
                reminders_triggered=[],
                encouraging_note="This is a solid attempt. Focus on the most natural phrasing now.",
                source="fallback",
            )

        return EvaluationResponse(
            is_correct=False,
            correctness_score=max(35, similarity),
            verdict="Not quite right yet.",
            learner_normalized=learner_normalized,
            target_normalized=target_normalized,
            suggested_sentence=request.target_sentence,
            more_common_sentence=request.target_sentence,
            tips=[
                "Check the core verb and the small grammar words.",
                "Use the suggested answer as a model, then try the next sentence quickly.",
            ],
            mistakes=["The meaning or structure differs noticeably from the target sentence."],
            learner_token_labels=self._build_fallback_token_labels(
                request.learner_answer,
                request.target_sentence,
                is_correct=False,
            ),
            reminders_triggered=[],
            encouraging_note="The important part is staying in the flow and learning from the comparison.",
            source="fallback",
        )

    def _explain_phrase_fallback(self, request: PhraseExplainRequest) -> PhraseExplainResponse:
        selected_normalized = normalize_french(request.selected_text)
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
                selected_text=request.selected_text,
                english_meaning=phrase_data["english_meaning"],
                usage_note=phrase_data["usage_note"],
                save_note=f"From: {request.english_sentence}",
                source="fallback",
            )

        wiktionary_result = lookup_wiktionary_french_definition(request.selected_text, request.target_sentence)
        if wiktionary_result is not None:
            english_meaning, usage_note = wiktionary_result
            return PhraseExplainResponse(
                selected_text=request.selected_text,
                english_meaning=english_meaning,
                usage_note=usage_note,
                save_note=f"From: {request.english_sentence}",
                source="fallback",
            )

        for hint in request.vocab_hints:
            if normalize_french(hint.french) == selected_normalized:
                return PhraseExplainResponse(
                    selected_text=request.selected_text,
                    english_meaning=hint.english,
                    usage_note=hint.note or "Useful vocabulary from this sentence.",
                    save_note=f"From: {request.english_sentence}",
                    source="fallback",
                )

        phrase = request.selected_text.strip()
        return PhraseExplainResponse(
            selected_text=phrase,
            english_meaning=f"Meaning of '{phrase}' in this sentence",
            usage_note="No custom hint was available, so treat this as a sentence-specific lookup target.",
            save_note=f"From: {request.english_sentence}",
            source="fallback",
        )
