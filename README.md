# French Story Trainer

A small FastAPI app for French writing practice through sequential story/dialogue translation.

## What it does

- Generates a themed sequence of English prompts and target French translations
- Lets the learner answer in free text, quickfire style
- Gives sentence-by-sentence feedback, including whether the answer is correct, natural, and commonly phrased
- Supports CEFR-style levels: `A1`, `A2`, `B1`, `B2`, `C1`
- Can reveal key vocabulary hints for unusual terms
- Saves vocabulary items locally and exports them as an Anki-friendly CSV
- Works with OpenAI when `OPENAI_API_KEY` is configured
- Falls back to a built-in demo lesson/evaluator when no API key is present

## Architecture

- `app/main.py`
  FastAPI server, lesson APIs, vocab APIs, and static file serving.
- `app/ai_service.py`
  OpenAI-backed lesson generation and answer evaluation, plus local fallback mode.
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

2. Optional: configure OpenAI

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

3. Start the app:

```powershell
uvicorn app.main:app --reload --port 8090
```

4. Open:

`http://127.0.0.1:8090`

## Notes

- The OpenAI integration uses the Responses API on the server side, so your API key stays off the client.
- Accent-insensitive checking is supported. The evaluator still points out when accents should normally be used.
- Saved vocabulary is stored in `data/saved_vocab.json`.
