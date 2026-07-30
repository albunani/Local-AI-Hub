# 🧭 Local AI Hub

**Gemma 4-Powered Offline Community Assistant**

A single Streamlit app that puts four AI assistants — Education, Healthcare,
Agriculture, and Emergency — behind one sidebar, all running on a local Gemma
model through Ollama. No internet connection required after setup.

---

## Why this exists

Most hackathon AI projects are "chat with your PDF." This is a **community
knowledge tool**: upload a document once and get a full study workflow out of
it (summary, flashcards, quiz, exam), or just ask a direct question in
Healthcare, Agriculture, or Emergency and get a straight answer — all offline,
all on a laptop, no cloud API key in sight.

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

- **Education** requires an uploaded document — Summary, Flashcards, Quiz,
  and Generate Exam all read from whatever you upload.
- **Healthcare, Agriculture, and Emergency** skip the document step entirely
  and go straight to Gemma with your question.
- Healthcare/Agriculture/Emergency responses are **true token streams** —
  text appears as Gemma generates it, not after a single long wait. Education's
  four features return structured JSON (concepts, questions, cards), so those
  use one blocking call with a spinner instead — streaming raw JSON
  character-by-character would just look broken until it's fully parsed.

---

## Setup

### 1. Install Ollama and pull a model

```bash
# Install from https://ollama.com, then:
ollama pull gemma3:4b
```

If you already have a different Gemma variant installed (e.g. `gemma4:e2b`,
`gemma2:2b`), that's fine — the app auto-detects every model you have
installed and lets you pick one from the sidebar. No hardcoded model name to
edit.

### 2. Start Ollama

```bash
OLLAMA_ORIGINS="*" ollama serve
```

(If Ollama is already running in the background, quit it from your system
tray first, or just skip this — the default install usually already has it
running on `localhost:11434`.)

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

It opens at `http://localhost:8501`. The sidebar will show **🟢 Ollama
Connected** and a dropdown of every model you have installed — pick one and
you're ready to go.

---

## File structure

```
local-ai-hub/
├── app.py                  ← Streamlit UI: sidebar, routing, all 4 domains
├── gemma_client.py          ← Ollama API calls + every prompt used
├── document_utils.py        ← PDF/TXT/MD text extraction
├── requirements.txt
├── .streamlit/
│   └── config.toml          ← Dark theme, green accent
└── README.md
```

Kept intentionally small — three Python files, each with one clear job. No
database, no backend server beyond Ollama itself.

---

## Features

### 🎓 Education (needs a document)
| Feature | What it does |
|---|---|
| **Summary** | Key concepts, must-know formulas, common mistakes, and a revision summary. Scales to document length — short docs get one pass, long docs are split into sections and combined, so a long document gets a genuinely thorough summary instead of one thin paragraph. |
| **Flashcards** | Auto-generated front/back cards, click to reveal the answer. |
| **Quiz** | Interactive multiple-choice quiz, graded on submit, with weak/strong topic breakdown. |
| **Generate Exam** | Mixed MCQ + short-answer exam paper with model answers. |

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
  long documents (not just a single truncated prompt), and JSON parsing
  includes a repair step for small models that occasionally cut off
  mid-generation.
- **Offline execution** — the entire app runs against `localhost:11434`.
  No external API, no internet required after the model is pulled.
- **Functionality (20%)** — file upload, four working generative features,
  an interactive graded quiz, and three streaming Q&A domains, all tested
  end to end.
- **Presentation & Writeup (20%)** — this README, plus a UI built to look
  intentional: consistent dark theme, clear sidebar navigation, response
  cards, success confirmations, and a footer that states the offline story
  plainly.

---

## Troubleshooting

**Sidebar says "🔴 Ollama Not Found"**
Ollama isn't reachable at `localhost:11434`. Run `OLLAMA_ORIGINS="*" ollama
serve` in a terminal and refresh the page.

**"Model not found" error when generating**
Run `ollama list` to see what's actually installed, then pick a matching
name from the sidebar dropdown — it only ever shows models Ollama
confirms it has.

**PDF upload says "No text found"**
The PDF is likely scanned/image-based rather than text-based. Use a
text-based PDF, or paste the content into a `.txt` file instead.

**Responses feel slow**
That's expected on CPU-only hardware with a local model — this is the
honest trade-off for running fully offline. The streaming responses
(Healthcare/Agriculture/Emergency) are there specifically so the wait
still feels active rather than frozen.
