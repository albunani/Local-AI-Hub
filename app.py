"""
Local AI Hub — Gemma 4-Powered Offline Community Assistant

A Streamlit rebuild of the original HTML prototype, focused on the four
things that matter for judging: solid Gemma integration, a genuinely
offline story, a working prototype, and a clean, confident presentation.
"""

import streamlit as st

from document_utils import extract_text
from gemma_client import (
    agriculture_stream,
    describe_simple_source,
    describe_summary_source,
    education_qa_stream,
    emergency_stream,
    exam as gemma_exam,
    flashcards as gemma_flashcards,
    get_installed_models,
    healthcare_stream,
    quiz as gemma_quiz,
    summary as gemma_summary,
)

# ---------------------------------------------------------------------------
# Page config + styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Local AI Hub",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Keep the useful "⋮" menu (Settings, Rerun, Screencast recording, About) —
       just hide the Deploy button, since this project targets running locally,
       not publishing to Streamlit Community Cloud. */
    [data-testid="stAppDeployButton"] { display: none; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    /* Tighter top padding so content sits higher on the page */
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
    }

    /* Containers used as "response cards" */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px !important;
    }

    /* Sidebar polish */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    /* Title spacing */
    h1 { margin-bottom: 0.2rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "doc_text": None,
    "doc_name": None,
    "last_summary": None,
    "last_summary_source": None,
    "last_exam": None,
    "last_exam_source": None,
    "last_flashcards": None,
    "last_flashcards_source": None,
    "quiz_questions": None,
    "quiz_submitted": False,
    "quiz_answers": {},
    "quiz_source": None,
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# Sidebar — domain selector, model status, architecture note, footer
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 🧭 Local AI Hub")
    st.caption("Gemma 4-Powered Offline Community Assistant")
    st.divider()

    if "domain" not in st.session_state:
        st.session_state.domain = "education"

    _NAV_ITEMS = [
        {"key": "education", "label": "🎓 Education", "featured": True},
        {"key": "healthcare", "label": "🩺 Healthcare", "featured": False},
        {"key": "agriculture", "label": "🌾 Agriculture", "featured": False},
        {"key": "emergency", "label": "🆘 Emergency", "featured": False},
    ]

    for item in _NAV_ITEMS:
        is_selected = st.session_state.domain == item["key"]
        if st.button(
            item["label"],
            key=f"nav_{item['key']}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            # Streamlit already reruns the script automatically on any button
            # click — calling st.rerun() here would run the whole app twice
            # per click, which is what was causing the 2-4 second lag.
            st.session_state.domain = item["key"]
        if item["featured"]:
            st.markdown(
                '<div style="margin:-6px 0 12px 2px;">'
                '<span style="background:rgba(34,197,94,0.15);color:#22c55e;'
                'padding:2px 10px;border-radius:100px;font-size:0.68rem;font-weight:700;'
                'letter-spacing:0.04em;">⭐ FEATURED — FULL STUDY WORKFLOW</span></div>',
                unsafe_allow_html=True,
            )

    domain = st.session_state.domain

    st.divider()

    if "force_recheck" not in st.session_state:
        st.session_state.force_recheck = 0
    if st.button("🔄 Check Ollama Connection", use_container_width=True):
        st.session_state.force_recheck += 1
        get_installed_models.clear()  # drop the cache so this click reflects reality right now

    installed_models = get_installed_models()
    if installed_models:
        st.success("🟢 Ollama Connected")
        default_idx = 0
        for i, m in enumerate(installed_models):
            if "gemma" in m.lower():
                default_idx = i
                break
        model = st.selectbox("Model", installed_models, index=default_idx)
    else:
        st.error("🔴 Ollama Not Found")
        st.caption('Start it with:\n\n`OLLAMA_ORIGINS="*" ollama serve`')
        model = None

    with st.expander("🧠 How it works"):
        st.markdown(
            """
            ```
            User Question
                  │
                  ▼
             Choose Domain
                  │
                  ▼
            Local document?
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
            Education can either answer a quick question directly, or read
            an uploaded document first for deeper study tools. Healthcare,
            Agriculture, and Emergency always go straight to Gemma.
            """
        )

    st.divider()
    st.caption("Your local AI Node — powered entirely by Gemma 4. Runs locally without internet.")


def _require_model():
    if not model:
        st.warning("Connect Ollama to use this feature — see the sidebar for setup.")
        st.stop()


# ---------------------------------------------------------------------------
# EDUCATION
# ---------------------------------------------------------------------------

def render_education():
    st.title("🎓 Education")
    st.caption("Ask a quick question, or upload a document for a full study workflow.")

    mode = st.radio(
        "Education mode",
        ["💬 Ask a Question", "📚 Study from a Document"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    if mode == "💬 Ask a Question":
        _render_education_qa()
    else:
        _render_document_workflow()


def _render_education_qa():
    st.caption("Any subject — math, physics, biology, electronics, whatever you're working through.")
    _example_buttons(
        {
            "Newton's 3rd law": "Explain Newton's third law of motion simply",
            "Photosynthesis": "How does photosynthesis work?",
            "Quadratic formula": "How do I use the quadratic formula to solve equations?",
        },
        "edu_qa_input",
    )
    st.text_area("Your question", key="edu_qa_input", height=100)
    _stream_response(
        lambda: education_qa_stream(st.session_state.edu_qa_input, model),
        "Ask Gemma",
        "edu_qa_input",
    )


def _render_document_workflow():
    uploaded = st.file_uploader("Upload a document", type=["pdf", "txt", "md"])
    if uploaded is not None and uploaded.name != st.session_state.doc_name:
        with st.spinner("📄 Reading document…"):
            try:
                text = extract_text(uploaded)
                st.session_state.doc_text = text
                st.session_state.doc_name = uploaded.name
                st.session_state.last_summary = None
                st.session_state.last_summary_source = None
                st.session_state.last_exam = None
                st.session_state.last_exam_source = None
                st.session_state.last_flashcards = None
                st.session_state.last_flashcards_source = None
                st.session_state.quiz_questions = None
                st.session_state.quiz_submitted = False
                st.session_state.quiz_source = None
            except Exception as e:
                st.error(f"Could not read file: {e}")

    if not st.session_state.doc_text:
        st.info("Upload a PDF, TXT, or MD file to get started.")
        return

    st.success(f"📎 **{st.session_state.doc_name}** — {len(st.session_state.doc_text):,} characters loaded")

    tab_summary, tab_flash, tab_quiz, tab_exam = st.tabs(
        ["📄 Summary", "🧠 Flashcards", "🎯 Quiz", "📝 Generate Exam"]
    )
    with tab_summary:
        _render_summary_tab()
    with tab_flash:
        _render_flashcards_tab()
    with tab_quiz:
        _render_quiz_tab()
    with tab_exam:
        _render_exam_tab()


def _render_summary_tab():
    if st.button("Generate Summary", key="gen_summary", type="primary", use_container_width=True):
        _require_model()
        progress_box = st.empty()

        def on_progress(msg):
            if msg:
                progress_box.caption(msg)
            else:
                progress_box.empty()

        with st.spinner("🧠 Gemma is thinking locally…"):
            result = gemma_summary(st.session_state.doc_text, model, progress_callback=on_progress)
        progress_box.empty()

        if "_raw" in result:
            st.warning(
                "The model's response got cut off before it finished (this happens "
                "occasionally with smaller local models). Try again — it usually succeeds on a retry."
            )
            with st.expander("Raw output"):
                st.code(result["_raw"][:600])
        else:
            st.session_state.last_summary = result
            st.session_state.last_summary_source = describe_summary_source(st.session_state.doc_text)
            st.success("✅ Summary generated!")

    data = st.session_state.last_summary
    if data and "_raw" not in data:
        with st.container(border=True):
            st.markdown("#### Key Concepts")
            for c in data.get("key_concepts", []):
                st.markdown(f"- {c}")

            st.markdown("#### Must-Know Formulas")
            formulas = data.get("formulas", [])
            if formulas:
                for f in formulas:
                    st.markdown(f"**{f.get('name', '')}**")
                    st.code(f.get("formula", ""), language=None)
                    st.caption(f.get("description", ""))
            else:
                st.caption("No formulas found in this material.")

            st.markdown("#### Common Mistakes")
            for m in data.get("common_mistakes", []):
                st.markdown(f"⚠️ {m}")

            st.markdown("#### Revision Summary")
            st.info(data.get("revision_summary", ""))

        if st.session_state.last_summary_source:
            with st.expander("📚 Knowledge used for this answer"):
                st.caption(f"Document: **{st.session_state.doc_name}**")
                st.caption(st.session_state.last_summary_source)


def _render_exam_tab():
    if st.button("Generate Exam", key="gen_exam", type="primary", use_container_width=True):
        _require_model()
        with st.spinner("🧠 Gemma is thinking locally…"):
            data = gemma_exam(st.session_state.doc_text, model)
        if "_raw" in data:
            st.warning("The model's response didn't come back as valid JSON. Try again.")
        else:
            st.session_state.last_exam = data
            st.session_state.last_exam_source = describe_simple_source(st.session_state.doc_text)
            st.success("✅ Exam generated!")

    data = st.session_state.last_exam
    if data and "_raw" not in data:
        with st.container(border=True):
            mcqs = data.get("mcq", [])
            st.markdown(f"#### Multiple Choice ({len(mcqs)})")
            for i, q in enumerate(mcqs):
                st.markdown(f"**Q{i + 1}. {q.get('question', '')}**")
                for opt in q.get("options", []):
                    prefix = "✅ " if opt == q.get("correct_answer") else "◻️ "
                    st.markdown(f"{prefix}{opt}")
                st.caption(q.get("explanation", ""))
                st.markdown("---")

            short_answers = data.get("short_answer", [])
            st.markdown(f"#### Short Answer ({len(short_answers)})")
            for i, q in enumerate(short_answers):
                st.markdown(f"**Q{i + 1}. {q.get('question', '')}**")
                st.caption(f"Model answer: {q.get('model_answer', '')}")

        if st.session_state.last_exam_source:
            with st.expander("📚 Knowledge used for this answer"):
                st.caption(f"Document: **{st.session_state.doc_name}**")
                st.caption(st.session_state.last_exam_source)


def _render_flashcards_tab():
    if st.button("Generate Flashcards", key="gen_flash", type="primary", use_container_width=True):
        _require_model()
        with st.spinner("🧠 Gemma is thinking locally…"):
            cards = gemma_flashcards(st.session_state.doc_text, model)
        st.session_state.last_flashcards = cards
        if cards:
            st.session_state.last_flashcards_source = describe_simple_source(st.session_state.doc_text)
            st.success(f"✅ Generated {len(cards)} flashcards!")
        else:
            st.warning("Could not generate flashcards. Try a different document.")

    cards = st.session_state.last_flashcards
    if cards:
        cols = st.columns(2)
        for i, c in enumerate(cards):
            with cols[i % 2]:
                with st.expander(f"**{i + 1}.** {c.get('front', '')}"):
                    st.write(c.get("back", ""))

        if st.session_state.last_flashcards_source:
            with st.expander("📚 Knowledge used for this answer"):
                st.caption(f"Document: **{st.session_state.doc_name}**")
                st.caption(st.session_state.last_flashcards_source)


def _render_quiz_tab():
    if st.button("Start New Quiz", key="gen_quiz", type="primary", use_container_width=True):
        _require_model()
        with st.spinner("🧠 Gemma is thinking locally…"):
            data = gemma_quiz(st.session_state.doc_text, model)
        questions = data.get("questions", [])
        if questions:
            st.session_state.quiz_questions = questions
            st.session_state.quiz_submitted = False
            st.session_state.quiz_answers = {}
            st.session_state.quiz_source = describe_simple_source(st.session_state.doc_text)
        else:
            st.warning("Could not generate a quiz. Try a different document.")

    questions = st.session_state.quiz_questions
    if not questions:
        return

    if not st.session_state.quiz_submitted:
        with st.form("quiz_form"):
            answers = {}
            for i, q in enumerate(questions):
                answers[i] = st.radio(
                    f"**Q{i + 1}. {q['question']}**",
                    q["options"],
                    key=f"quiz_radio_{i}",
                    index=None,
                )
            if st.form_submit_button("Submit Quiz", type="primary", use_container_width=True):
                st.session_state.quiz_answers = answers
                st.session_state.quiz_submitted = True
                st.rerun()
    else:
        answers = st.session_state.quiz_answers
        score, topic_scores = 0, {}
        for i, q in enumerate(questions):
            correct = answers.get(i) == q.get("correct_answer")
            if correct:
                score += 1
            topic = q.get("topic", "General")
            topic_scores.setdefault(topic, {"c": 0, "n": 0})
            topic_scores[topic]["n"] += 1
            if correct:
                topic_scores[topic]["c"] += 1

        pct = round(score / max(len(questions), 1) * 100)
        weak = [t for t, s in topic_scores.items() if s["c"] / s["n"] < 0.5]
        strong = [t for t, s in topic_scores.items() if s["c"] / s["n"] >= 0.8]

        with st.container(border=True):
            st.markdown(f"## {score}/{len(questions)} — {pct}%")
            if weak:
                st.warning("Needs work: " + ", ".join(weak))
            if strong:
                st.success("Strong topics: " + ", ".join(strong))
            st.markdown("---")
            for i, q in enumerate(questions):
                correct = answers.get(i) == q.get("correct_answer")
                st.markdown(f"**{'✅' if correct else '❌'} Q{i + 1}. {q['question']}**")
                st.caption(f"Your answer: {answers.get(i, '—')} · Correct: {q.get('correct_answer')}")
                if q.get("explanation"):
                    st.caption(q["explanation"])

        if st.session_state.quiz_source:
            with st.expander("📚 Knowledge used for this answer"):
                st.caption(f"Document: **{st.session_state.doc_name}**")
                st.caption(st.session_state.quiz_source)

        if st.button("Try Another Quiz", key="retry_quiz"):
            st.session_state.quiz_questions = None
            st.session_state.quiz_submitted = False
            st.rerun()


# ---------------------------------------------------------------------------
# HEALTHCARE / AGRICULTURE / EMERGENCY — shared streaming pattern
# ---------------------------------------------------------------------------

def _example_buttons(examples, state_key):
    """Renders a row of example buttons that pre-fill the input on click."""
    cols = st.columns(len(examples))
    for col, (label, text) in zip(cols, examples.items()):
        if col.button(label, key=f"{state_key}_ex_{label}", use_container_width=True):
            st.session_state[state_key] = text


def _stream_response(stream_fn, button_label, state_key):
    """Runs the given streaming generator function into a bordered response card."""
    if st.button(button_label, key=f"{state_key}_submit", type="primary", use_container_width=True):
        _require_model()
        query = st.session_state.get(state_key, "").strip()
        if not query:
            st.warning("Please enter something first.")
            return
        with st.container(border=True):
            try:
                with st.spinner("🧠 Gemma is thinking locally…"):
                    full_text = st.write_stream(stream_fn())
            except Exception as e:
                st.error(f"Error: {e}")
                return

            if not full_text or not full_text.strip():
                st.warning(
                    "The model didn't return any text for this request. "
                    "Try again — this can happen on the very first call while the model loads into memory."
                )
            else:
                st.success("✅ Response generated")


def render_healthcare():
    st.title("🩺 Healthcare")
    st.caption("Describe symptoms and get general health information.")
    st.warning("⚠️ This is NOT medical advice. Always consult a qualified healthcare professional.")

    _example_buttons(
        {
            "Headache & fever": "headache and mild fever for 2 days",
            "Signs of malaria": "what are the signs of malaria?",
            "Persistent cough": "persistent cough and chest tightness for a week",
        },
        "healthcare_input",
    )
    st.text_area("Describe your symptoms", key="healthcare_input", height=100)
    _stream_response(
        lambda: healthcare_stream(st.session_state.healthcare_input, model),
        "Get Guidance",
        "healthcare_input",
    )


def render_agriculture():
    st.title("🌾 Agriculture")
    st.caption("Ask a crop question and get practical, seasonal advice.")

    _example_buttons(
        {
            "Prepare for maize": "How do I prepare farmland for maize?",
            "Cassava planting": "best planting season and pest control",
            "Rice yield": "How to improve rice yield in wet season?",
        },
        "agri_input",
    )
    crop = st.text_input("Crop type (optional)", key="agri_crop", placeholder="e.g., maize, cassava, rice")
    st.text_area("Your question", key="agri_input", height=100)
    _stream_response(
        lambda: agriculture_stream(st.session_state.agri_input, crop, model),
        "Get Advice",
        "agri_input",
    )


def render_emergency():
    st.title("🆘 Emergency")
    st.caption("Describe a situation and get immediate first-aid guidance.")
    st.error("🚨 In a real emergency, call your local emergency services immediately.")

    _example_buttons(
        {
            "Minor burn": "minor burn from hot water on hand",
            "Choking": "someone is choking on food",
            "Snakebite": "snakebite on lower leg",
        },
        "emergency_input",
    )
    st.text_area("Describe the situation", key="emergency_input", height=100)
    _stream_response(
        lambda: emergency_stream(st.session_state.emergency_input, model),
        "Get Guidance",
        "emergency_input",
    )


# ---------------------------------------------------------------------------
# Route to the selected domain
# ---------------------------------------------------------------------------

if domain == "education":
    render_education()
elif domain == "healthcare":
    render_healthcare()
elif domain == "agriculture":
    render_agriculture()
elif domain == "emergency":
    render_emergency()
