# 🧭 Local AI Hub

**Gemma 4-Powered Offline Community Assistant**

A single Streamlit app that puts four AI assistants — Education, Healthcare,
Agriculture, and Emergency — behind one sidebar, all running on a local Gemma
model through Ollama. No internet connection required after setup.

---

## Why this exists

Most hackathon AI projects are "chat with your PDF." This is a **community
knowledge tool**: upload a document once and get a full study workflow out of
it (summary, flashcards, quiz, exam), or ask a direct question — in Education
without any document at all, or in Healthcare, Agriculture, and Emergency —
and get a straight, streamed answer. All offline, all on a laptop, no cloud
API key in sight.

---

## Architecture

```
User Question
      │
      ▼
 Choose Domain
      │
      ▼
Does this need a local document?
   ┌──┴──┐
  No     Yes
   │      │
   ▼      ▼
 Gemma   Read Document
   │      │
   └──┬───┘
      ▼
Streamed Response
```

- **Education** can go either way: ask a quick question directly (no upload
  needed), or upload a document first for Summary, Flashcards, Quiz, and
  Generate Exam.
- **Healthcare, Agriculture, and Emergency** always skip the document step
  and go straight to Gemma.
- Healthcare/Agriculture/Emergency and Education's "Ask a Question" mode use
  **true token streaming** — text appears as Gemma generates it, satisfying
  the "Streamed Response" step for real. The four document-based Education
  features (Summary, Exam, Flashcards, Quiz) return structured JSON instead,
  so those use one blocking call with a spinner — streaming raw JSON
  character-by-character would just look broken until it's fully parsed.

---

## Setup

### 1. Install Ollama and pull a model

```bash
# Install from https://ollama.com, then:
ollama pull gemma3:4b
```

If you already have a different Gemma variant installed (e.g. `gemma4:e2b`,
`gemma2:2b`), that's fine — the sidebar auto-detects every model you have
installed via Ollama's API and lets you pick one from a dropdown. No
hardcoded model name to edit.

### 2. Start Ollama

```bash
ollama serve
```

