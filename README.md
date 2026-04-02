# French Story Trainer

A small FastAPI app for French writing practice through sequential story/dialogue translation.

It now also includes an experimental `/adventure` mode: a wider animated prototype where you move through a generated world by typing French to NPCs.

## What it does

- Generates a themed sequence of English prompts and target French translations
- Includes a separate adventure prototype with scene generation, NPC dialogue, task tracking, and a markdown world brain
- Lets the learner answer in free text, quickfire style
- Gives sentence-by-sentence feedback, including whether the answer is correct, natural, and commonly phrased
- Supports CEFR-style levels: `A1`, `A2`, `B1`, `B2`, `C1`
- Can reveal key vocabulary hints for unusual terms
- Saves vocabulary items locally and exports them as an Anki-friendly CSV
- Requires OpenAI access for lesson generation, answer evaluation, and phrase explanation

## Architecture

- `app/main.py`
  FastAPI server, lesson APIs, adventure APIs, vocab APIs, and static file serving.
- `app/ai_service.py`
  OpenAI-backed lesson generation, answer evaluation, and phrase explanation.
- `app/adventure_service.py`
  Adventure-mode world generation, turn handling, fallback story logic, and markdown brain snapshots.
- `app/models.py`
  Pydantic request/response models.
- `app/storage.py`
  Simple JSON-file persistence for saved vocabulary.
- `app/static/`
  Single-page frontend in plain HTML/CSS/JS.

## Run locally

1. Install dependencies:

```powershell
cd C:\Users\curtu\docker_test\french_trainer
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure OpenAI

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

Optional: override the default model if you want:

```powershell
$env:OPENAI_LESSON_MODEL="gpt-5-mini"
$env:OPENAI_EVAL_MODEL="gpt-5-mini"
```

Optional: tune for lower latency:

```powershell
$env:OPENAI_LESSON_REASONING_EFFORT="minimal"
$env:OPENAI_EVAL_REASONING_EFFORT="minimal"
$env:OPENAI_LESSON_MAX_OUTPUT_TOKENS="1200"
$env:OPENAI_EVAL_MAX_OUTPUT_TOKENS="320"
$env:OPENAI_EXPLAIN_MAX_OUTPUT_TOKENS="220"
```

3. Start the app:

```powershell
uvicorn app.main:app --reload --port 8090
```

4. Open:

`http://127.0.0.1:8090`

Adventure mode:

`http://127.0.0.1:8090/adventure`

## Notes

- The OpenAI integration uses the Responses API on the server side, so your API key stays off the client.
- The app defaults to `gpt-5-mini` for both lesson generation and evaluation.
- You can reduce latency by lowering reasoning effort and capping output tokens with the optional environment variables above.
- The app now requires internet access and a working OpenAI API key; if the API call fails, the server returns an explicit error instead of falling back locally.
- Accent-insensitive checking is supported. The evaluator still points out when accents should normally be used.
- Saved vocabulary is stored in `data/saved_vocab.json`.
