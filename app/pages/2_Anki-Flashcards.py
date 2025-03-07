import streamlit as st
import os
import subprocess

st.set_page_config(
    page_title="EduForge",
    layout="centered"
)

# Custom CSS style [OUTDATED]
#page_style = """
#<style>
#    div.stButton > button:hover {
#        // background-color: #3498db !important;
#        background-color: #4CAF50 !important;
#        border-color: #4CAF50 !important;
#        color: white !important;
#    }
#</style>
#"""

# Apply the custom style to the Streamlit page
#st.markdown(page_style, unsafe_allow_html=True)


# Custom CSS for theme [UPDATED]
with open('././ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

st.header("Anki Flashcards", anchor=False)

topic = st.selectbox(
    "Select the file's topic",
    ["DSA", "Java", "OOP and OOD", "Problem Solving", "Python", "The Odin Project"]
)

# Example file upload
def save_uploaded_file(uploadedfile):
    with open(os.path.join(topic,uploadedfile.name),"wb") as f:
        f.write(uploadedfile.getbuffer())
    return st.success(uploaded_file.name + " successfully save in " + topic)

uploaded_file = st.file_uploader("Upload a file")
if uploaded_file is not None:
    save_uploaded_file(uploaded_file)

# Generate Flashcards
c1, c2, c3 = st.columns([1, 1, 1])
if c2.button('Generate Flashcards', use_container_width=True):

    # Run the command using subprocess
    result = subprocess.run([r'.\venv\Scripts\python.exe', 'main.py'], capture_output=True, text=True)

    # Display the output or any error
    st.write(result.stdout)
    st.write(result.stderr)