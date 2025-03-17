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


#openai_api_key = os.getenv("OPENAI_API_KEY")
with st.sidebar:
    openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
    "[Get an OpenAI API key](https://platform.openai.com/account/api-keys)"

output_format = {
    "title": "Question goes here.",
    "choices": ["choice1", "choice2", "choice3", "choice4"],
    "answer": "index of answer from choices array"
}

with st.container():
    st.title("Quiz 📝")
    st.text("What would you like to be quizzed on?")
    c1, c2 = st.columns([3, 1])
    user_input = c1.text_input("What do you want to be quizzed on?", label_visibility="collapsed", placeholder="Data Structures")
    generate_btn = c2.button("Generate Question", use_container_width=True)

if "generate_btn" not in state:
   state.generate_btn = False

if "question" not in state:
    state.question = ""

if "answer_message" not in state:
    state.result = None
    state.answer_message = ""

if generate_btn:
    # Check for empty input
    if not user_input:
        st.info("Please enter a word or phrase to generate a question.")
        st.stop()

    # Check for api key
    if not openai_api_key:
        st.info("Please add your OpenAI API key to continue.")
        st.stop()

    # Make request for question
    client = OpenAI(api_key=openai_api_key)
    state.message = [{
        "role": "user", 
        "content": f"Generate a question regarding {user_input}. Follow example json output format: {output_format}"
    }]

    response = client.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=state.message
    )

    output = response.choices[0].message.content
    output = output.replace('"', '\\"').replace("'", '"')

    state.question = json.loads(output)
    state.generate_btn = True

# Display question
if state.generate_btn:
    state.result = None

    st.header("Question", divider=True, anchor=False)

    question = state["question"]
    answer = question["choices"][int(question["answer"])]

    st.subheader(question["title"], anchor=False)

    cols = st.columns(2)

    for i, choice in enumerate(question["choices"]):
        col = cols[i % 2]
        with col:
            if st.button(choice, key=choice, use_container_width=True):
                if choice == answer:
                    st.session_state.result = "correct"
                    state.answer_message = "Correct!"
                else:
                    st.session_state.result = "incorrect"
                    state.answer_message = "Incorrect!"

    if state.result == "correct":
        st.success(state.answer_message)
    elif state.result == "incorrect":
        st.error(state.answer_message)