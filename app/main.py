# main.py

import streamlit as st

from eduforge.app.flashcards import render_deck_detail, render_deck_review, render_decks_section
from generated_items import render_generated_items_window
from notebooks import render_notebook_detail, render_notebook_review, render_notebooks_section
from sidebar import render_generation_sidebar
from utils.flashcards_db import init_db as init_flashcards_db, update_db_schema
from utils.notes_db import init_db as init_notes_db
from eduforge.app.quiz import render_quiz_section

def init_session_state():
    """Initialize session variables for flashcards, notebooks, tools, and generation view."""
    # Deck‑specific states
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
    if "view_card_id" not in st.session_state:
        st.session_state.view_card_id = None
    if "view_show_answer" not in st.session_state:
        st.session_state.view_show_answer = False
    if "selected_card_id" not in st.session_state:
        st.session_state.selected_card_id = None

    # Manage card field definitions per deck
    if "deck_fields" not in st.session_state:
        st.session_state.deck_fields = {}
    if "edit_fields" not in st.session_state:
        st.session_state.edit_fields = False

    # Notebook‑specific states
    if "selected_notebook_id" not in st.session_state:
        st.session_state.selected_notebook_id = None
    if "notebook_pending_delete" not in st.session_state:
        st.session_state.notebook_pending_delete = None
    if "selected_notebook_mode" not in st.session_state:
        st.session_state.selected_notebook_mode = None   # "browse" | "review"
    if "review_note_id" not in st.session_state:
        st.session_state.review_note_id = None
    if "review_note_edit_mode" not in st.session_state:
        st.session_state.review_note_edit_mode = False

    # For the Delete‑Tab dialog (unique keys to prevent collisions)
    if "delete_tab_dialog_open" not in st.session_state:
        st.session_state.delete_tab_dialog_open = False
    if "tab_to_delete" not in st.session_state:
        st.session_state.tab_to_delete = None

    # Track which tab (if any) is currently in "edit mode"
    if "editing_tab_id" not in st.session_state:
        st.session_state.editing_tab_id = None

    # AI generation states (for the "Generate Flashcards" tool)
    if "generated_cards" not in st.session_state:
        st.session_state.generated_cards = []
    if "generated_notes" not in st.session_state:
        st.session_state.generated_notes = []

    # Sidebar generation tool global vars
    if "gen_target_deck_id" not in st.session_state:
        st.session_state.gen_target_deck_id = None

    # Dedicated generation window view control
    if "generated_view" not in st.session_state:
        st.session_state.generated_view = False
    if "pre_gen_state" not in st.session_state:
        st.session_state.pre_gen_state = None

def main():
    # --- DB & session state init ---
    init_flashcards_db()
    update_db_schema()  # adds columns if missing
    init_notes_db()
    init_session_state()

    # --- Sidebar generation tool (always available) ---
    render_generation_sidebar()

    # --- Routing: dedicated generation view takes precedence ---
    if st.session_state.get("generated_view"):
        render_generated_items_window()
        return

    st.text("")

    # --- Regular routing ---
    if (st.session_state.selected_deck_id is not None) and (st.session_state.selected_deck_mode is not None):
        if st.session_state.selected_deck_mode == "browse":
            render_deck_detail(st.session_state.selected_deck_id)
        elif st.session_state.selected_deck_mode == "review":
            render_deck_review(st.session_state.selected_deck_id)

    elif st.session_state.selected_notebook_id is not None:
        if st.session_state.get("selected_notebook_mode") == "review":
            render_notebook_review(st.session_state.selected_notebook_id)
        else:
            render_notebook_detail(st.session_state.selected_notebook_id)

    else:
        # Main dashboard
        render_decks_section()
        st.divider()
        render_notebooks_section()
        st.divider()                 # << NEW spacer under notebooks
        render_quiz_section()        # << QUIZ now lives in‑page

if __name__ == "__main__":
    main()
