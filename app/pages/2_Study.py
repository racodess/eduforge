# 2_Study.py

import json
from datetime import datetime
import streamlit as st

# --- DB modules (unchanged) ---
from utils.flashcards_db import (
    init_db as init_flashcards_db,
    update_db_schema,
    get_decks, create_deck, trash_deck, reset_deck, get_deck_stats,
    get_cards, get_card_by_id, delete_card, update_card, add_card
)
from utils.notes_db import (
    init_db as init_notes_db,
    get_notebooks, create_notebook, delete_notebook, rename_notebook,
    get_notes, create_note, update_note, rename_note, delete_note
)

# --- SM-2 and other flashcards utilities (unchanged) ---
from utils.flashcards_sm2 import update_sm2, project_interval, format_interval_short
from utils.flashcards_ui import render_card_visual, render_card_form

# --- Helper for AI generation / file processing ---
from utils.file_helper import FileHelper


# --------------------------------------------------------------
#                   DEFAULT CONTENT FOR NOTEBOOKS
# --------------------------------------------------------------
DEFAULT_TAB_CONTENT = """\
# Welcome to Your Notebook!

This is your *default* tab. Each notebook must always have at least one tab.

## Quick Guide
- **Add** creates a new tab and immediately opens it in an edit form so you can name it and add notes. 
  - If you have only a single "Default" tab, it’s automatically removed right after the new one is created.
- **Edit** a tab to rename or modify it. You will see a "Save" and "Cancel" button for that tab.
- **Delete** a tab from the notebook-level "Delete" button (opens a dialog).
  
All tabs support **GitHub-Flavored Markdown** (headings, bold, italics, bullet lists, etc.). 
"""


# --------------------------------------------------------------
#                   Session State Setup
# --------------------------------------------------------------

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

# --------------------------------------------------------------
#               DIALOGS FOR DECK & NOTEBOOK CREATION
# --------------------------------------------------------------
@st.dialog("Create Deck", width="small")
def create_deck_dialog():
    """
    A Streamlit modal dialog for creating a new deck.
    Called by clicking "Create Deck" under the Flashcard Decks list.
    """
    st.write("Enter the name for your new deck:")
    new_deck_name = st.text_input("Deck Name")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create", key="create_deck_btn"):
            if new_deck_name.strip():
                create_deck(new_deck_name.strip())
                st.rerun()  # closes the dialog and refreshes
            else:
                st.error("Name cannot be empty.")

    with c2:
        # This Cancel button also triggers st.rerun() to close the dialog
        if st.button("Cancel", key="cancel_create_deck_btn"):
            st.rerun()


@st.dialog("Create Notebook", width="small")
def create_notebook_dialog():
    """
    A Streamlit modal dialog for creating a new notebook.
    Called by clicking "Create Notebook" under the Notebooks list.
    """
    st.write("Enter the name for your new notebook:")
    new_notebook_name = st.text_input("Notebook Name")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create", key="create_notebook_btn"):
            if new_notebook_name.strip():
                create_notebook(new_notebook_name.strip())
                st.rerun()
            else:
                st.error("Name cannot be empty.")
    with c2:
        if st.button("Cancel", key="cancel_create_notebook_btn"):
            st.rerun()


