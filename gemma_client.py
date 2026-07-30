"""
gemma_client.py — All communication with the local Gemma model via Ollama.

Design notes (carried over from the earlier prototype, where these were
hard-won fixes):
  - JSON parsing includes a repair step for output that gets cut off
    mid-generation, which happens occasionally with small local models.
  - Smart Summary scales with document length: short documents get one
    direct pass, long documents are split into sections and combined
    (map-reduce), so a long document produces a genuinely thorough
    revision summary instead of one thin paragraph.
  - Healthcare / Agriculture / Emergency use true token streaming, since
    their output is plain prose and benefits from appearing as it's
    generated. Education's structured features (Summary, Exam, Flashcards,
    Quiz) use a single blocking call instead, since streaming raw JSON
    character-by-character looks broken until it's fully parsed.
"""

import json
import math
import re

import requests
import streamlit as st

OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 300  # seconds — small local models can be slow on CPU

# Raised from 3500/6000: a ~7,000-char document was triggering the 4-call
# map-reduce pipeline (3 section calls + 1 combine call), which is why it
# took 5-7 minutes for a fairly modest document. Most single-topic lecture
# notes are under 10k characters and now get one fast single-pass call instead.
SUMMARY_CHUNK_THRESHOLD = 10000  # beyond this, summary switches to map-reduce
SUMMARY_SINGLE_PASS_MAX_CHARS = 10000
SIMPLE_FEATURE_MAX_CHARS = 2500  # what Exam/Flashcards/Quiz actually send to the model

TARGET_SUMMARY_PCT = 0.18   # revision summary targets ~18% of source length (middle of 15-20%)
CHARS_PER_WORD = 5.5        # rough English average, used to convert char targets to word targets


# ---------------------------------------------------------------------------
# Connection / model discovery
# ---------------------------------------------------------------------------

@st.cache_data(ttl=5)
def get_installed_models():
    """Returns a list of model names actually installed in Ollama, or [] if unreachable.
    Cached briefly so normal UI interactions don't re-hit Ollama's API on every rerun —
    the sidebar's "Check Ollama Connection" button clears this cache for an immediate recheck."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def is_ollama_running():
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate(prompt, model, max_tokens=150, temperature=0.7):
    """Single blocking call — returns the full response text at once."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        },
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code == 404:
        raise RuntimeError(
            f'Model "{model}" not found in Ollama. Run "ollama list" in your terminal '
            f"to see installed models, then pick one from the sidebar."
        )
    resp.raise_for_status()
    return resp.json().get("response", "")


def generate_stream(prompt, model, max_tokens=200, temperature=0.7):
    """Generator that yields text chunks as Ollama produces them (true token streaming)."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        },
        stream=True,
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code == 404:
        raise RuntimeError(
            f'Model "{model}" not found in Ollama. Run "ollama list" in your terminal '
            f"to see installed models, then pick one from the sidebar."
        )
    resp.raise_for_status()

    got_any_chunk = False
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            # A single malformed line shouldn't silently kill the whole stream —
            # skip it and keep going rather than failing with no output at all.
            continue
        if chunk.get("response"):
            got_any_chunk = True
            yield chunk["response"]
        if chunk.get("done"):
            break

    if not got_any_chunk:
        # Nothing usable came back at all — surface this instead of silently
        # yielding zero chunks, which looks like a frozen/blank response.
        raise RuntimeError(
            "Ollama returned no text for this request. This can happen if the "
            "model is still loading into memory on the first call — try again."
        )


def generate_json(prompt, model, max_tokens=700):
    raw = generate(prompt, model, max_tokens=max_tokens)
    return parse_json(raw)


# ---------------------------------------------------------------------------
# JSON parsing with truncation repair
# ---------------------------------------------------------------------------

def parse_json(raw):
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    repaired = _repair_truncated_json(cleaned)
    if repaired is not None:
        return repaired

    return {"_raw": raw}


def _repair_truncated_json(raw):
    """If the model's output was cut off mid-generation, salvage whatever
    complete fields exist by cutting at the last clean boundary and closing
    any open brackets from there."""
    boundary_ends = [m.end() for m in re.finditer(r'"[^"\\]*(?:\\.[^"\\]*)*"|\}|\]', raw)]

    for pos in reversed(boundary_ends):
        candidate = raw[:pos].rstrip()
        if candidate.endswith(","):
            candidate = candidate[:-1]
        opens, closes = candidate.count("{"), candidate.count("}")
        opens_a, closes_a = candidate.count("["), candidate.count("]")
        fixed = candidate + ("]" * max(0, opens_a - closes_a)) + ("}" * max(0, opens - closes))
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            continue
    return None


def _trim_text(text, max_chars=SIMPLE_FEATURE_MAX_CHARS):
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...truncated...]"


# ===========================================================================
# EDUCATION PROMPTS
# ===========================================================================

def describe_summary_source(text):
    """Human-readable note on how much of the document Summary actually used —
    shown in the app's "Knowledge used for this answer" section."""
    n = len(text)
    target_words, paragraphs = _target_summary_length(min(n, SUMMARY_SINGLE_PASS_MAX_CHARS) if n <= SUMMARY_CHUNK_THRESHOLD else n)
    if n <= SUMMARY_CHUNK_THRESHOLD:
        used = min(n, SUMMARY_SINGLE_PASS_MAX_CHARS)
        base = (
            f"Used the full document in a single pass ({n:,} characters)."
            if used >= n else
            f"Used the first {used:,} of {n:,} characters, in a single pass."
        )
        return f"{base} Targeted a {paragraphs}-paragraph, ~{target_words}-word revision summary (~18% of source length)."
    chunks = _chunk_text(text)
    return (
        f"Document split into {len(chunks)} sections and summarized section-by-section, "
        f"then combined into one summary ({n:,} characters total). "
        f"Targeted a {paragraphs}-paragraph, ~{target_words}-word revision summary (~18% of source length)."
    )


