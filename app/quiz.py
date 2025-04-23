# quiz.py

"""
Implements a multiple-choice quiz interface using Streamlit and OpenAI API.
Provides helper functions for state management and JSON parsing,
and renders a quiz section with question generation, difficulty selection,
and answer evaluation.
"""

from __future__ import annotations

import json
import os
import re
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from a .env file, including OPENAI_API_KEY
load_dotenv()

# Alias for Streamlit session state for convenience
state = st.session_state  # quick alias

"""
Helper callbacks and utility functions
"""

def _reset_counters() -> None:
    """
    Reset the quiz result counters and clear the last result message.
    """
    # Reset correct and incorrect counters to zero
    state.correct_counter = state.incorrect_counter = 0

    # Clear result and answer message
    state.result = state.answer_message = ""


def _mark_correct() -> None:
    """
    Mark the current answer as correct: update state and increment counter.
    """
    state.result = "correct"
    state.answer_message = "✅ Correct!"

    # Safely get current correct count or default to 0, then increment
    state.correct_counter = state.get("correct_counter", 0) + 1


def _mark_incorrect() -> None:
    """
    Mark the current answer as incorrect: update state and increment counter.
    """
    state.result = "incorrect"
    state.answer_message = "❌ Incorrect!"
    # Safely get current incorrect count or default to 0, then increment
    state.incorrect_counter = state.get("incorrect_counter", 0) + 1

# Regular expression to extract JSON content from text, handling fenced blocks
_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.I)

def _safe_json(text: str) -> dict | None:
    """
    Attempt to extract and parse JSON from a text response.
    Handles fenced JSON blocks, stray prose, and single quotes.
    Returns a dict if successful, otherwise None.
    """
    # Search for a fenced JSON block first
    m = _JSON_RE.search(text)
    if m:
        text = m.group(1)

    # Fallback: take substring from first '{' to last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end+1]

    # Replace single quotes and attempt JSON parse
    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        return None

