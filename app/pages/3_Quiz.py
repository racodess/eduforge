import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()
state = st.session_state

# Custom CSS for theme
with open('././ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)


openai_api_key = os.getenv("OPENAI_API_KEY")
with st.sidebar:
#     openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
    "[Need an OpenAI API key?](https://openai.com/api/)"

output_format = {
    "title": "What is the capital of France?",
    "choices": ["Berlin", "Madrid", "Paris", "Rome"],
    "answer": 2
}

output_format_with_code = {
    "title": "What is the output of the following Python code snippet?",
    "code": "\n\nx = 5\ny = 2\nz = x + y * 10\nprint(z)",
    "choices": ["22", "42", "62", "82"],
    "answer": 1
}

def reset_counters():
    state.correct_counter = 0
    state.incorrect_counter = 0
    return

def correct_function():
    state.result = "correct"
    state.answer_message = "Correct!"
    state.correct_counter = state.get("correct_counter", 0) + 1
    return

def incorrect_function():
    state.result = "incorrect"
    state.answer_message = "Incorrect!"
    state.incorrect_counter = state.get("incorrect_counter", 0) + 1
    return

# Initialize states
if "correct_counter" not in state:
    state.correct_counter = 0

if "incorrect_counter" not in state:
    state.incorrect_counter = 0

if "generate_btn" not in state:
   state.generate_btn = False

if "question" not in state:
    state.question = ""

if "result" not in state:
    state.result = None

if "answer_message" not in state:
    state.answer_message = ""

if "difficulty_selected" not in state:
    state.difficulty_selected = False
    state.difficulty = "None"

# Input Quiz Phrase
with st.container():
    st.title("Quiz 📝", anchor=False)
    st.text("What would you like to be quizzed on?")
    c1, c2 = st.columns([5, 2])
    user_input = c1.text_input("What do you want to be quizzed on?", label_visibility="collapsed", placeholder="Data Structures")
    generate_btn = c2.button("Generate New Question", use_container_width=True)

st.divider()

# Select Difficulty
with st.container():
    st.text("Select a level of difficulty")
    c1, c2, c3 = st.columns([2, 2, 2])
    beginner_btn = c1.button("Beginner", use_container_width=True)
    intermediate_btn = c2.button("Intermediate", use_container_width=True)
    expert_btn = c3.button("Expert", use_container_width=True)

    if beginner_btn:
        state.difficulty = "Beginner"
    elif intermediate_btn:
        state.difficulty = "Intermediate"
    elif expert_btn:
        state.difficulty = "Expert"

    if beginner_btn or intermediate_btn or expert_btn:
        state.difficulty_selected = True

# Display Selected Difficulty
st.markdown(
    f"""
        <div style="text-align: right;">
            Selected Difficulty: {state.difficulty}
        </div>
    """,
    unsafe_allow_html=True
)

st.divider()

# Generate Question
if generate_btn:
    # Check for empty input
    if not user_input:
        st.info("Please enter a word or phrase to generate a question.")
        st.stop()

    # Check difficulty level
    if not state.difficulty_selected:
        st.info("Please select a difficulty level.")
        st.stop()

    # Check for api key
    if not openai_api_key:
        st.info("Please add an OpenAI API key to continue.")
        st.stop()

    # Clear result from previous question
    state.result = None

    # Make request for question
    client = OpenAI(api_key=openai_api_key)
    state.message = [{
        "role": "user", 
        "content": f"Generate a {state.difficulty} level question regarding {user_input}. Follow the exact output format: {output_format}. The answer must be an index (an intenger) pointing to the correct choice. If there is a code snippet, follow the format {output_format_with_code}."
    }]

    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=state.message
    )

    output = response.choices[0].message.content
    state.message.append({"role": "assistant", "content": output})
    output = output.replace('"', '\\"').replace("'", '"')

    state.question = json.loads(output)
    state.generate_btn = True

# Display question
if state.generate_btn:
    st.header("Question", divider=True, anchor=False)

    question = state["question"]
    answer = question["choices"][int(question["answer"])]

    st.subheader(question["title"], anchor=False)
    if "code" in question:
        st.markdown(f"```{question["code"]}", unsafe_allow_html=True)

    cols = st.columns(2)

    for i, choice in enumerate(question["choices"]):
        col = cols[i % 2]
        with col:
            if choice == answer:
                st.button(
                    choice,
                    key=choice,
                    use_container_width=True,
                    on_click=correct_function
                )
            else:
                st.button(
                    choice,
                    key=choice,
                    use_container_width=True,
                    on_click=incorrect_function
                )

    # Display results
    if state.result == "correct":
        st.success(state.answer_message)
    elif state.result == "incorrect":
        st.error(state.answer_message)

    # Metric Padding        
    if not state.result:
        st.markdown(
            f"""
                <div style="margin-top: 72px"></div>
            """,
            unsafe_allow_html=True
        )

    # Display metrics
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        c1.metric("Correct Attempts", state.correct_counter)

        with c2.container():
            st.write("")
            reset_btn = st.button("Reset Attempts", on_click=reset_counters, use_container_width=True)

        c3.markdown(
            f"""
                <div style="text-align: right; display: flex; flex-direction: column;">
                    <p style="margin: 0">Incorrect Attempts</p>
                    <p style="font-size: 2.25rem; line-height: normal;">{state.incorrect_counter}</p>
                </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")
    c1, c2, c3 = st.columns([2, 2, 2])
    generate_similar_btn = c2.button("Generate Similar Question", use_container_width=True)

    if generate_similar_btn:
        # Clear result from previous question
        state.result = None

        # Append new question to conversation
        state.message.append({
            "role": "user", 
            "content": f"Generate a different but similar question of {state.difficulty} difficulty regarding {user_input}. Follow the same output format."
        })

        # Make request for question
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=state.message
        )

        output = response.choices[0].message.content
        state.message.append({"role": "assistant", "content": output})
        output = output.replace('"', '\\"').replace("'", '"')

        state.question = json.loads(output)
        st.rerun()