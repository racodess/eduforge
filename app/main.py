# main.py

"""
Entry point for the EduForge Streamlit application.
Initializes databases and session state, renders sidebar tools,
and routes to deck, notebook, quiz, or generation views based on state.
"""

import streamlit as st

from flashcards import (
    render_decks_section, render_deck_detail, render_deck_review
)
from generated_items import render_generated_items_window
from notebooks import (
    render_notebooks_section,
    render_notebook_detail,
    render_notebook_review
)
from sidebar import render_generation_sidebar
from utils.flashcards_db import init_db as init_flashcards_db, update_db_schema
from utils.notes_db import init_db as init_notes_db
from quiz import render_quiz_section


def init_session_state() -> None:
    """
    Ensure all expected Streamlit session_state keys exist with default values.
    Tracks selection, modes, and UI flags across flashcards, notebooks, and AI tools.
    """
    # Flashcards: selection, review, and deletion flags
    state = st.session_state
    state.setdefault("selected_deck_id", None)
    state.setdefault("selected_deck_mode", None) # "browse" or "review"
    state.setdefault("deck_pending_delete", None)
    state.setdefault("deck_pending_reset", None)
    state.setdefault("review_card_id", None)
    state.setdefault("review_show_answer", False)
    state.setdefault("review_edit_mode", False)
    state.setdefault("selected_stats_card_id", None)
    state.setdefault("view_card_id", None)
    state.setdefault("view_show_answer", False)
    state.setdefault("selected_card_id", None)
    state.setdefault("deck_fields", {}) # custom field definitions per deck

    # Notebooks: selection, deletion, and editing flags
    state.setdefault("selected_notebook_id", None)
    state.setdefault("notebook_pending_delete", None)
    state.setdefault("selected_notebook_mode", None) # "browse" or "review"
    state.setdefault("review_note_id", None)
    state.setdefault("review_note_edit_mode", False)
    state.setdefault("delete_tab_dialog_open", False)
    state.setdefault("tab_to_delete", None)
    state.setdefault("editing_tab_id", None)

    # AI Generation: store generated content and view flags
    state.setdefault("generated_cards", [])
    state.setdefault("generated_notes", [])
    state.setdefault("gen_target_deck_id", None)
    state.setdefault("generated_view", False) # dedicated generation output view
    state.setdefault("pre_gen_state", None) # store previous UI context


def main() -> None:
    """
    Application entry point: initialize resources, render sidebar, and route to views.
    """
    # Initialize SQLite databases and ensure schema is up-to-date
    init_flashcards_db()
    update_db_schema() # add missing columns if necessary
    init_notes_db()

    # Ensure session state has all needed keys
    init_session_state()

    # Always render the AI generation sidebar tool
    render_generation_sidebar()

    # If user is viewing generated items, show that view exclusively
    if st.session_state.get("generated_view"):
        render_generated_items_window()
        return

    # Spacer for layout
    st.text("")

    # Routing logic for flashcards
    deck_id = st.session_state.get("selected_deck_id")
    deck_mode = st.session_state.get("selected_deck_mode")
    if deck_id is not None and deck_mode is not None:
        if deck_mode == "browse":
            render_deck_detail(deck_id)
        elif deck_mode == "review":
            render_deck_review(deck_id)
        return

    # Routing logic for notebooks
    nb_id = st.session_state.get("selected_notebook_id")
    nb_mode = st.session_state.get("selected_notebook_mode")
    if nb_id is not None:
        if nb_mode == "review":
            render_notebook_review(nb_id)
        else:
            render_notebook_detail(nb_id)
        return

    # Default dashboard: show decks, notebooks, and quiz
    with st.container(border=True):
        render_decks_section()
    
    st.text("")
    st.text("")

    with st.container(border=True):
        render_notebooks_section()
    
    st.text("")
    st.text("")

    with st.container(border=True):
        render_quiz_section()


# Run the app
if __name__ == "__main__":
    main()