def describe_simple_source(text, max_chars=SIMPLE_FEATURE_MAX_CHARS):
    """Same idea, for Exam/Flashcards/Quiz which use a single pass with no chunking."""
    n = len(text)
    if n <= max_chars:
        return f"Used the full document ({n:,} characters)."
    return f"Used the first {max_chars:,} of {n:,} characters of your document."


def _target_summary_length(char_count):
    """Computes an explicit (word_target, paragraph_count) pair scaled to
    ~18% of the source document length. Small local models reliably
    undershoot a bare word-count suggestion, so the prompt also gets a
    concrete paragraph count — a structural target is much more reliably
    followed than an abstract number of words."""
    target_words = round(char_count * TARGET_SUMMARY_PCT / CHARS_PER_WORD)
    target_words = max(150, min(900, target_words))
    paragraphs = max(3, min(8, round(char_count / 1200)))
    return target_words, paragraphs


def _normalize_summary(raw):
    if not raw or "_raw" in raw:
        return raw

    def pick(*keys):
        for k in keys:
            if k in raw:
                return raw[k]
        return None

    return {
        "key_concepts": pick("key_concepts", "keyConcepts", "concepts", "key_points", "keyPoints") or [],
        "formulas": pick("formulas", "keyFormulas", "key_formulas", "formula_list") or [],
        "common_mistakes": pick("common_mistakes", "commonMistakes", "mistakes", "common_errors") or [],
        "revision_summary": pick("revision_summary", "revisionSummary", "summary", "revision") or "",
    }


def summary(text, model, progress_callback=None):
    """Smart Summary — scales to document length.
    Short documents: one direct pass with a richer prompt.
    Long documents: split into sections, summarize each, then combine into
    one comprehensive final summary (map-reduce), so a long document yields
    a genuinely thorough revision summary rather than one thin paragraph."""
    if len(text) <= SUMMARY_CHUNK_THRESHOLD:
        return _summary_single_pass(text, model)
    return _summary_chunked(text, model, progress_callback)


def _summary_single_pass(text, model):
    material = _trim_text(text, SUMMARY_SINGLE_PASS_MAX_CHARS)
    target_words, paragraphs = _target_summary_length(len(material))
    prompt = f"""You are a study assistant. From this material, extract a JSON object with EXACTLY these keys (snake_case):
- "key_concepts": array of 8-12 specific, meaningful concept names (not generic single words)
- "formulas": array of up to 6 objects with "name", "formula", "description" (1 sentence each). Empty array if none exist.
- "common_mistakes": array of 5-6 full-sentence explanations of mistakes students make and why, not just short phrases
- "revision_summary": MUST be {paragraphs} full paragraphs (3-5 sentences each), each paragraph covering a different theme or section of the material. This must be at least {target_words} words total — do NOT write a short summary or a single paragraph. Be thorough and comprehensive, covering every major topic in the material, not just the introduction.

Material:
{material}

ONLY valid JSON. No markdown. No explanation. Do not use different key names."""
    raw = generate_json(prompt, model, max_tokens=max(1200, math.ceil(target_words * 2.5)))
    return _normalize_summary(raw)