# Main quiz UI renderer
def render_quiz_section() -> None:
    """
    Render the quiz user interface in the current Streamlit page.
    Includes API key input, topic and difficulty selection,
    question generation, display, and answer evaluation.
    """
    # Ensure all expected session state keys are initialized
    for key, default in [
        ("correct_counter", 0),
        ("incorrect_counter", 0),
        ("quiz_api_key", os.getenv("OPENAI_API_KEY", "")),
        ("difficulty_selected", False),
        ("difficulty", "None"),
        ("question", {}),
        ("conversation", []),
        ("show_question", False),
    ]:
        state.setdefault(key, default)

    # Sample JSON formats for instructing the model
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

    # Section header
    st.markdown(
        "<h2 style='text-align:center;'>Quiz 📝</h2>",
        unsafe_allow_html=True,
    )

    # Prompt for OpenAI API key if not already set
    if not state.quiz_api_key:
        key_input = st.text_input("OpenAI API key", type="password")
        if key_input:
            state.quiz_api_key = key_input

    # Topic input field and generate button
    st.markdown(
        "<p style='text-align:center;'>What would you like to be quizzed on?</p>",
        unsafe_allow_html=True,
    )
    topic_col, button_col = st.columns([5, 2])
    topic = topic_col.text_input(
        "quiz_topic",
        label_visibility="collapsed",
        placeholder="Data Structures",
    )
    generate_clicked = button_col.button("", type="secondary", icon=":material/send:", use_container_width=True)

    st.text("")
    st.text("")
    st.text("")
    st.text("")

    # Difficulty selection buttons
    st.markdown(
        "<p style='text-align:center;'>Select a difficulty level</p>",
        unsafe_allow_html=True,
    )
    beg_col, int_col, exp_col = st.columns(3)
    if beg_col.button("Easy", use_container_width=True):
        state.difficulty, state.difficulty_selected = "Easy", True
    if int_col.button("Medium", use_container_width=True):
        state.difficulty, state.difficulty_selected = "Medium", True
    if exp_col.button("Hard", use_container_width=True):
        state.difficulty, state.difficulty_selected = "Hard", True

    # Display current difficulty
    st.markdown(
        f"<p style='text-align:right;'><em>Selected: {state.difficulty}</em></p>",
        unsafe_allow_html=True,
    )

    st.text("")
    st.text("")


    with st.container():
        # Handle question generation when button is clicked
        if generate_clicked:
            # Validate inputs
            if not topic:
                st.warning("Please type a topic first.")
                st.stop()
            if not state.difficulty_selected:
                st.warning("Pick a difficulty.")
                st.stop()
            if not state.quiz_api_key:
                st.warning("Enter your OpenAI API key.")
                st.stop()

            # Initialize OpenAI client and prepare prompt
            client = OpenAI(api_key=state.quiz_api_key)
            prompt = (
                f"Generate ONE {state.difficulty} multiple‑choice question about {topic}. "
                f"Return ONLY JSON like {bare_fmt}. If code is needed use the 'code' field like {code_fmt}."
            )
            state.conversation = [{"role": "user", "content": prompt}]

            # Request a completion from the model
            raw_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=state.conversation,
                temperature=0.7,
            ).choices[0].message.content

            # Parse the JSON response safely
            parsed_question = _safe_json(raw_response)
            if parsed_question is None:
                st.error("Model returned malformed JSON:\n\n" + raw_response)
                st.stop()

            # Update state with the new question and prepare to display it
            state.question = parsed_question
            state.show_question = True
            state.result = "" # Clear any previous result feedback

        # Display the question and choices if available
        if state.show_question and state.question:
            q = state.question
            try:
                answer_index = int(q.get("answer", 0))
            except (TypeError, ValueError):
                answer_index = 0

            # Show question title
            st.markdown(
                f"<h3 style='text-align:center;'>{q['title']}</h3>",
                unsafe_allow_html=True,
            )

            # Show code block if question includes code
            if "code" in q:
                st.code(q["code"], language="python")

            st.text("")
            st.text("")
            st.text("")
            st.text("")

            # Arrange choice buttons in two columns
            col_left, col_right = st.columns(2)
            for idx, choice_text in enumerate(q["choices"]):
                current_col = col_left if idx % 2 == 0 else col_right

                # Assign correct or incorrect callback based on answer index
                click_callback = _mark_correct if idx == answer_index else _mark_incorrect
                current_col.button(
                    choice_text,
                    key=f"ch_{idx}_{uuid4().hex[:6]}",
                    on_click=click_callback,
                    use_container_width=True,
                )

            # Provide feedback message based on user's answer
            if state.result == "correct":
                st.success(state.answer_message)
            elif state.result == "incorrect":
                st.error(state.answer_message)

            st.text("")
            st.text("")
            st.divider()

            # Display counters for correct/incorrect answers
            st.text("")  # Spacer
            metric_col1, metric_col2 = st.columns(2)
            metric_col1.metric("Correct", state.correct_counter)
            metric_col2.metric("Incorrect", state.incorrect_counter)

            # Action buttons: reset counters or generate similar question
            reset_col, similar_col = st.columns(2)
            reset_col.button("", on_click=_reset_counters, type="secondary", icon=":material/delete_history:", use_container_width=True)

            if similar_col.button("", type="secondary", icon=":material/autorenew:", use_container_width=True):
                # Clear previous result and append follow-up prompt
                state.result = ""
                state.conversation.append({
                    "role": "user",
                    "content": (
                        "Generate another *different* question of the same difficulty and topic. "
                        "Same JSON format."
                    ),
                })
                # Call OpenAI to get a new question
                new_raw = OpenAI(api_key=state.quiz_api_key).chat.completions.create(
                    model="gpt-4o-mini",
                    messages=state.conversation,
                    temperature=0.7,
                ).choices[0].message.content

                # Parse and handle new question response
                new_question = _safe_json(new_raw)
                if new_question is None:
                    st.error("Model returned malformed JSON:\n\n" + new_raw)
                else:
                    state.question = new_question
                    st.rerun()
