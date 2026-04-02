from __future__ import annotations

import json
import os
import textwrap
import uuid
from typing import Any

from openai import OpenAI

from .ai_service import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    RateLimitError,
    load_openai_api_key,
    normalize_french,
)
from .models import (
    AdventureActionRequest,
    AdventureCharacter,
    AdventureFeedback,
    AdventureScene,
    AdventureStartRequest,
    AdventureStateResponse,
    AdventureTask,
)
from .storage import save_adventure_brain


class AdventureService:
    def __init__(self) -> None:
        api_key = load_openai_api_key()
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_ADVENTURE_MODEL", os.getenv("OPENAI_LESSON_MODEL", "gpt-5-mini"))
        self.reasoning_effort = os.getenv("OPENAI_ADVENTURE_REASONING_EFFORT", "minimal")
        self.max_output_tokens = int(os.getenv("OPENAI_ADVENTURE_MAX_OUTPUT_TOKENS", "1600"))
        self.sessions: dict[str, dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def start_adventure(self, request: AdventureStartRequest) -> AdventureStateResponse:
        session_id = str(uuid.uuid4())
        if self.enabled:
            try:
                response = self._start_adventure_openai(request, session_id)
            except Exception as exc:
                response = self._start_adventure_fallback(request, session_id, self._format_openai_error("adventure setup", exc))
        else:
            response = self._start_adventure_fallback(request, session_id, "")

        self.sessions[session_id] = self._serialize_response(response)
        save_adventure_brain(session_id, response.brain_markdown)
        return response

    def submit_action(self, request: AdventureActionRequest) -> AdventureStateResponse:
        session = self.sessions.get(request.session_id)
        if session is None:
            raise RuntimeError("Adventure session not found.")

        learner_french = request.learner_french.strip()
        if not learner_french:
            raise RuntimeError("Type some French before submitting your action.")

        if session["source"] == "openai" and self.enabled:
            try:
                response = self._submit_action_openai(session, learner_french)
            except Exception as exc:
                response = self._submit_action_fallback(session, learner_french, self._format_openai_error("adventure turn", exc))
        else:
            response = self._submit_action_fallback(session, learner_french, "")

        self.sessions[request.session_id] = self._serialize_response(response)
        save_adventure_brain(request.session_id, response.brain_markdown)
        return response

    def _response_create_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
        }
        if self.reasoning_effort and self.model.startswith("gpt-5"):
            options["reasoning"] = {"effort": self.reasoning_effort}
        return options

    def _responses_create_with_retry(self, *, retries: int = 2, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for _attempt in range(retries + 1):
            try:
                return self.client.responses.create(**kwargs)
            except RateLimitError as exc:
                last_error = exc
            except (APIConnectionError, APIError, APITimeoutError) as exc:
                last_error = exc
        if last_error is None:
            raise RuntimeError("Adventure generation failed for an unknown reason.")
        raise last_error

    def _format_openai_error(self, action: str, exc: Exception) -> str:
        if isinstance(exc, RateLimitError):
            return f"{action.capitalize()} was rate-limited, so the local fallback took over."
        if isinstance(exc, BadRequestError):
            return f"{action.capitalize()} hit a model-format issue, so the local fallback took over."
        if isinstance(exc, APITimeoutError):
            return f"{action.capitalize()} timed out, so the local fallback took over."
        if isinstance(exc, APIConnectionError):
            return f"{action.capitalize()} could not reach OpenAI, so the local fallback took over."
        if isinstance(exc, APIError):
            return f"{action.capitalize()} hit an OpenAI API error, so the local fallback took over."
        return f"{action.capitalize()} fell back to the local story engine."

    def _start_adventure_openai(self, request: AdventureStartRequest, session_id: str) -> AdventureStateResponse:
        schema = {
            "name": "adventure_opening",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "scene": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "location_name": {"type": "string"},
                            "location_description": {"type": "string"},
                            "visual_motif": {"type": "string"},
                            "ambience": {"type": "string"},
                            "objective": {"type": "string"},
                            "player_prompt": {"type": "string"},
                            "npc_name": {"type": "string"},
                            "npc_role": {"type": "string"},
                            "npc_message_french": {"type": "string"},
                            "npc_message_english": {"type": "string"},
                        },
                        "required": [
                            "location_name",
                            "location_description",
                            "visual_motif",
                            "ambience",
                            "objective",
                            "player_prompt",
                            "npc_name",
                            "npc_role",
                            "npc_message_french",
                            "npc_message_english",
                        ],
                    },
                    "characters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"},
                                "mood": {"type": "string"},
                                "note": {"type": "string"},
                            },
                            "required": ["name", "role", "mood", "note"],
                        },
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "status": {"type": "string", "enum": ["active", "complete"]},
                            },
                            "required": ["title", "description", "status"],
                        },
                    },
                    "inventory": {"type": "array", "items": {"type": "string"}},
                    "transcript": {"type": "array", "items": {"type": "string"}},
                    "brain_markdown": {"type": "string"},
                },
                "required": ["title", "scene", "characters", "tasks", "inventory", "transcript", "brain_markdown"],
            },
        }

        response = self._responses_create_with_retry(
            **self._response_create_options(),
            input=[
                {
                    "role": "system",
                    "content": (
                        "You generate a French-learning adventure game. "
                        "The learner plays inside the world and can only act by typing French. "
                        "NPCs should feel warm, reactive, and teacher-like: they keep the story moving while correcting the learner naturally. "
                        "Keep the learner-facing dialogue in French. Support notes may be in English. "
                        "Return a compact but vivid opening scene with one clear objective, 2-4 memorable characters, and a markdown brain that stores facts, tasks, locations, and unresolved mysteries."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create the opening state for a French-learning adventure.\n"
                        f"Difficulty: {request.difficulty}\n"
                        f"Theme: {request.theme}\n"
                        f"Setting: {request.setting}\n"
                        f"Player name: {request.player_name}\n\n"
                        "Constraints:\n"
                        "- The opening should be playable immediately.\n"
                        "- The player must need to answer or ask something in French to proceed.\n"
                        "- The NPC message in French should be short enough to answer in one learner turn.\n"
                        "- The markdown brain must include headings for Premise, Characters, Locations, Active Tasks, Inventory, and Timeline.\n"
                        "- Keep objectives concrete and game-like."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )
        payload = json.loads(response.output_text)
        return AdventureStateResponse(
            session_id=session_id,
            difficulty=request.difficulty,
            theme=request.theme,
            setting=request.setting,
            turn=1,
            source="openai",
            title=payload["title"],
            scene=AdventureScene(**payload["scene"]),
            characters=[AdventureCharacter(**item) for item in payload["characters"]],
            tasks=[AdventureTask(**item) for item in payload["tasks"]],
            inventory=payload["inventory"],
            transcript=payload["transcript"],
            brain_markdown=payload["brain_markdown"],
        )

    def _submit_action_openai(self, session: dict[str, Any], learner_french: str) -> AdventureStateResponse:
        schema = {
            "name": "adventure_turn",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "feedback": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "accepted": {"type": "boolean"},
                            "score": {"type": "integer", "minimum": 0, "maximum": 100},
                            "correction_french": {"type": "string"},
                            "teacher_note": {"type": "string"},
                            "encouragement": {"type": "string"},
                        },
                        "required": ["accepted", "score", "correction_french", "teacher_note", "encouragement"],
                    },
                    "scene": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "location_name": {"type": "string"},
                            "location_description": {"type": "string"},
                            "visual_motif": {"type": "string"},
                            "ambience": {"type": "string"},
                            "objective": {"type": "string"},
                            "player_prompt": {"type": "string"},
                            "npc_name": {"type": "string"},
                            "npc_role": {"type": "string"},
                            "npc_message_french": {"type": "string"},
                            "npc_message_english": {"type": "string"},
                        },
                        "required": [
                            "location_name",
                            "location_description",
                            "visual_motif",
                            "ambience",
                            "objective",
                            "player_prompt",
                            "npc_name",
                            "npc_role",
                            "npc_message_french",
                            "npc_message_english",
                        ],
                    },
                    "characters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"},
                                "mood": {"type": "string"},
                                "note": {"type": "string"},
                            },
                            "required": ["name", "role", "mood", "note"],
                        },
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "status": {"type": "string", "enum": ["active", "complete"]},
                            },
                            "required": ["title", "description", "status"],
                        },
                    },
                    "inventory": {"type": "array", "items": {"type": "string"}},
                    "transcript": {"type": "array", "items": {"type": "string"}},
                    "brain_markdown": {"type": "string"},
                },
                "required": ["feedback", "scene", "characters", "tasks", "inventory", "transcript", "brain_markdown"],
            },
        }

        response = self._responses_create_with_retry(
            **self._response_create_options(),
            input=[
                {
                    "role": "system",
                    "content": (
                        "You run one turn of a French-learning adventure game. "
                        "You must both continue the fiction and tutor the learner. "
                        "If the learner's French is imperfect but understandable, accept it, correct it gently, and let the story move forward. "
                        "Only block progress if the French is too unclear to understand. "
                        "Keep the world-state coherent with the markdown brain. "
                        "Update the brain markdown every turn."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Session title: {session['title']}\n"
                        f"Difficulty: {session['difficulty']}\n"
                        f"Theme: {session['theme']}\n"
                        f"Setting: {session['setting']}\n"
                        f"Turn number: {session['turn']}\n\n"
                        f"Current scene JSON:\n{json.dumps(session['scene'], ensure_ascii=False)}\n\n"
                        f"Characters JSON:\n{json.dumps(session['characters'], ensure_ascii=False)}\n\n"
                        f"Tasks JSON:\n{json.dumps(session['tasks'], ensure_ascii=False)}\n\n"
                        f"Inventory JSON:\n{json.dumps(session['inventory'], ensure_ascii=False)}\n\n"
                        f"Transcript JSON:\n{json.dumps(session['transcript'], ensure_ascii=False)}\n\n"
                        f"Markdown brain:\n{session['brain_markdown']}\n\n"
                        f"Learner action in French: {learner_french}\n\n"
                        "Return the corrected French, a short teacher note in English, the next NPC response, the updated scene, and the updated markdown brain."
                    ),
                },
            ],
            text={"format": {"type": "json_schema", **schema}},
        )
        payload = json.loads(response.output_text)
        return AdventureStateResponse(
            session_id=session["session_id"],
            title=session["title"],
            difficulty=session["difficulty"],
            theme=session["theme"],
            setting=session["setting"],
            turn=session["turn"] + 1,
            source="openai",
            scene=AdventureScene(**payload["scene"]),
            characters=[AdventureCharacter(**item) for item in payload["characters"]],
            tasks=[AdventureTask(**item) for item in payload["tasks"]],
            inventory=payload["inventory"],
            transcript=payload["transcript"],
            brain_markdown=payload["brain_markdown"],
            feedback=AdventureFeedback(**payload["feedback"]),
        )

    def _start_adventure_fallback(
        self,
        request: AdventureStartRequest,
        session_id: str,
        fallback_note: str,
    ) -> AdventureStateResponse:
        scene = AdventureScene(
            location_name="Place des Embruns",
            location_description=(
                f"A lantern-lit square in a {request.setting}, with market stalls, drifting paper banners, "
                "and townspeople searching for something important."
            ),
            visual_motif="glowing festival lanterns, gull silhouettes, and puddles reflecting warm light",
            ambience="Curious, lively, and slightly urgent.",
            objective="Ask the town guide what happened to the missing lantern map.",
            player_prompt="Greet the guide and ask what is wrong. You must type in French.",
            npc_name="Mme Aubry",
            npc_role="town guide",
            npc_message_french="Bonjour ! La carte des lanternes a disparu. Tu peux m'aider ?",
            npc_message_english="Hello. The lantern map has disappeared. Can you help me?",
        )
        characters = [
            AdventureCharacter(name="Mme Aubry", role="town guide", mood="worried but encouraging", note="She corrects French gently."),
            AdventureCharacter(name="Léo", role="baker's apprentice", mood="restless", note="He saw someone running toward the harbour."),
            AdventureCharacter(name="Nadia", role="library keeper", mood="observant", note="She keeps old town records and clues."),
        ]
        tasks = [
            AdventureTask(title="Find the lantern map", description="Question the guide and collect your first clue.", status="active"),
            AdventureTask(title="Gain trust in French", description="Use simple French to keep people talking.", status="active"),
        ]
        transcript = [
            "Narrator: The square hums with festival music, but something important is missing.",
            f"{scene.npc_name}: {scene.npc_message_french}",
        ]
        brain_markdown = self._build_brain_markdown(
            request=request,
            scene=scene,
            characters=characters,
            tasks=tasks,
            inventory=["festival badge"],
            timeline=["You arrive in the square just as the missing map causes a stir."],
            extra_note=fallback_note,
        )
        return AdventureStateResponse(
            session_id=session_id,
            title=f"Les lanternes perdues: {request.theme.title()}",
            difficulty=request.difficulty,
            theme=request.theme,
            setting=request.setting,
            turn=1,
            source="fallback",
            scene=scene,
            characters=characters,
            tasks=tasks,
            inventory=["festival badge"],
            transcript=transcript,
            brain_markdown=brain_markdown,
        )

    def _submit_action_fallback(
        self,
        session: dict[str, Any],
        learner_french: str,
        fallback_note: str,
    ) -> AdventureStateResponse:
        normalized = normalize_french(learner_french)
        score = self._score_fallback_french(normalized)
        accepted = score >= 55
        correction = self._build_fallback_correction(learner_french, normalized)
        teacher_note = self._build_fallback_teacher_note(normalized, accepted, fallback_note)

        old_inventory = list(session["inventory"])
        transcript = list(session["transcript"])
        transcript.append(f"Player: {learner_french}")

        progress_stage = min(session["turn"], 3)
        scene, characters, tasks = self._advance_fallback_world(
            session=session,
            accepted=accepted,
            progress_stage=progress_stage,
        )
        if accepted and progress_stage == 1 and "wet sketch of the harbour" not in old_inventory:
            old_inventory.append("wet sketch of the harbour")
        if accepted and progress_stage == 2 and "brass key with a moon symbol" not in old_inventory:
            old_inventory.append("brass key with a moon symbol")

        transcript.append(f"{scene.npc_name}: {scene.npc_message_french}")
        timeline = [
            f"Turn {session['turn']}: the player said '{learner_french}'.",
            f"The guide treated it as {'understandable' if accepted else 'too unclear'} and responded.",
            f"Scene shifted to {scene.location_name}.",
        ]
        if accepted and progress_stage >= 1:
            timeline.append("A new clue pushes the search forward.")

        brain_markdown = self._build_brain_markdown(
            request=AdventureStartRequest(
                difficulty=session["difficulty"],
                theme=session["theme"],
                setting=session["setting"],
                player_name="Camille",
            ),
            scene=scene,
            characters=characters,
            tasks=tasks,
            inventory=old_inventory,
            timeline=timeline,
            extra_note=fallback_note,
        )
        return AdventureStateResponse(
            session_id=session["session_id"],
            title=session["title"],
            difficulty=session["difficulty"],
            theme=session["theme"],
            setting=session["setting"],
            turn=session["turn"] + 1,
            source="fallback",
            scene=scene,
            characters=characters,
            tasks=tasks,
            inventory=old_inventory,
            transcript=transcript[-8:],
            brain_markdown=brain_markdown,
            feedback=AdventureFeedback(
                accepted=accepted,
                score=score,
                correction_french=correction,
                teacher_note=teacher_note,
                encouragement="Keep it short and direct. Everyday French is enough to drive the story.",
            ),
        )

    def _advance_fallback_world(
        self,
        *,
        session: dict[str, Any],
        accepted: bool,
        progress_stage: int,
    ) -> tuple[AdventureScene, list[AdventureCharacter], list[AdventureTask]]:
        characters = [AdventureCharacter(**item) for item in session["characters"]]
        tasks = [AdventureTask(**item) for item in session["tasks"]]
        if not accepted:
            scene = AdventureScene(
                location_name=session["scene"]["location_name"],
                location_description=session["scene"]["location_description"],
                visual_motif=session["scene"]["visual_motif"],
                ambience="Patient, expectant, and gently instructional.",
                objective="Try again in simpler French so the guide can understand you.",
                player_prompt="Ask a simple question or offer help in one short French sentence.",
                npc_name=session["scene"]["npc_name"],
                npc_role=session["scene"]["npc_role"],
                npc_message_french="Je comprends un peu, mais peux-tu le dire plus simplement ?",
                npc_message_english="I understand a little, but can you say it more simply?",
            )
            return scene, characters, tasks

        for task in tasks:
            if task.status == "active":
                task.status = "complete"
                break

        next_scenes = [
            AdventureScene(
                location_name="Boulangerie du Phare",
                location_description="A glowing bakery where flour dust hangs in the air and fresh bread fogs the windows.",
                visual_motif="swinging copper lamps, warm ovens, and a flour-covered counter",
                ambience="Busy, warm, and conspiratorial.",
                objective="Ask Léo what he saw near the harbour.",
                player_prompt="Question Léo in French about what happened.",
                npc_name="Léo",
                npc_role="baker's apprentice",
                npc_message_french="J'ai vu une silhouette courir vers le port avec un tube bleu. Tu veux savoir quand ?",
                npc_message_english="I saw a figure run toward the harbour with a blue tube. Do you want to know when?",
            ),
            AdventureScene(
                location_name="Archives de la Marée",
                location_description="A narrow record room stacked with maps, brass drawers, and damp notebooks from old festivals.",
                visual_motif="dusty shelves, moon-marked drawers, and drifting paper scraps",
                ambience="Quiet, observant, and full of hidden patterns.",
                objective="Ask Nadia how to use the moon-marked key.",
                player_prompt="Speak to Nadia in French and ask for help with the key.",
                npc_name="Nadia",
                npc_role="library keeper",
                npc_message_french="Cette clef ouvre un coffre sous la tour. Si tu es prêt, dis-moi ce que tu cherches exactement.",
                npc_message_english="This key opens a chest under the tower. If you're ready, tell me exactly what you're looking for.",
            ),
            AdventureScene(
                location_name="Tour des Lanternes",
                location_description="A wind-bent tower above the harbour where lanterns sway like constellations.",
                visual_motif="storm glass, moonlit ropes, and lantern chains moving in the wind",
                ambience="Triumphant, airy, and slightly magical.",
                objective="Describe in French what you want to do next and claim the recovered map.",
                player_prompt="Use French to give your final action.",
                npc_name="Mme Aubry",
                npc_role="town guide",
                npc_message_french="Tu as trouvé toutes les pistes. Encore une phrase en français, et nous récupérons la carte ensemble.",
                npc_message_english="You found all the clues. One more sentence in French, and we recover the map together.",
            ),
        ]
        scene = next_scenes[min(progress_stage - 1, len(next_scenes) - 1)]

        updated_tasks = [task for task in tasks if task.status != "complete"]
        updated_tasks.insert(0, AdventureTask(title=scene.objective, description=scene.player_prompt, status="active"))
        return scene, characters, updated_tasks[:3]

    def _score_fallback_french(self, normalized: str) -> int:
        if not normalized:
            return 0
        common = {
            "bonjour", "bonsoir", "je", "tu", "vous", "peux", "pouvez", "veux", "aide", "aider",
            "ou", "quoi", "quand", "comment", "cherche", "sais", "voir", "carte", "port", "cle",
            "clef", "lanterne", "merci", "oui", "non",
        }
        tokens = normalized.split()
        french_hits = sum(1 for token in tokens if token in common or token.endswith(("er", "ez", "ons")))
        english_penalty = 18 if any(token in {"the", "what", "where", "help", "map"} for token in tokens) else 0
        base = 30 + min(55, french_hits * 12)
        if len(tokens) >= 3:
            base += 8
        return max(10, min(100, base - english_penalty))

    def _build_fallback_correction(self, learner_french: str, normalized: str) -> str:
        if "bonjour" in normalized and "aide" in normalized:
            return "Bonjour, je peux vous aider ?"
        if "ou" in normalized and ("carte" in normalized or "plan" in normalized):
            return "Où est la carte des lanternes ?"
        if "quand" in normalized:
            return "Quand avez-vous vu cette silhouette ?"
        if "cherche" in normalized and "cle" in normalized:
            return "Je cherche une clé avec un symbole de lune."
        cleaned = learner_french.strip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned[:1].upper() + cleaned[1:] if cleaned else "Pouvez-vous répéter, s'il vous plaît ?"

    def _build_fallback_teacher_note(self, normalized: str, accepted: bool, fallback_note: str) -> str:
        note = ""
        if not accepted:
            note = "Your meaning was hard to recover. Try a shorter French sentence with a subject, a verb, and one clear question."
        elif "ou" in normalized and "est" not in normalized:
            note = "Nice job. To sound more natural, try using a full question frame like 'Où est... ?'"
        elif "bonjour" not in normalized:
            note = "This works. Adding a greeting first would make it feel even more natural in conversation."
        else:
            note = "That was understandable and natural enough to move the story forward."
        if fallback_note:
            note = f"{note} {fallback_note}"
        return note.strip()

    def _build_brain_markdown(
        self,
        *,
        request: AdventureStartRequest,
        scene: AdventureScene,
        characters: list[AdventureCharacter],
        tasks: list[AdventureTask],
        inventory: list[str],
        timeline: list[str],
        extra_note: str,
    ) -> str:
        character_lines = "\n".join(f"- **{item.name}**: {item.role}. Mood: {item.mood}. {item.note}".strip() for item in characters)
        task_lines = "\n".join(f"- [{'x' if item.status == 'complete' else ' '}] {item.title}: {item.description}" for item in tasks)
        inventory_lines = "\n".join(f"- {item}" for item in inventory) or "- none"
        timeline_lines = "\n".join(f"- {item}" for item in timeline)
        location_lines = f"- **{scene.location_name}**: {scene.location_description}"
        extra_section = f"\n## Engine Notes\n- {extra_note}" if extra_note else ""
        return textwrap.dedent(
            f"""\
            # Adventure Brain

            ## Premise
            - Player: {request.player_name}
            - Theme: {request.theme}
            - Setting: {request.setting}
            - Current objective: {scene.objective}

            ## Characters
            {character_lines}

            ## Locations
            {location_lines}

            ## Active Tasks
            {task_lines}

            ## Inventory
            {inventory_lines}

            ## Timeline
            {timeline_lines}
            {extra_section}
            """
        ).strip()

    def _serialize_response(self, response: AdventureStateResponse) -> dict[str, Any]:
        payload = response.model_dump()
        payload["scene"] = response.scene.model_dump()
        payload["characters"] = [item.model_dump() for item in response.characters]
        payload["tasks"] = [item.model_dump() for item in response.tasks]
        if response.feedback is not None:
            payload["feedback"] = response.feedback.model_dump()
        return payload
