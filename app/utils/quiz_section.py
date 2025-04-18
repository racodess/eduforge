"""Quiz Section – AI‑generated MCQ component
--------------------------------------------------
Drop‑in module for EduForge Study Dashboard.
Call `render_quiz_section()` wherever you want the quiz to appear.
"""

from __future__ import annotations

import json
import os
import re
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
state = st.session_state  # quick alias

# ════════════════════════════════════════════════════════════════════════
# Helper callbacks and utils
# ════════════════════════════════════════════════════════════════════════

def _reset_counters() -> None:
    """Reset correct / incorrect counters and clear last result."""
    state.correct_counter = state.incorrect_counter = 0
    state.result = state.answer_message = ""


def _mark_correct() -> None:
    state.result, state.answer_message = "correct", "✅ Correct!"
    state.correct_counter = state.get("correct_counter", 0) + 1


def _mark_incorrect() -> None:
    state.result, state.answer_message = "incorrect", "❌ Incorrect!"
    state.incorrect_counter = state.get("incorrect_counter", 0) + 1


# robust JSON extractor ── handles ```json blocks, stray prose, single quotes
_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.I)

def _safe_json(text: str) -> dict | None:
    """Attempt to coerce *any* assistant reply into a JSON dict.

    Returns None if we still can't parse."""
    # prefer fenced block
    m = _JSON_RE.search(text)
    if m:
        text = m.group(1)

    # substring from first "{" to last "}"
    start, end = text.find("{"), text.rfind("}")
    if start != -1 < end:
        text = text[start : end + 1]

    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        return None


# ════════════════════════════════════════════════════════════════════════
# Main renderer
# ════════════════════════════════════════════════════════════════════════

def render_quiz_section() -> None:
    """Render the quiz UI inside the current Streamlit page."""

    # ── ensure all session keys exist ────────────────────────────────
    for k, v in [
        ("correct_counter", 0),
        ("incorrect_counter", 0),
        ("quiz_api_key", os.getenv("OPENAI_API_KEY", "")),
        ("difficulty_selected", False),
        ("difficulty", "None"),
        ("question", {}),
        ("conversation", []),
        ("show_question", False),
    ]:
        state.setdefault(k, v)

    # sample formats we instruct the model with (for prompt only)
    bare_fmt = {
        "title": "What is the capital of France?",
        "choices": ["Berlin", "Madrid", "Paris", "Rome"],
        "answer": 2,
    }
    code_fmt = {
        "title": "What is the output of the following Python code?",
        "code": "x = 1 + 1\nprint(x)",
        "choices": ["1", "2"],
        "answer": 1,
    }

    # ── UI container ────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<h2 style='text-align:center;'>Quiz&nbsp;📝</h2>",
            unsafe_allow_html=True,
        )

        # API key prompt if env var missing
        if not state.quiz_api_key:
            key_in = st.text_input("OpenAI API key", type="password")
            if key_in:
                state.quiz_api_key = key_in

        # topic input & generate button
        st.markdown(
            "<p style='text-align:center;'>What would you like to be quizzed on?</p>",
            unsafe_allow_html=True,
        )
        t1, t2 = st.columns([5, 2])
        topic = t1.text_input(
            "quiz_topic",
            label_visibility="collapsed",
            placeholder="Data Structures",
        )
        gen_clicked = t2.button("Generate ⚡", use_container_width=True)

        st.divider()

        # difficulty selector
        st.markdown(
            "<p style='text-align:center;'>Select a difficulty level</p>",
            unsafe_allow_html=True,
        )
        d1, d2, d3 = st.columns(3)
        if d1.button("Beginner", use_container_width=True):
            state.difficulty, state.difficulty_selected = "Beginner", True
        if d2.button("Intermediate", use_container_width=True):
            state.difficulty, state.difficulty_selected = "Intermediate", True
        if d3.button("Expert", use_container_width=True):
            state.difficulty, state.difficulty_selected = "Expert", True
        st.markdown(
            f"<p style='text-align:right;'><em>Selected: {state.difficulty}</em></p>",
            unsafe_allow_html=True,
        )

        st.divider()

        # ── question generation ────────────────────────────────────
        if gen_clicked:
            if not topic:
                st.warning("Please type a topic first."); st.stop()
            if not state.difficulty_selected:
                st.warning("Pick a difficulty."); st.stop()
            if not state.quiz_api_key:
                st.warning("Enter your OpenAI API key."); st.stop()

            client = OpenAI(api_key=state.quiz_api_key)
            prompt = (
                f"Generate ONE {state.difficulty} multiple‑choice question about {topic}. "
                f"Return ONLY JSON like {bare_fmt}. If code is needed use the 'code' field like {code_fmt}."
            )
            state.conversation = [{"role": "user", "content": prompt}]
            raw = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=state.conversation,
                temperature=0.7,
            ).choices[0].message.content

            parsed = _safe_json(raw)
            if parsed is None:
                st.error("Model returned malformed JSON:\n\n" + raw)
                st.stop()

            state.question = parsed
            state.show_question = True
            state.result = ""  # clear previous result

        # ── show question ──────────────────────────────────────────
        if state.show_question and state.question:
            q = state.question
            try:
                ans_index = int(q.get("answer", 0))
            except (TypeError, ValueError):
                ans_index = 0

            st.markdown(
                f"<h3 style='text-align:center;'>{q['title']}</h3>",
                unsafe_allow_html=True,
            )
            if "code" in q:
                st.code(q["code"], language="python")

            c_left, c_right = st.columns(2)
            for idx, choice_txt in enumerate(q["choices"]):
                col = c_left if idx % 2 == 0 else c_right
                callback = _mark_correct if idx == ans_index else _mark_incorrect
                col.button(
                    choice_txt,
                    key=f"ch_{idx}_{uuid4().hex[:6]}",
                    on_click=callback,
                    use_container_width=True,
                )

            # feedback message
            if state.result == "correct":
                st.success(state.answer_message)
            elif state.result == "incorrect":
                st.error(state.answer_message)

            # counters row
            st.text("")
            m1, m2 = st.columns(2)
            m1.metric("Correct", state.correct_counter)
            m2.metric("Incorrect", state.incorrect_counter)

            # actions row inside its own container
            with st.container():
                a1, a2 = st.columns(2)
                a1.button("Reset counters", on_click=_reset_counters, use_container_width=True)
                if a2.button("Generate similar", use_container_width=True):
                    state.result = ""
                    state.conversation.append({
                        "role": "user",
                        "content": (
                            "Generate another *different* question of the same difficulty and topic. "
                            "Same JSON format."
                        ),
                    })
                    raw2 = OpenAI(api_key=state.quiz_api_key).chat.completions.create(
                        model="gpt-4o-mini",
                        messages=state.conversation,
                        temperature=0.7,
                    ).choices[0].message.content
                    new_q = _safe_json(raw2)
                    if new_q is None:
                        st.error("Model returned malformed JSON:\n\n" + raw2)
                    else:
                        state.question = new_q
                        st.rerun()
