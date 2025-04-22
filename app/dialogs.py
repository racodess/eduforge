import json
import streamlit as st

from notebooks import DEFAULT_TAB_CONTENT
from utils.flashcards_db import create_deck
from utils.notes_db import create_notebook, get_notes, create_note, delete_note

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
