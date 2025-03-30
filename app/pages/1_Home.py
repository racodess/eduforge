import streamlit as st

# Custom CSS for theme
with open('././ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

# Remove anchor tags
st.html("<style>[data-testid='stHeaderActionElements'] {display: none;}</style>")

st.header("eduForge", anchor=False)
st.caption("AI ENHANCED LEARNING")

st.divider()

col1, col2 = st.columns([3, 4])
col1.markdown("""
    # Here to help :violet[optimize] your learning

    eduForge will aid your pathway to becoming a Software Engineer!
""")
col2.image("media/code.jpg")

st.divider()

st.markdown("""
    ### Key Features

    - **Flashcards**: Leverage AI to transform data covering software engineering topics from uploaded PDF files, URLs, or text files into highly effective flashcards.
    - **Quiz Questions**: To further support your flashcards, enhance your learning with AI-generated quiz questions tailored to any topic of your choice.
    - **Latest Updates**: Stay in the loop with our latest features and improvements, ensuring you never miss a new addition!
            
    ### Usage
    
    To get started, simply navigate using the sidebar menu. <br /> <br /> 
    *Check the requirements below to make sure you have all dependencies installed depending on what feature you would like to use.*
            
    ### Requirements
    - [Python 3.12+](https://www.python.org/)
    - [OpenAI API Key](https://openai.com/api/)

    ### Feedback
    
    We are welcome to feedback! If you encounter any issues or simply want to provide suggestions, please open an issue on our [github](https://github.com/racodess/eduforge)!

    ### Credits
            
    Image courtesy of [Luis Gomes](https://www.pexels.com/photo/close-up-photo-of-programming-of-codes-546819/).

""", unsafe_allow_html=True)