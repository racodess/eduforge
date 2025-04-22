# dialogs.py

"""
Defines modal dialogs for creating and importing decks, notebooks, and deleting notebook tabs.
Utilizes Streamlit's @st.dialog decorator for user interactions in pop-up windows.
"""

import json
import streamlit as st

from notebooks import DEFAULT_TAB_CONTENT
from utils.flashcards_db import create_deck
from utils.notes_db import (
    create_notebook, get_notes, create_note, delete_note
)

@st.dialog("Create Deck", width="small")
def create_deck_dialog() -> None:
    """
    Modal dialog for creating a new flashcard deck.
    Prompts the user for a deck name and handles creation or cancellation.
    """
    # Prompt user for the new deck name
    st.write("Enter the name for your new deck:")
    new_deck_name = st.text_input("Deck Name")

    # Layout two buttons side-by-side: Create and Cancel
    col_create, col_cancel = st.columns(2)
    with col_create:
        if st.button("Create", key="create_deck_btn"):
            # Ensure the name is not empty
            if new_deck_name.strip():
                create_deck(new_deck_name.strip()) # Insert new deck into DB
                st.rerun() # Close dialog and refresh main view
            else:
                st.error("Name cannot be empty.")  # Validate input
    with col_cancel:
        if st.button("Cancel", key="cancel_create_deck_btn"):
            st.rerun() # Close dialog without changes

@st.dialog("Create Notebook", width="small")
def create_notebook_dialog() -> None:
    """
    Modal dialog for creating a new notebook.
    Prompts the user for a notebook name and handles creation or cancellation.
    """
    # Prompt user for the new notebook name
    st.write("Enter the name for your new notebook:")
    new_notebook_name = st.text_input("Notebook Name")

    # Two-column layout for Create/Cancel actions
    col_create, col_cancel = st.columns(2)
    with col_create:
        if st.button("Create", key="create_notebook_btn"):
            if new_notebook_name.strip():
                create_notebook(new_notebook_name.strip()) # Insert new notebook into DB
                st.rerun() # Close dialog and refresh
            else:
                st.error("Name cannot be empty.")  # Validate input
    with col_cancel:
        if st.button("Cancel", key="cancel_create_notebook_btn"):
            st.rerun() # Close dialog without changes

