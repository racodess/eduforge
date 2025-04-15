# 2_Flashcards.py

import streamlit as st

from utils.flashcards_db import init_db, update_db_schema
from utils.flashcards_pages import (
    render_deck_list,
    render_deck_detail,
    render_deck_review
)

# Custom CSS for theme
with open('./ui-theme/global.css') as f:
    css = f.read()
st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

# ------------- Session State Setup -------------
if "selected_deck_id" not in st.session_state:
    st.session_state.selected_deck_id = None
if "selected_deck_mode" not in st.session_state:
    st.session_state.selected_deck_mode = None  # "browse" or "review"
if "deck_pending_delete" not in st.session_state:
    st.session_state.deck_pending_delete = None
if "deck_pending_reset" not in st.session_state:
    st.session_state.deck_pending_reset = None

if "review_card_id" not in st.session_state:
    st.session_state.review_card_id = None
if "review_show_answer" not in st.session_state:
    st.session_state.review_show_answer = False
if "review_edit_mode" not in st.session_state:
    st.session_state.review_edit_mode = False

if "selected_stats_card_id" not in st.session_state:
    st.session_state.selected_stats_card_id = None

# For managing card field definitions per deck
if "deck_fields" not in st.session_state:
    st.session_state.deck_fields = {}

# “View” mode states in the Browse screen
if "view_card_id" not in st.session_state:
    st.session_state.view_card_id = None
if "view_show_answer" not in st.session_state:
    st.session_state.view_show_answer = False

# ------------- Database Initialization -------------
init_db()
update_db_schema()

# ------------- Main Page Logic -------------
def main():
    st.markdown(
        f'<div style="text-align: center; font-size: 36px;"><strong>Flashcards</strong></div>',
        unsafe_allow_html=True
    )
    st.text("")
    st.text("")
    
    if st.session_state.selected_deck_id is None:
        # Show deck list
        render_deck_list()
    else:
        # Show deck detail or deck review
        if st.session_state.selected_deck_mode == "browse":
            render_deck_detail(st.session_state.selected_deck_id)
        elif st.session_state.selected_deck_mode == "review":
            render_deck_review(st.session_state.selected_deck_id)

if __name__ == "__main__":
    main()
