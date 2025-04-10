# Imports
import streamlit as st


# Custom CSS for theme
with open('./ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)


# Content
st.title('eduForge 📖', anchor=False)
st.markdown('Welcome to **eduForge**! Enjoy your stay!')
st.markdown("""

# Version Notes: eduForge v0.1.3
            
## Changes
- Removed excess files
- Added environment variable integration of API Key for:
    - Quiz
    - Chatbot
- Updated the Quiz page to:
    - offer varying difficulty of questions
    - provide number of correct/incorrect attempts
    - enable the user to ask a similar question

### File Structure
            
- ```RENAME``` %/app/0_Menu.py → %/app/0_Updates.py            
- ```REMOVE``` %/pages/1_Quiz.py - extra file
- ```REMOVE``` %/pages/2_Chatbot.py - extra file
- ```UPDATE``` %/app/pages/3_Quiz.py - added multiple features (see changes)
- ```UPDATE``` Multiple files to remove anchor tags from title
            
---    

# Version Notes: eduForge v0.1.2
            
## Changes
- Added a Home page
- Reorganized page order in sidebar
- Updated the Quiz UI to correctly display answer feedback.

### File Structure
            
- ```NEW``` %/app/pages/1_Home.py - home page outlining eduForge
- ```RENAME/UPDATE``` %/app/pages/1_Quiz.py → %/app/pages/3_Quiz.py
- ```RENAME``` %/app/pages/3_Chatbot.py → %/app/pages/4_Chatbot.py 
            
---        

# Version Notes: eduForge v0.1.1
As promised, welcome to my patch notes for v0.1.1!
            
## Changes
Basic overview of changes made to eduForge
### File Structure
Folders
- ```NEW``` %/.streamlit - folder containing config files
- ```NEW``` %/app - folder containing webapp structure
- ```NEW``` %/ui_theme - folder containing Global CSS Values
- ```MOVE``` %/pages -> %/app/pages - folder restructuring

Files
- ```NEW``` %/run.bat - easier access to run
- ```NEW``` %/.streamlit/config.toml - streamlit theme config file
- ```NEW``` %/ui_theme/global.css - css file containing all global rulesets for style in webapp
- ```NEW``` %/pages/0_Menu.py - menu/landing for eduForge page
- ```RENAME/MOVE``` %/Anki_Flashcards.py -> %/app/pages/2_Anki-Flashcards.py
- ```RENAME/MOVE``` %/pages/2_Chatbot.py -> %/app/pages/3_Chatbot.py
- ```MOVE``` %/pages/1_Quiz.py -> %/app/pages/1_Quiz.py

### Run
The easiest way to run this app rn is to just run the command ./run.bat```, which just runs the run command for streamlit and opens up the site.

### UI Updates
Changed the color scheme to match Catpuccin Mocha, making it look kinda nice though.
Made it a multi-page app that is swapable between the left side sidebar that responds to mobile too.

That's all! Let me know if you have any questions! :)
""")