# --------------------------------------------------------------
#             DIALOGS FOR DECK & NOTEBOOK IMPORT
# --------------------------------------------------------------
@st.dialog("Import Deck", width="small")
def import_deck_dialog():
    """
    A Streamlit modal dialog for importing a Deck from a JSON file.
    Triggered by the "Import Deck" button in the Flashcard Decks section.
    """
    st.write("Upload a .json file containing your Deck data:")
    imported_file = st.file_uploader("Deck JSON file", type=["json"], key="import_deck_file")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Import", key="import_deck_button"):
            if imported_file is not None:
                try:
                    data = json.load(imported_file)
                    imported_deck_name = data.get("name", None)
                    cards_list = data.get("cards", [])

                    if imported_deck_name:
                        from utils.flashcards_db import c, conn
                        import sqlite3
                        try:
                            c.execute("INSERT INTO decks (name) VALUES (?)", (imported_deck_name,))
                            conn.commit()
                            new_deck_id = c.lastrowid
                            for card in cards_list:
                                front = card.get("front", "")
                                back = card.get("back", "")
                                c.execute("""
                                    INSERT INTO cards
                                       (deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (new_deck_id, front, back, None, 0, 0, 2.5, None))
                            conn.commit()
                            st.success(f"Deck '{imported_deck_name}' imported successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("A deck with that name already exists!")
                    else:
                        st.error("Invalid deck file format!")
                except Exception as e:
                    st.error(f"Error importing deck: {e}")
            else:
                st.error("Please select a .json deck file to import.")
    with c2:
        if st.button("Cancel", key="cancel_import_deck_btn"):
            st.rerun()


@st.dialog("Import Notebook", width="small")
def import_notebook_dialog():
    """
    A Streamlit modal dialog for importing a Notebook from a JSON file.
    Triggered by the "Import Notebook" button in the Notebooks section.
    """
    st.write("Upload a .json file containing your Notebook data:")
    imported_file = st.file_uploader("Notebook JSON file", type=["json"], key="import_notebook_file")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Import", key="import_notebook_button"):
            if imported_file is not None:
                try:
                    data = json.load(imported_file)
                    imported_nb_name = data.get("name", None)
                    notes_list = data.get("notes", [])

                    if imported_nb_name:
                        from utils.notes_db import c as notes_c, conn as notes_conn
                        import sqlite3
                        try:
                            notes_c.execute("INSERT INTO notebooks (name) VALUES (?)", (imported_nb_name,))
                            notes_conn.commit()
                            new_nb_id = notes_c.lastrowid

                            # Create each tab as a note in the new notebook
                            for note_item in notes_list:
                                tab_name = note_item.get("tab_name", "")
                                content = note_item.get("content", "")
                                if not tab_name.strip():
                                    tab_name = "Default"
                                notes_c.execute("""
                                    INSERT INTO notes (notebook_id, tab_name, content)
                                    VALUES (?, ?, ?)
                                """, (new_nb_id, tab_name, content))
                            notes_conn.commit()
                            st.success(f"Notebook '{imported_nb_name}' imported successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("A notebook with that name already exists!")
                    else:
                        st.error("Invalid notebook file format!")
                except Exception as e:
                    st.error(f"Error importing notebook: {e}")
            else:
                st.error("Please select a .json notebook file to import.")
    with c2:
        if st.button("Cancel", key="cancel_import_notebook_btn"):
            st.rerun()


# --------------------------------------------------------------
#          DIALOG FOR DELETING A TAB (Notebook-level)
# --------------------------------------------------------------
@st.dialog("Delete Notebook Tab", width="small")
def delete_tab_dialog(notebook_id: int):
    """
    A Streamlit modal dialog to delete a tab from a notebook.
    If user attempts to delete the only remaining tab, we create
    a new default tab first, so we never end up with zero tabs.
    """
    notes = get_notes(notebook_id)  # each => (id, tab_name, content)
    if not notes:
        st.error("No tabs to delete.")
        if st.button("OK", key="delete_tab_ok"):
            st.session_state.delete_tab_dialog_open = False
            st.rerun()
        return

    # Build a list of tab names
    tab_names = [n[1] for n in notes]  # n[1] = tab_name
    if "tab_to_delete" not in st.session_state or st.session_state.tab_to_delete not in tab_names:
        st.session_state.tab_to_delete = tab_names[0]  # pick the first tab by default

    st.write("Select which tab to delete:")
    st.session_state.tab_to_delete = st.selectbox(
        "Tab to delete",
        options=tab_names,
        index=tab_names.index(st.session_state.tab_to_delete),
        key="tab_to_delete_selectbox"
    )

    # Confirm / Cancel
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirm Delete", key="confirm_delete_tab"):
            # Find the note_id for the chosen tab
            note_id_to_delete = None
            for (nid, tname, _) in notes:
                if tname == st.session_state.tab_to_delete:
                    note_id_to_delete = nid
                    break

            if note_id_to_delete is None:
                st.error("Tab not found. Maybe it was already deleted.")
                st.session_state.delete_tab_dialog_open = False
                st.session_state.tab_to_delete = None
                st.rerun()

            # If there's only one tab left, create a new default tab before removing it
            if len(notes) == 1:
                create_note(notebook_id, "Default", DEFAULT_TAB_CONTENT)

            delete_note(note_id_to_delete)
            st.success(f"Deleted tab '{st.session_state.tab_to_delete}'.")
            st.session_state.delete_tab_dialog_open = False
            st.session_state.tab_to_delete = None
            st.rerun()

    with c2:
        if st.button("Cancel", key="cancel_delete_tab"):
            st.session_state.delete_tab_dialog_open = False
            st.session_state.tab_to_delete = None
            st.rerun()


# --------------------------------------------------------------
#                   Flashcard Decks Section
# --------------------------------------------------------------
def render_decks_section():
    """
    Renders the top-level table of flashcard decks.
    Adds "Create Deck" and "Import Deck" buttons (each open a dialog).
    """
    st.markdown("## Flashcard Decks")

    decks = get_decks()
    if decks:
        # Table header
        header_cols = st.columns([2, 1, 1, 1, 6])
        header_cols[0].markdown("**Deck**")
        header_cols[1].markdown("**New**")
        header_cols[2].markdown("**Learn**")
        header_cols[3].markdown("**Due**")

        for deck_id, deck_name in decks:
            stats = get_deck_stats(deck_id)
            row_cols = st.columns([2, 1, 1, 1, 6])
            row_cols[0].write(deck_name)
            row_cols[1].write(stats["new"])
            row_cols[2].write(stats["learn"])
            row_cols[3].write(stats["due"])

            # Actions
            with row_cols[4]:
                action_cols = st.columns(4)
                if action_cols[0].button("Review", key=f"review_deck_{deck_id}", use_container_width=True):
                    st.session_state.selected_deck_id = deck_id
                    st.session_state.selected_deck_mode = "review"
                    st.session_state.review_card_id = None
                    st.session_state.review_show_answer = False
                    st.session_state.review_edit_mode = False
                    st.rerun()

                if action_cols[1].button("Browse", key=f"browse_deck_{deck_id}", use_container_width=True):
                    st.session_state.selected_deck_id = deck_id
                    st.session_state.selected_deck_mode = "browse"
                    st.rerun()

                # Export
                cards_data = get_cards(deck_id)
                deck_data = {
                    "name": deck_name,
                    "cards": [{"front": c[1], "back": c[2]} for c in cards_data]
                }
                deck_json = json.dumps(deck_data, indent=2)
                action_cols[2].download_button(
                    "Export",
                    deck_json,
                    file_name=f"{deck_name}.json",
                    mime="application/json",
                    key=f"export_deck_{deck_id}",
                    use_container_width=True
                )

                if action_cols[3].button("Delete", key=f"delete_deck_{deck_id}", use_container_width=True):
                    st.session_state.deck_pending_delete = deck_id
                    st.rerun()

            # Confirm deck deletion
            if st.session_state.deck_pending_delete == deck_id:
                st.info(f"Are you sure you want to delete the deck '{deck_name}'?")
                confirm_cols = st.columns(2)
                if confirm_cols[0].button("Yes", key=f"confirm_delete_yes_{deck_id}", use_container_width=True):
                    trash_deck(deck_id)
                    st.success(f"Deck '{deck_name}' deleted!")
                    st.session_state.deck_pending_delete = None
                    st.rerun()
                if confirm_cols[1].button("No", key=f"confirm_delete_no_{deck_id}", use_container_width=True):
                    st.session_state.deck_pending_delete = None
                    st.rerun()
    else:
        st.info("No flashcard decks found.")

    # "Create Deck" and "Import Deck" buttons side-by-side
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("Create Deck", key="create_deck_top_btn"):
            create_deck_dialog()

    with c2:
        if st.button("Import Deck", key="import_deck_top_btn"):
            import_deck_dialog()


# --------------------------------------------------------------
#                   Notebooks Section
# --------------------------------------------------------------
def render_notebooks_section():
    """
    Displays all notebooks in a table, plus "Create Notebook" and "Import Notebook" buttons.
    """
    st.markdown("## Notebooks")

    notebooks = get_notebooks()
    if notebooks:
        header_cols = st.columns([2, 1, 1, 1, 6])
        header_cols[0].markdown("**Notebook**")
        header_cols[1].markdown("**New**")
        header_cols[2].markdown("**Learn**")
        header_cols[3].markdown("**Due**")

        for nb_id, nb_name in notebooks:
            row_cols = st.columns([2, 1, 1, 1, 6])
            row_cols[0].write(nb_name)
            row_cols[1].write("0")  # placeholder
            row_cols[2].write("0")
            row_cols[3].write("0")

            with row_cols[4]:
                action_cols = st.columns(4)
                if action_cols[0].button("Review", key=f"review_nb_{nb_id}", use_container_width=True):
                    st.warning("Notebook Review not implemented yet.")

                if action_cols[1].button("Browse", key=f"browse_nb_{nb_id}", use_container_width=True):
                    st.session_state.selected_notebook_id = nb_id
                    st.rerun()

                # Export
                notes_data = get_notes(nb_id)
                nb_data = {
                    "name": nb_name,
                    "notes": [
                        {"tab_name": n[1], "content": n[2]}
                        for n in notes_data
                    ]
                }
                nb_json = json.dumps(nb_data, indent=2)
                action_cols[2].download_button(
                    "Export",
                    nb_json,
                    file_name=f"{nb_name}.json",
                    mime="application/json",
                    key=f"export_nb_{nb_id}",
                    use_container_width=True
                )

                if action_cols[3].button("Delete", key=f"delete_nb_{nb_id}", use_container_width=True):
                    st.session_state.notebook_pending_delete = nb_id
                    st.rerun()

            # Confirm notebook deletion
            if st.session_state.notebook_pending_delete == nb_id:
                st.info(f"Are you sure you want to delete notebook '{nb_name}'?")
                confirm_cols = st.columns(2)
                if confirm_cols[0].button("Yes", key=f"confirm_nb_delete_yes_{nb_id}", use_container_width=True):
                    delete_notebook(nb_id)
                    st.success(f"Notebook '{nb_name}' deleted!")
                    st.session_state.notebook_pending_delete = None
                    st.rerun()
                if confirm_cols[1].button("No", key=f"confirm_nb_delete_no_{nb_id}", use_container_width=True):
                    st.session_state.notebook_pending_delete = None
                    st.rerun()
    else:
        st.info("No notebooks found.")

    # "Create Notebook" and "Import Notebook" buttons side-by-side
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("Create Notebook", key="create_notebook_top_btn"):
            create_notebook_dialog()
    with c2:
        if st.button("Import Notebook", key="import_notebook_top_btn"):
            import_notebook_dialog()


# --------------------------------------------------------------
#         Notebook Detail (Browse Selected Notebook)
# --------------------------------------------------------------
def render_notebook_detail(notebook_id: int):
    """Shows a single notebook page with Back, Add, Delete, and tab-by-tab content or editing."""
    from utils.notes_db import c as notes_c
    notes_c.execute("SELECT name FROM notebooks WHERE id = ?", (notebook_id,))
    row = notes_c.fetchone()
    if not row:
        st.error("This notebook does not exist.")
        st.session_state.selected_notebook_id = None
        return
    notebook_name = row[0]

    # Fetch existing tabs
    notes = get_notes(notebook_id)  # each => (id, tab_name, content)

    # If no tabs => create a default tab automatically
    if not notes:
        create_note(notebook_id, "Default", DEFAULT_TAB_CONTENT)
        st.rerun()

    # -- Top row: Back
    top_cols = st.columns([2, 8])
    with top_cols[0]:
        if st.button("Back", key="notebook_back_btn"):
            st.session_state.selected_notebook_id = None
            st.rerun()

    top_cols[1].markdown(f"<h2 style='text-align:left;'>{notebook_name}</h2>", unsafe_allow_html=True)

    # -- Second row: Add and Delete
    ad_cols = st.columns([1, 1, 8])
    with ad_cols[0]:
        if st.button("Add", key="notebook_add_tab_btn"):
            # Create a new empty tab
            new_tab_id = create_note(notebook_id, "New Tab", "")
            # If we had exactly 1 tab named "Default", remove it
            if len(notes) == 1 and notes[0][1] == "Default":
                delete_note(notes[0][0])
            # Immediately open the newly created tab in edit mode
            st.session_state.editing_tab_id = new_tab_id
            st.rerun()

    with ad_cols[1]:
        if st.button("Delete", key="notebook_delete_tab_btn"):
            st.session_state.delete_tab_dialog_open = True
            st.rerun()

    # If user triggered the Delete Tab dialog
    if st.session_state.get("delete_tab_dialog_open"):
        delete_tab_dialog(notebook_id)

    st.markdown("---")

    # Build the tab labels
    tab_labels = [n[1] for n in notes]  # n[1] = tab_name
    tab_objects = st.tabs(tab_labels)

    for i, (note_id, tab_name, content) in enumerate(notes):
        with tab_objects[i]:
            # Check if we're editing THIS tab
            is_editing = (st.session_state.editing_tab_id == note_id)

            if not is_editing:
                # View mode
                st.markdown(content if content else "*[Empty note]*", unsafe_allow_html=True)
                st.write("")
                if st.button("Edit", key=f"edit_tab_btn_{note_id}"):
                    st.session_state.editing_tab_id = note_id
                    st.rerun()
            else:
                # Edit mode
                with st.form(key=f"edit_tab_form_{note_id}", clear_on_submit=False):
                    new_tab_name = st.text_input("Tab Name", value=tab_name, key=f"tab_name_input_{note_id}")
                    new_content = st.text_area("Content:", value=content, height=300, key=f"tab_content_input_{note_id}")

                    s1, s2 = st.columns(2)
                    with s1:
                        if st.form_submit_button("Save"):
                            rename_note(note_id, new_tab_name)
                            update_note(note_id, new_content)
                            st.session_state.editing_tab_id = None
                            st.rerun()
                    with s2:
                        if st.form_submit_button("Cancel"):
                            st.session_state.editing_tab_id = None
                            st.rerun()


# --------------------------------------------------------------
#         Deck Detail (Browse Selected Deck) & Review
# --------------------------------------------------------------
def render_deck_detail(deck_id):
    from utils.flashcards_db import c
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("This deck does not exist.")
        st.session_state.selected_deck_id = None
        return

    deck_name = row[0]
    top_row = st.columns([2, 8, 2])
    if top_row[0].button("Back", key="deck_back_btn", use_container_width=True):
        st.session_state.selected_deck_id = None
        st.session_state.selected_deck_mode = None
        st.rerun()

    top_row[1].markdown(f"<h2 style='text-align:left;'>{deck_name}</h2>", unsafe_allow_html=True)

    if top_row[2].button("Reset Deck", key="reset_deck_btn", use_container_width=True):
        st.session_state.deck_pending_reset = deck_id
        st.rerun()

    if st.session_state.deck_pending_reset == deck_id:
        st.info(f"Are you sure you want to permanently reset SM‑2 stats for '{deck_name}'?")
        cc = st.columns(2)
        if cc[0].button("Yes", key="reset_deck_yes_btn", use_container_width=True):
            reset_deck(deck_id)
            st.success("Deck reset successfully!")
            st.session_state.deck_pending_reset = None
            st.rerun()
        if cc[1].button("No", key="reset_deck_no_btn", use_container_width=True):
            st.session_state.deck_pending_reset = None
            st.rerun()

    # If we’re editing the deck fields
    if deck_id not in st.session_state.deck_fields:
        st.session_state.deck_fields[deck_id] = ["Front", "Back"]
    if st.session_state.get("edit_fields", False):
        render_edit_fields(deck_id)
        return

    # If we’re editing a specific card
    card_to_edit = None
    if st.session_state.selected_card_id:
        card_to_edit = get_card_by_id(st.session_state.selected_card_id)
    editing = (card_to_edit is not None)

    # Render form for adding or editing a single card
    render_card_form(deck_id, editing, card_to_edit)
    st.divider()

    # Show existing cards
    cards_data = get_cards(deck_id)
    if not cards_data:
        st.info("No cards to display.")
        return

    ccols = st.columns([1, 6])
    with ccols[1]:
        hh = st.columns([1, 2, 1, 1, 1, 1])
        hh[0].markdown("**ID**")
        hh[1].markdown("**Front**")
        for (card_id, front, back) in cards_data:
            row = st.columns([1, 2, 1, 1, 1, 1])
            row[0].write(card_id)
            row[1].write(front)

            if row[2].button("View", key=f"view_{card_id}", use_container_width=True):
                if st.session_state.view_card_id == card_id:
                    st.session_state.view_card_id = None
                    st.session_state.view_show_answer = False
                else:
                    st.session_state.view_card_id = card_id
                    st.session_state.view_show_answer = False
                st.rerun()

            if row[3].button("Edit", key=f"edit_{card_id}", use_container_width=True):
                st.session_state.selected_card_id = card_id
                st.rerun()

            if row[4].button("Stats", key=f"stats_{card_id}", use_container_width=True):
                if st.session_state.get("selected_stats_card_id") == card_id:
                    st.session_state.selected_stats_card_id = None
                else:
                    st.session_state.selected_stats_card_id = card_id
                st.rerun()

            if row[5].button("Delete", key=f"delete_{card_id}", use_container_width=True):
                delete_card(card_id)
                st.success("Card deleted!")
                st.rerun()

            # If user clicked "Stats"
            if st.session_state.get("selected_stats_card_id") == card_id:
                card_full = get_card_by_id(card_id)
                if card_full:
                    _, _, _, _, next_review, interval, repetition, ef, _ = card_full
                    nr_str = "Not scheduled"
                    if next_review:
                        nr_str = datetime.fromisoformat(next_review).strftime("%Y-%m-%d %H:%M:%S")
                    st.markdown(
                        f"<div style='margin-left:40px;'>"
                        f"<strong>Next Review:</strong> {nr_str}<br>"
                        f"<strong>Interval:</strong> {interval} day(s)<br>"
                        f"<strong>Repetition:</strong> {repetition}<br>"
                        f"<strong>Ease Factor:</strong> {ef:.2f}"
                        f"</div><br>",
                        unsafe_allow_html=True
                    )

    # If "View" is toggled
    if st.session_state.view_card_id:
        card_to_view = get_card_by_id(st.session_state.view_card_id)
        if card_to_view:
            _, _, f_text, b_text, _, _, _, _, extra_json = card_to_view
            extras = {}
            if extra_json:
                try:
                    extras = json.loads(extra_json)
                except:
                    extras = {}
            st.markdown("---")
            st.markdown("### Card Preview")
            render_card_visual(f_text, b_text, extras=extras, show_back=st.session_state.view_show_answer)
            if st.button("Toggle Answer View", key="toggle_answer_view_btn"):
                st.session_state.view_show_answer = not st.session_state.view_show_answer
            if st.button("Done Viewing", key="done_viewing_btn"):
                st.session_state.view_card_id = None
                st.session_state.view_show_answer = False
                st.rerun()


def render_deck_review(deck_id):
    from utils.flashcards_db import c
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("This deck does not exist.")
        st.session_state.selected_deck_id = None
        return

    deck_name = row[0]
    top_row = st.columns([2, 8])
    if top_row[0].button("Back", key="review_deck_back_btn", use_container_width=True):
        st.session_state.selected_deck_id = None
        st.session_state.selected_deck_mode = None
        st.session_state.review_card_id = None
        st.session_state.review_show_answer = False
        st.session_state.review_edit_mode = False
        st.rerun()

    stats = get_deck_stats(deck_id)
    top_row[1].markdown(
        f"<h2 style='text-align:left;'>{deck_name} — Review</h2>"
        f"<p>New: {stats['new']} | Learn: {stats['learn']} | Due: {stats['due']}</p>",
        unsafe_allow_html=True
    )
    if stats["new"] == 0 and stats["due"] == 0:
        st.success("Congratulations! You have completed your review.")
        return

    st.divider()
    cards_data = get_cards(deck_id)
    if not cards_data:
        st.info("No cards to review.")
        return

    if st.session_state.review_card_id is None:
        st.session_state.review_card_id = cards_data[0][0]

    card = get_card_by_id(st.session_state.review_card_id)
    if not card:
        st.error("Selected card not found.")
        return

    card_id, _, front, back, next_review, interval, repetition, ef, extra_json = card
    if st.session_state.review_edit_mode:
        with st.form("edit_review_form", clear_on_submit=False):
            new_front = st.text_area("Edit Front", value=front)
            new_back = st.text_area("Edit Back", value=back)
            e1, e2 = st.columns(2)
            with e2:
                if st.form_submit_button("Save"):
                    if new_front.strip() and new_back.strip():
                        update_card(card_id, new_front.strip(), new_back.strip())
                        st.success("Card updated!")
                        st.session_state.review_edit_mode = False
                        st.rerun()
                    else:
                        st.error("Front and back must not be empty.")
            with e1:
                if st.form_submit_button("Cancel"):
                    st.session_state.review_edit_mode = False
                    st.rerun()
        return

    extras = {}
    if extra_json:
        try:
            extras = json.loads(extra_json)
        except:
            extras = {}

    render_card_visual(front, back, extras=extras, show_back=st.session_state.review_show_answer)
    st.divider()

    if not st.session_state.review_show_answer:
        if st.button("Show Answer", key="show_answer_btn", use_container_width=True):
            st.session_state.review_show_answer = True
            st.rerun()
    else:
        proj_again = format_interval_short(project_interval(card, 0))
        proj_hard  = format_interval_short(project_interval(card, 3))
        proj_good  = format_interval_short(project_interval(card, 4))
        proj_easy  = format_interval_short(project_interval(card, 5))

        h_cols = st.columns([2, 1, 1, 1, 1])
        h_cols[1].markdown(proj_again)
        h_cols[2].markdown(proj_hard)
        h_cols[3].markdown(proj_good)
        h_cols[4].markdown(proj_easy)

        b_cols = st.columns([2, 1, 1, 1, 1])
        if b_cols[0].button("Edit", key="review_edit_card", use_container_width=True):
            st.session_state.review_edit_mode = True
            st.rerun()
        if b_cols[1].button("Again", key="review_again_btn", use_container_width=True):
            update_sm2(card_id, 0)
            go_to_next_card(deck_id)
        if b_cols[2].button("Hard", key="review_hard_btn", use_container_width=True):
            update_sm2(card_id, 3)
            go_to_next_card(deck_id)
        if b_cols[3].button("Good", key="review_good_btn", use_container_width=True):
            update_sm2(card_id, 4)
            go_to_next_card(deck_id)
        if b_cols[4].button("Easy", key="review_easy_btn", use_container_width=True):
            update_sm2(card_id, 5)
            go_to_next_card(deck_id)


def go_to_next_card(deck_id):
    cards_data = get_cards(deck_id)
    if not cards_data:
        return
    c_ids = [c[0] for c in cards_data]
    current = st.session_state.review_card_id
    if current in c_ids:
        idx = c_ids.index(current)
        next_idx = (idx + 1) % len(c_ids)
        st.session_state.review_card_id = c_ids[next_idx]
        st.session_state.review_show_answer = False
        st.session_state.review_edit_mode = False
    st.rerun()


def render_edit_fields(deck_id):
    """
    Optional advanced function for deck field editing.
    """
    st.markdown("### Edit Card Fields")
    for i, field in enumerate(st.session_state.deck_fields[deck_id].copy()):
        c1, c2 = st.columns([4, 1])
        if field in ["Front", "Back"]:
            c1.text_input(
                f"Field {i+1} (Mandatory)",
                value=field,
                key=f"edit_field_{deck_id}_{i}",
                disabled=True
            )
        else:
            new_val = c1.text_input(
                f"Field {i+1}",
                value=field,
                key=f"edit_field_{deck_id}_{i}"
            )
            st.session_state.deck_fields[deck_id][i] = new_val
            if c2.button("Delete", key=f"delete_field_{deck_id}_{i}", use_container_width=True):
                st.session_state.deck_fields[deck_id].pop(i)
                st.rerun()

    nf = st.text_input("New Field Name", key=f"new_field_input_{deck_id}")
    if st.button("Add Field", key=f"add_field_button_{deck_id}", use_container_width=True):
        if nf and nf not in st.session_state.deck_fields[deck_id]:
            st.session_state.deck_fields[deck_id].append(nf)
            st.rerun()

    if st.button("Done Editing Fields", key=f"done_edit_fields_{deck_id}", use_container_width=True):
        st.session_state.edit_fields = False
        st.rerun()

# --------------------------------------------------------------
#              Tools – Generation (Sidebar)
# --------------------------------------------------------------

def render_generation_sidebar():
    """Generation tool now lives permanently in the sidebar."""
    with st.sidebar:
        st.markdown("## Generate Flashcards")

        # --- Select target deck ---
        decks = get_decks()
        if not decks:
            st.error("No decks available. Please create a deck first.")
            return

        deck_options = {dname: did for (did, dname) in decks}
        default_deck_name = list(deck_options.keys())[0]
        selected_deck_name = st.selectbox(
            "Select Deck to Add Flashcards",
            options=list(deck_options.keys()),
            index=list(deck_options.keys()).index(default_deck_name)
        )
        st.session_state.gen_target_deck_id = deck_options[selected_deck_name]

        # --- File / text / URL inputs ---
        file_helper = FileHelper()

        uploaded_file = st.file_uploader(
            label="Upload a .txt, .pdf, or image file",
            type=["txt", "pdf", "png", "jpg", "jpeg", "gif"],
            key="gen_file_uploader"
        )

        page_range = None
        if uploaded_file is not None and uploaded_file.name.lower().endswith('.pdf'):
            try:
                from PyPDF2 import PdfReader
                uploaded_file.seek(0)
                pdf_reader = PdfReader(uploaded_file)
                total_pages = len(pdf_reader.pages)
                uploaded_file.seek(0)
            except Exception:
                total_pages = 0
            sc1, sc2 = st.columns(2)
            start_page = sc1.number_input("Start Page", min_value=1, max_value=total_pages if total_pages else 1, value=1, step=1)
            end_page = sc2.number_input("End Page", min_value=1, max_value=total_pages if total_pages else 1, value=total_pages if total_pages else 1, step=1)
            page_range = (start_page, end_page)

        text_input = st.text_area("Or paste text content here", "", key="gen_text_input")
        url_input = st.text_input("Or provide a URL", "", key="gen_url_input")

        if st.button("Generate Flashcards", key="gen_button", use_container_width=True):
            final_text = ""
            if uploaded_file is not None:
                if uploaded_file.name.lower().endswith('.pdf') and page_range is not None:
                    final_text = file_helper.process_file(uploaded_file, start_page=page_range[0], end_page=page_range[1])
                else:
                    final_text = file_helper.process_file(uploaded_file)
            elif text_input.strip():
                final_text = file_helper.process_text(text_input.strip())
            elif url_input.strip():
                final_text = file_helper.process_url(url_input.strip())

            if not final_text:
                st.warning("No valid content provided!")
            else:
                generated_models = file_helper.generate_flashcards_pipeline(final_text)
                generated_cards = []
                for model_instance in generated_models:
                    if hasattr(model_instance, "flashcards"):
                        generated_cards.extend(model_instance.flashcards)
                st.session_state.generated_cards = generated_cards
                if generated_cards:
                    st.success(f"Generated {len(generated_cards)} flashcards!")
                    # Switch to dedicated window – store current context first
                    if not st.session_state.generated_view:
                        st.session_state.pre_gen_state = {
                            "selected_deck_id": st.session_state.get("selected_deck_id"),
                            "selected_deck_mode": st.session_state.get("selected_deck_mode"),
                            "selected_notebook_id": st.session_state.get("selected_notebook_id")
                        }
                        st.session_state.generated_view = True
                        st.rerun()
                else:
                    st.info("No flashcards were generated.")


# --------------------------------------------------------------
#      Dedicated Window for Viewing Generated Flashcards
# --------------------------------------------------------------

def render_generated_cards_window():
    """Full‑screen view for the cards produced by the sidebar generator."""
    # Top row: Back button + title
    top_cols = st.columns([2, 8])
    if top_cols[0].button("Back", key="gen_back_btn", use_container_width=True):
        # Restore context
        if st.session_state.pre_gen_state is not None:
            for k, v in st.session_state.pre_gen_state.items():
                st.session_state[k] = v
        st.session_state.generated_view = False
        st.session_state.pre_gen_state = None
        st.rerun()

    top_cols[1].markdown("<h2 style='text-align:left;'>Generated Flashcards</h2>", unsafe_allow_html=True)

    if not st.session_state.get("generated_cards"):
        st.info("No generated flashcards to display.")
        return

    target_deck_id = st.session_state.get("gen_target_deck_id")
    if target_deck_id is None:
        st.error("Target deck not found. Please regenerate cards and select a deck first.")
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    # Global Add/Delete buttons
    all_cols = st.columns(2)
    with all_cols[0]:
        if st.button("Add All", use_container_width=True):
            for card in st.session_state.generated_cards:
                add_card(target_deck_id, card.front, card.back, extra_fields=None)
            st.success("All generated flashcards have been imported to your deck!")
            st.session_state.generated_cards = []
            st.rerun()
    with all_cols[1]:
        if st.button("Delete All", use_container_width=True):
            st.session_state.generated_cards = []
            st.rerun()

    # Individual flashcard render loop
    for i, card in enumerate(st.session_state.generated_cards):
        center_cols = st.columns([1, 6, 1])
        with center_cols[1]:
            with st.container(border=True):
                st.markdown(
                    f'<div style="text-align: left; font-size: 16px;"><strong>Flashcard {i+1}</strong></div>',
                    unsafe_allow_html=True
                )
                st.text("")
                st.markdown('<div style="text-align: center;"><h3>Front</h3></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="text-align: center;">{card.front}</div>', unsafe_allow_html=True)
                st.text("")
                st.text("")
                st.markdown('<div style="text-align: center;"><h3>Back</h3></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="text-align: center;">{card.back}</div>', unsafe_allow_html=True)
                st.divider()
                btn_cols = st.columns(5)
                with btn_cols[1]:
                    if st.button("", key=f"gen_add_{i}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                        add_card(target_deck_id, card.front, card.back, extra_fields=None)
                        st.success(f"Added flashcard {i+1} to deck")
                        st.session_state.generated_cards.pop(i)
                        st.rerun()
                with btn_cols[2]:
                    if st.button("", key=f"gen_regen_{i}", type="tertiary", icon=":material/cached:", use_container_width=True):
                        new_card = FileHelper().regenerate_flashcard(card)
                        st.session_state.generated_cards[i] = new_card
                        st.rerun()
                with btn_cols[3]:
                    if st.button("", key=f"gen_delete_{i}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                        st.session_state.generated_cards.pop(i)
                        st.rerun()

# --------------------------------------------------------------
#                          Main App
# --------------------------------------------------------------

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
        render_generated_cards_window()
        return  # Skip the rest of the dashboard while in generated‑view mode

    # --- Title ---
    st.markdown("<div style='text-align: center; font-size: 36px;'><strong>Study Dashboard</strong></div>", unsafe_allow_html=True)
    st.text("")

    # --- Regular routing ---
    if (st.session_state.selected_deck_id is not None) and (st.session_state.selected_deck_mode is not None):
        if st.session_state.selected_deck_mode == "browse":
            render_deck_detail(st.session_state.selected_deck_id)
        elif st.session_state.selected_deck_mode == "review":
            render_deck_review(st.session_state.selected_deck_id)

    elif st.session_state.selected_notebook_id is not None:
        render_notebook_detail(st.session_state.selected_notebook_id)

    else:
        # Main dashboard
        render_decks_section()
        st.markdown("---")
        render_notebooks_section()
        # The old bottom‑of‑page Tools section has been removed now that the
        # generator lives permanently in the sidebar.


if __name__ == "__main__":
    main()