(If Ollama is already running in the background — check your system tray —
you can skip this. On Windows, if you get "address already in use," that
just means it's already running.)

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

(On Windows, if `pip` isn't recognized, use `python -m pip install -r requirements.txt` instead.)

### 4. Run the app

```bash
streamlit run app.py
```

(Same PATH note as above — if `streamlit` isn't recognized, use
`python -m streamlit run app.py`.)

It opens at `http://localhost:8501`. The sidebar will show **🟢 Ollama
Connected** and a dropdown of every model you have installed — pick one and
you're ready to go.

---

## File structure

```
local-ai-hub/
├── app.py                  ← Streamlit UI: sidebar nav, routing, all 4 domains
├── gemma_client.py          ← Ollama API calls + every prompt used
├── document_utils.py        ← PDF/TXT/MD text extraction
├── requirements.txt
├── .streamlit/
│   └── config.toml          ← Dark theme, green accent
└── README.md
```

Three Python files, each with one clear job. No database, no backend server
beyond Ollama itself.

---

## The sidebar

- **Navigation** — four buttons (not a dropdown or radio list): Education,
  Healthcare, Agriculture, Emergency. The currently selected one fills solid
  green (Streamlit's native `type="primary"` button style). Education always
  carries a **⭐ FEATURED — FULL STUDY WORKFLOW** badge underneath it, since
  it's the deepest feature set of the four.
- **🔄 Check Ollama Connection** — forces an immediate recheck of what
  Ollama has running, instead of waiting for the normal 5-second cache to
  expire on its own.
- **Model dropdown** — populated live from Ollama; only ever shows models
  that are actually installed.
- **🧠 How it works** — an expandable panel showing the architecture diagram
  above, for quick reference during a demo.
- A footer line stating the offline story plainly: *"Your local AI Node —
  powered entirely by Gemma 4. Runs locally without internet."*

Streamlit's own built-in "⋮" menu (top right) is left visible — Rerun,
Settings (theme, wide mode), and **Record a screencast** are all genuinely
useful, especially the screencast recorder for putting together a demo
video. Only the **Deploy** button is hidden, since this project targets
running locally, not publishing to Streamlit Community Cloud.

---

## Features

### 🎓 Education

Two modes, selected with a toggle at the top of the page:

**💬 Ask a Question** — no document required. A free-form box for any
subject: math, physics, biology, electronics, whatever. Answered by Gemma
with a live streamed response, same as Healthcare/Agriculture/Emergency
below. Comes with three example buttons (Newton's third law, photosynthesis,
the quadratic formula) so a demo never has to invent a question live.

**📚 Study from a Document** — upload a PDF, TXT, or MD file, then use:

| Feature | What it does |
|---|---|
| **Summary** | Key concepts, must-know formulas, common mistakes, and a revision summary. Scales to document length: documents up to 10,000 characters get one direct pass; longer documents are split into sections, summarized individually, then combined into one final summary (map-reduce), so a long document gets a genuinely thorough result instead of one thin paragraph. The revision summary specifically targets **~18% of the source document's length**, expressed to the model as an explicit paragraph count plus a minimum word count — a soft "write about N words" suggestion is reliably ignored by small local models, so the prompt gives it a concrete structural target instead. |
| **Flashcards** | Auto-generated front/back cards, click to reveal the answer. |
| **Quiz** | Interactive multiple-choice quiz, graded on submit, with a weak/strong topic breakdown. |
| **Generate Exam** | Mixed MCQ + short-answer exam paper with model answers. |

Every result includes a **📚 Knowledge used for this answer** expander,
showing exactly how much of the document was used and, for Summary, what
length was targeted — so nothing about what the model actually saw is
hidden.

> **Known limitation:** Exam, Flashcards, and Quiz currently send only the
> **first 2,500 characters** of an uploaded document to the model, regardless
> of the document's actual length (this limit is `SIMPLE_FEATURE_MAX_CHARS`
> in `gemma_client.py`). Summary does not have this limitation — it was
> fixed to scale with document length as described above. On a document
> longer than ~2,500 characters, an Exam/Flashcards/Quiz generated today
> only reflects roughly the first third of the material, silently ignoring
> the rest. The "Knowledge used" expander under each of these three features
> states this plainly (e.g. *"Used the first 2,500 of 6,964 characters of
> your document"*), but the underlying limit itself has not yet been raised
> to match Summary's fix.

### 🩺 Healthcare
Describe symptoms → streamed general health information (never diagnostic —
always ends with a "not medical advice" disclaimer).

### 🌾 Agriculture
Ask a crop question (with an optional crop name) → streamed practical advice
covering best practices and seasonal timing.

### 🆘 Emergency
Describe a situation → streamed first-aid steps, what not to do, and when to
call emergency services.

All three non-Education domains include example buttons so a live demo never
has to invent a question on the spot.

---

## Reliability details worth knowing about

- **JSON repair for truncated output** — small local models occasionally cut
  off mid-generation. Instead of showing a broken fragment, the app tries to
  salvage whatever complete fields exist by trimming to the last clean
  boundary and closing any open brackets, before falling back to a plain
  "try again" message.
- **Key-name tolerance** — if the model returns `keyConcepts` instead of
  `key_concepts` (or similar variations), the app normalizes it rather than
  silently showing empty results.
- **Streaming that surfaces real failures** — if Ollama genuinely returns no
  usable text for a Healthcare/Agriculture/Emergency/Ask-a-Question request,
  the app says so directly instead of showing a blank "success" card.
- **Model auto-detection** — no model name is hardcoded anywhere; the
  sidebar dropdown only ever shows models Ollama actually reports as
  installed, which avoids the "model not found" class of error entirely.
- **Instant navigation** — clicking between domains triggers exactly one
  script rerun, not two, so switching pages feels immediate rather than
  laggy.

---

## What was deliberately left out

The original HTML prototype also had Explain Simply, a Study Planner,
Learning Analytics, and an Activity History log. Per the hackathon scoping
call, those were cut for this build — two polished domains beat four
half-finished ones, and every one of those four extra features was judged
unlikely to move the needle on Gemma Integration, Innovation & Impact,
Functionality, or Presentation relative to the time it'd cost. They're a
natural "future work" list if there's time left after the core is solid.

---

## Judging criteria alignment

- **Gemma Integration (30%)** — every domain calls Gemma directly through
  Ollama; Education's Summary feature includes real map-reduce logic for
  long documents (not just a single truncated prompt), explicit length
  targeting to counter small-model undershoot, and JSON parsing with a
  repair step for output that cuts off mid-generation.
- **Offline execution** — the entire app runs against `localhost:11434`.
  No external API, no internet required after the model is pulled.
- **Functionality (20%)** — file upload, four working document-based
  features, a general-purpose Q&A mode, an interactive graded quiz, and
  three streaming domain assistants, all tested end to end.
- **Presentation & Writeup (20%)** — this README, plus a UI built to look
  intentional: consistent dark theme, a featured-domain badge, response
  cards, success confirmations, transparency into what the model actually
  used, and a footer that states the offline story plainly.

---

## Troubleshooting

**Sidebar says "🔴 Ollama Not Found"**
Ollama isn't reachable at `localhost:11434`. Run `ollama serve` in a
terminal and click **🔄 Check Ollama Connection** in the sidebar.

**"Model not found" error when generating**
Run `ollama list` to see what's actually installed, then pick a matching
name from the sidebar dropdown — it only ever shows models Ollama
confirms it has.

**PDF upload says "No text found"**
The PDF is likely scanned/image-based rather than text-based. Use a
text-based PDF, or paste the content into a `.txt` file instead.

**Exam/Flashcards/Quiz seem to ignore parts of a long document**
Expected for now — see the Known Limitation note under Education above.
Summary does not have this issue.

**Responses feel slow**
That's expected on CPU-only hardware with a local model — this is the
honest trade-off for running fully offline. The streaming responses
(Healthcare/Agriculture/Emergency, and Education's Ask a Question) are
there specifically so the wait still feels active rather than frozen.
