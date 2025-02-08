import streamlit as st

state = st.session_state

with st.container():
    st.write("What do you want to be quizzed on?")
    c1, c2 = st.columns([3, 1])
    c1.text_input("What do you want to be quizzed on?", label_visibility="collapsed", placeholder="Data Structures")
    generate_btn = c2.button("Generate Question", use_container_width=True)

if "generate_btn" not in state:
   state.generate_btn = False

if "question" not in state:
    state.question = ""

if generate_btn:
    state.generate_btn = True

if st.session_state.generate_btn:
    st.header("Question", divider=True, anchor=False)
    st.subheader("What color is red?", anchor=False)

    c1, c2 = st.columns(2)

    with c1:
        a1 = st.button("Orange", use_container_width=True)
        a2 = st.button("Red", use_container_width=True)
    with c2:
        a3 = st.button("Blue", use_container_width=True)
        a4 = st.button("Green", use_container_width=True)

    if a1 or a2 or a3 or a4:
        st.info("Red")