def _chunk_text(text, max_chunks=8):
    """Split long text into digestible sections, capped at ~8 chunks so runtime stays reasonable."""
    chunk_size = max(2500, math.ceil(len(text) / max_chunks))
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for p in paragraphs:
        if current and (len(current) + len(p) + 2) > chunk_size:
            chunks.append(current.strip())
            current = p
        else:
            current = current + "\n\n" + p if current else p
        while len(current) > chunk_size * 1.5:
            chunks.append(current[:chunk_size].strip())
            current = current[chunk_size:]

    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def _summary_chunked(text, model, progress_callback=None):
    chunks = _chunk_text(text)
    chunk_notes = []

    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback(f"📖 Reading section {i + 1} of {len(chunks)}…")
        prompt = f"""From this section of a larger document, extract JSON:
{{"key_concepts": [3-5 specific concept names], "formulas": [{{"name","formula","description"}}], "common_mistakes": [1-2 full-sentence mistakes], "summary": "2-4 sentence summary of this section only"}}

Section {i + 1} of {len(chunks)}:
{chunk}

ONLY valid JSON."""
        result = generate_json(prompt, model, max_tokens=500)
        chunk_notes.append(result if "_raw" not in result else {})

    if progress_callback:
        progress_callback("🧩 Combining sections into final summary…")

    all_concepts = list(dict.fromkeys(sum([c.get("key_concepts", []) for c in chunk_notes], [])))
    all_formulas = sum([c.get("formulas", []) for c in chunk_notes], [])
    all_mistakes = list(dict.fromkeys(sum([c.get("common_mistakes", []) for c in chunk_notes], [])))
    section_summaries = "\n".join(
        f"Section {i + 1}: {c.get('summary', '(no summary extracted)')}" for i, c in enumerate(chunk_notes)
    )

    target_words, paragraphs = _target_summary_length(len(text))
    final_prompt = f"""Based on these section-by-section notes from a full document, write a comprehensive JSON study summary:
- "key_concepts": select and refine the 10-14 most important from this list: {json.dumps(all_concepts[:40])}
- "formulas": select up to 8 most important from: {json.dumps(all_formulas[:20])}
- "common_mistakes": select and refine the 6-8 most useful from: {json.dumps(all_mistakes[:30])}
- "revision_summary": MUST be {paragraphs} full paragraphs (3-5 sentences each), each covering a different section of the document below. This must be at least {target_words} words total — do NOT write a short summary. Be thorough: every section listed below should be represented in the final summary, not just the first few.

Section notes:
{section_summaries}

ONLY valid JSON. No markdown."""
    raw = generate_json(final_prompt, model, max_tokens=max(1200, min(2200, math.ceil(target_words * 2.5))))
    if progress_callback:
        progress_callback(None)  # clear
    return _normalize_summary(raw)


def exam(text, model, num_mcq=5, num_short=3):
    material = _trim_text(text)
    prompt = f"""Create an exam from this material. Return JSON:
- "mcq": {num_mcq} questions, each: {{"question","options":[4 strings],"correct_answer","explanation"(1 sentence),"topic"}}
- "short_answer": {num_short} questions, each: {{"question","model_answer"(max 30 words),"topic"}}

Material:
{material}

ONLY valid JSON."""
    return generate_json(prompt, model, max_tokens=900)


def flashcards(text, model, max_cards=10):
    material = _trim_text(text)
    prompt = f"""Generate {max_cards} flashcards from this material. Return a JSON array. Each item: {{"front":"question","back":"answer (max 20 words)"}}

Material:
{material}

ONLY a JSON array."""
    result = generate_json(prompt, model, max_tokens=700)
    if isinstance(result, list):
        return result
    return result.get("flashcards") or result.get("cards") or []


def quiz(text, model, num_questions=5):
    material = _trim_text(text)
    prompt = f"""Create {num_questions} multiple-choice quiz questions. Return JSON with key "questions", each: {{"question","options":[4 strings],"correct_answer"(must match an option),"topic","explanation"(1 sentence)}}

Material:
{material}

ONLY valid JSON."""
    return generate_json(prompt, model, max_tokens=700)


# ===========================================================================
# EDUCATION — QUICK Q&A (no document required)
# ===========================================================================

def education_qa_stream(question, model):
    """General-purpose tutor Q&A — no document required. Covers any subject:
    math, physics, biology, electronics, whatever the student asks."""
    prompt = f"""You are a friendly, knowledgeable tutor. A student asks: "{question}"

Answer clearly and helpfully in under 150 words. If it's a math or science
question, briefly show the key steps or reasoning. Include a relevant
formula if one applies. Keep the tone encouraging and easy to follow.

No markdown formatting."""
    yield from generate_stream(prompt, model, max_tokens=220)


# ===========================================================================
# HEALTHCARE / AGRICULTURE / EMERGENCY — streamed plain-text prompts
# ===========================================================================

def healthcare_stream(symptoms, model):
    prompt = f"""You are a health information assistant (NOT a doctor). A user reports: "{symptoms}"

In under 100 words, provide:
1. Possible common conditions (list 2-3)
2. General advice (1-2 sentences)
3. When to see a doctor (1 sentence)

End with: "This is general information, not medical advice."
No markdown formatting."""
    yield from generate_stream(prompt, model, max_tokens=180)


def agriculture_stream(query, crop, model):
    crop_part = f' Crop: "{crop}"' if crop else ""
    prompt = f"""You are an agricultural advisor. Question: "{query}"{crop_part}

In under 100 words, provide practical advice covering:
1. Direct answer
2. 2-3 best practices
3. One seasonal tip

No markdown formatting."""
    yield from generate_stream(prompt, model, max_tokens=180)


def emergency_stream(situation, model):
    prompt = f"""You are a first-aid information guide. Situation: "{situation}"

In under 100 words:
1. Immediate steps (numbered, max 4)
2. What NOT to do (1-2 items)
3. When to call emergency services

End with: "In a real emergency, call local emergency services immediately."
No markdown formatting."""
    yield from generate_stream(prompt, model, max_tokens=180)