@st.dialog("Import Deck", width="small")
def import_deck_dialog() -> None:
    """
    Modal dialog to import a flashcard deck from a JSON file.
    Validates file structure and inserts decks and cards into the database.
    """
    # Prompt user to upload a JSON file
    st.write("Upload a .json file containing your Deck data:")
    imported_file = st.file_uploader(
        "Deck JSON file", type=["json"], key="import_deck_file"
    )

    col_import, col_cancel = st.columns(2)
    with col_import:
        if st.button("Import", key="import_deck_button"):
            if imported_file is not None:
                try:
                    # Load JSON data
                    data = json.load(imported_file)
                    imported_deck_name = data.get("name")
                    cards_list = data.get("cards", [])

                    if imported_deck_name:
                        # Perform DB inserts for deck and its cards
                        from utils.flashcards_db import c, conn
                        import sqlite3
                        try:
                            # Insert deck record
                            c.execute(
                                "INSERT INTO decks (name) VALUES (?)",
                                (imported_deck_name,)
                            )
                            conn.commit()
                            new_deck_id = c.lastrowid

                            # Insert each card entry
                            for card in cards_list:
                                front = card.get("front", "")
                                back = card.get("back", "")
                                c.execute(
                                    """
                                    INSERT INTO cards
                                        (deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (new_deck_id, front, back, None, 0, 0, 2.5, None)
                                )
                            conn.commit()
                            st.success(
                                f"Deck '{imported_deck_name}' imported successfully!"
                            )
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("A deck with that name already exists!")
                    else:
                        st.error("Invalid deck file format!")
                except Exception as e:
                    st.error(f"Error importing deck: {e}")
            else:
                st.error("Please select a .json deck file to import.")
    with col_cancel:
        if st.button("Cancel", key="cancel_import_deck_btn"):
            st.rerun() # Close dialog

@st.dialog("Import Notebook", width="small")
def import_notebook_dialog() -> None:
    """
    Modal dialog to import a notebook from a JSON file.
    Creates a notebook and its tabs (notes) in the database.
    """
    # Prompt user to upload a JSON file
    st.write("Upload a .json file containing your Notebook data:")
    imported_file = st.file_uploader(
        "Notebook JSON file", type=["json"], key="import_notebook_file"
    )

    col_import, col_cancel = st.columns(2)
    with col_import:
        if st.button("Import", key="import_notebook_button"):
            if imported_file is not None:
                try:
                    data = json.load(imported_file)
                    imported_nb_name = data.get("name")
                    notes_list = data.get("notes", [])

                    if imported_nb_name:
                        from utils.notes_db import c as notes_c, conn as notes_conn
                        import sqlite3
                        try:
                            # Insert notebook record
                            notes_c.execute(
                                "INSERT INTO notebooks (name) VALUES (?)",
                                (imported_nb_name,)
                            )
                            notes_conn.commit()
                            new_nb_id = notes_c.lastrowid

                            # Insert each note/tab
                            for note_item in notes_list:
                                tab_name = note_item.get("tab_name", "") or "Default"
                                content = note_item.get("content", "")
                                notes_c.execute(
                                    "INSERT INTO notes (notebook_id, tab_name, content)"
                                    " VALUES (?, ?, ?)",
                                    (new_nb_id, tab_name, content)
                                )
                            notes_conn.commit()
                            st.success(
                                f"Notebook '{imported_nb_name}' imported successfully!"
                            )
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("A notebook with that name already exists!")
                    else:
                        st.error("Invalid notebook file format!")
                except Exception as e:
                    st.error(f"Error importing notebook: {e}")
            else:
                st.error("Please select a .json notebook file to import.")
    with col_cancel:
        if st.button("Cancel", key="cancel_import_notebook_btn"):
            st.rerun() # Close dialog

@st.dialog("Delete Notebook Tab", width="small")
def delete_tab_dialog(notebook_id: int) -> None:
    """
    Modal dialog to delete a tab from a notebook.
    Ensures at least one default tab remains after deletion.
    """
    # Fetch existing tabs for the notebook
    notes = get_notes(notebook_id) # List of (id, tab_name, content)
    if not notes:
        st.error("No tabs to delete.")
        if st.button("OK", key="delete_tab_ok"):
            # Close dialog and reset state
            st.session_state.delete_tab_dialog_open = False
            st.rerun()
        return

    # Determine which tab is currently selected for deletion
    tab_names = [n[1] for n in notes]
    if (
        "tab_to_delete" not in st.session_state
        or st.session_state.tab_to_delete not in tab_names
    ):
        st.session_state.tab_to_delete = tab_names[0] # Default to first tab

    st.write("Select which tab to delete:")
    st.session_state.tab_to_delete = st.selectbox(
        "Tab to delete",
        options=tab_names,
        index=tab_names.index(st.session_state.tab_to_delete),
        key="tab_to_delete_selectbox"
    )

    # Confirm or cancel deletion
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Confirm Delete", key="confirm_delete_tab"):
            # Locate note_id for the selected tab
            note_id_to_delete = next(
                (nid for nid, name, _ in notes if name == st.session_state.tab_to_delete),
                None
            )
            if note_id_to_delete is None:
                st.error("Tab not found. Maybe it was already deleted.")
                st.session_state.delete_tab_dialog_open = False
                st.session_state.tab_to_delete = None
                st.rerun()

            # Ensure at least one tab remains by creating default if needed
            if len(notes) == 1:
                create_note(notebook_id, "Default", DEFAULT_TAB_CONTENT)

            # Delete the selected tab
            delete_note(note_id_to_delete)
            st.success(f"Deleted tab '{st.session_state.tab_to_delete}'.")

            # Reset dialog state and close
            st.session_state.delete_tab_dialog_open = False
            st.session_state.tab_to_delete = None
            st.rerun()
    with col_cancel:
        if st.button("Cancel", key="cancel_delete_tab"):
            # Close dialog without changes
            st.session_state.delete_tab_dialog_open = False
            st.session_state.tab_to_delete = None
            st.rerun()
