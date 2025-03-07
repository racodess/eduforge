# Imports
import streamlit as st


# Custom CSS for theme
with open('./ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)


# Content
st.title('eduForge 📖')
st.markdown('Welcome to **eduForge**! Enjoy your stay!')
st.markdown("""# Version Notes: eduForge v0.1.1
As promised, dropping this shi mid-week! Welcome to my bootleg ass patch notes for v0.1.1 (which I named because my devious ass is the first to name a version so I've taken the liberty to make up a name :smiling_imp:)
## Changes
Basic overview of changes made to eduForge
### File Structure
Folders
- ```NEW``` %/.streamlit - folder containing config files
- ```NEW``` %/app - folder containing webapp structure
- ```NEW``` %/ui_theme - folder containing Global CSS Values
- ```MOVE``` %/pages -> %/app/pages - folder restructuring

Files
- ```NEW``` %/run.bat - look man im lazy asf im not gonna type the command a morbillion times so i just made it pop up by typing ./run.bat
- ```NEW``` %/.streamlit/config.toml - streamlit theme config file
- ```NEW``` %/ui_theme/global.css - css file containing all global rulesets for style in webapp
- ```NEW``` %/pages/0_Menu.py - menu/landing for eduForge page
- ```RENAME/MOVE``` %/Anki_Flashcards.py -> %/app/pages/2_Anki-Flashcards.py
- ```RENAME/MOVE``` %/pages/2_Chatbot.py -> %/app/pages/3_Chatbot.py
- ```MOVE``` %/pages/1_Quiz.py -> %/app/pages/1_Quiz.py

### Run
The easiest way to run this app rn is to just run the command ./run.bat```, which just runs the run command for streamlit and opens up the site.

### UI Updates
Changed the color scheme to match Catpuccin Mocha, making it look kinda nice tho.
Made it a multi-page app that is swapable between the left side sidebar that responds to mobile too (altho its not gonna be used in mobile but still i get bragging rights).

That's all! Let me know if you have any questions! :)
""")