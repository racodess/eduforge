# 2_Study.py

import re
import json
from datetime import datetime
import streamlit as st

from utils.flashcards_db import (
    init_db as init_flashcards_db,
    update_db_schema,
    get_decks, create_deck, rename_deck, trash_deck, reset_deck, get_deck_stats,
    get_cards, get_card_by_id, delete_card, update_card, add_card
)
from utils.notes_db import (
    init_db as init_notes_db,
    get_notebooks, create_notebook, delete_notebook, rename_notebook,
    get_notes, create_note, update_note, rename_note, delete_note
)
from utils.flashcards_sm2 import update_sm2, project_interval, format_interval_short
from utils.flashcards_ui import render_card_visual, render_card_form
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
def render_decks_section() -> None:
    """
    Deck list is shown in an editable Streamlit data_editor.

    • Add a new deck:  simply add a row and type a name.
    • Rename a deck   :  edit the Deck cell and press ⏎.
    • Select a deck   :  tick the Select box, then use the buttons underneath.
    """
    import pandas as pd

    st.markdown("## Flashcard Decks")

    # -------- Build the dataframe shown in the editor --------
    decks_raw = get_decks()                 # [(id, name), …]
    if decks_raw:
        df_orig = pd.DataFrame(
            [
                {
                    "id": d_id,
                    "Select": False,
                    "Deck": d_name,
                    **get_deck_stats(d_id)   # ⇒ {"new":…, "learn":…, "due":…}
                }
                for d_id, d_name in decks_raw
            ]
        )
    else:
        # Empty template so the user can create the first deck
        df_orig = pd.DataFrame(
            columns=["id", "Select", "Deck", "new", "learn", "due"]
        )

    # Disable stats + id in the editor
    col_cfg = {
        "id": st.column_config.TextColumn(disabled=True),
        "new": st.column_config.NumberColumn("New", disabled=True),
        "learn": st.column_config.NumberColumn("Learn", disabled=True),
        "due": st.column_config.NumberColumn("Due", disabled=True),
        "Select": st.column_config.CheckboxColumn("Select")
    }

    edited_df = st.data_editor(
        df_orig,
        column_config=col_cfg,
        num_rows="dynamic",          # allows adding rows
        hide_index=True,
        use_container_width=True,
        key="decks_editor"
    )

    # -------- Persist data‑editor changes --------
    # 1) New rows  → create_deck
    new_rows = edited_df[edited_df["id"].isna() & edited_df["Deck"].notna()]

    created_any = False

    existing_names = {n.lower() for _, n in decks_raw}
    for _, row in new_rows.iterrows():
        new_name = row["Deck"].strip()
        if not new_name:
            continue
        if new_name.lower() in existing_names:
            st.error(f"Deck name '{new_name}' already exists.")
            continue
        create_deck(new_name)
        created_any = True
        existing_names.add(new_name.lower())        # keep set up‑to‑date

    # 2) Renamed rows → rename_deck
    renamed = (
        edited_df[edited_df["id"].notna()]
        .merge(df_orig[["id", "Deck"]], on="id", suffixes=("_new", "_old"))
    )
    for _, r in renamed.iterrows():
        old = r["Deck_old"].strip()
        new = r["Deck_new"].strip()
        if new == old:
            continue
        if new.lower() in existing_names:
            st.error(f"Deck name '{new}' already exists.")
            continue
        rename_deck(int(r["id"]), new)
        existing_names.discard(old.lower())
        existing_names.add(new.lower())

    if created_any: # refresh so stats columns appear
        st.rerun()

    # 3) Fetch the selection (use the first True tick if several)
    sel_rows = edited_df[edited_df["Select"].fillna(False)]
    sel_deck_id = int(sel_rows.iloc[0]["id"]) if not sel_rows.empty else None
    sel_deck_name = sel_rows.iloc[0]["Deck"] if not sel_rows.empty else None

    # -------- Action buttons --------
    btn_cols = st.columns(4)
    with btn_cols[0]:
        if st.button("Review", key="deck_review_btn", disabled=sel_deck_id is None):
            st.session_state.update(
                selected_deck_id=sel_deck_id,
                selected_deck_mode="review",
                review_card_id=None,
                review_show_answer=False,
                review_edit_mode=False,
            )
            st.rerun()

    with btn_cols[1]:
        if st.button("Browse", key="deck_browse_btn", disabled=sel_deck_id is None):
            st.session_state.selected_deck_id = sel_deck_id
            st.session_state.selected_deck_mode = "browse"
            st.rerun()

    with btn_cols[2]:
        if sel_deck_id is not None:          # a deck is selected → real download button
            cards_data = get_cards(sel_deck_id)
            deck_json = json.dumps(
                {
                    "name": sel_deck_name,
                    "cards": [{"front": c[1], "back": c[2]} for c in cards_data],
                },
                indent=2,
            )
            st.download_button(
                label="Export",                         # <- single, immediate‑download button
                data=deck_json,
                file_name=f"{sel_deck_name}.json",
                mime="application/json",
                key=f"download_deck_{sel_deck_id}",
            )
        else:                                # nothing selected → disabled placeholder
            st.button("Export", disabled=True, key="deck_export_btn_disabled")

    with btn_cols[3]:
        if st.button("Delete", key="deck_delete_btn", disabled=sel_deck_id is None):
            st.session_state.deck_pending_delete = sel_deck_id
            st.rerun()

    # -------- Deletion confirmation --------
    pending_deck_id = st.session_state.get("deck_pending_delete")
    if pending_deck_id is not None and pending_deck_id == sel_deck_id:
        st.info(f"Delete deck **{sel_deck_name}**?")
        c_yes, c_no = st.columns(2)
        if c_yes.button("Yes – delete it", key="deck_delete_btn_yes"):
            trash_deck(sel_deck_id)
            st.session_state.deck_pending_delete = None
            st.success("Deleted ✅")
            st.rerun()
        if c_no.button("No – keep it", key="deck_delete_btn_no"):
            st.session_state.deck_pending_delete = None
            st.rerun()

    # -------- Import Deck button (create is now via the table) --------
    if st.button("Import Deck"):
        import_deck_dialog()


# --------------------------------------------------------------
#                   Notebooks Section
# --------------------------------------------------------------
def render_notebooks_section() -> None:
    """
    Notebook list in a Streamlit data_editor.
    """
    import pandas as pd

    st.markdown("## Notebooks")

    notebooks_raw = get_notebooks()             # [(id, name), …]
    if notebooks_raw:
        df_orig = pd.DataFrame(
            [
                {
                    "id": nb_id,
                    "Select": False,
                    "Notebook": nb_name,
                    "new": 0,
                    "learn": 0,
                    "due": 0,
                }
                for nb_id, nb_name in notebooks_raw
            ]
        )
    else:
        df_orig = pd.DataFrame(
            columns=["id", "Select", "Notebook", "new", "learn", "due"]
        )

    col_cfg = {
        "id": st.column_config.TextColumn(disabled=True),
        "new": st.column_config.NumberColumn("New", disabled=True),
        "learn": st.column_config.NumberColumn("Learn", disabled=True),
        "due": st.column_config.NumberColumn("Due", disabled=True),
        "Select": st.column_config.CheckboxColumn("Select"),
    }

    edited_df = st.data_editor(
        df_orig,
        column_config=col_cfg,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="notebooks_editor",
    )

    # Persist adds / renames
    new_rows = edited_df[edited_df["id"].isna() & edited_df["Notebook"].notna()]

    created_any = False

    existing_names = {n.lower() for _, n in notebooks_raw}
    for _, row in new_rows.iterrows():
        new_name = row["Notebook"].strip()
        if not new_name:
            continue
        if new_name.lower() in existing_names:
            st.error(f"Notebook name '{new_name}' already exists.")
            continue
        create_notebook(new_name)
        created_any = True
        existing_names.add(new_name.lower())

    renamed = (
        edited_df[edited_df["id"].notna()]
        .merge(df_orig[["id", "Notebook"]], on="id", suffixes=("_new", "_old"))
    )
    for _, r in renamed.iterrows():
        old = r["Notebook_old"].strip()
        new = r["Notebook_new"].strip()
        if new == old:
            continue
        if new.lower() in existing_names:
            st.error(f"Notebook name '{new}' already exists.")
            continue
        rename_notebook(int(r["id"]), new)
        existing_names.discard(old.lower())
        existing_names.add(new.lower())

    if created_any:                           # refresh the table
        st.rerun()

    sel_rows = edited_df[edited_df["Select"].fillna(False)]
    sel_nb_id = int(sel_rows.iloc[0]["id"]) if not sel_rows.empty else None
    sel_nb_name = sel_rows.iloc[0]["Notebook"] if not sel_rows.empty else None

    btn_cols = st.columns(4)
    with btn_cols[0]:
        if st.button("Review", key="nb_review_btn", disabled=True):
            st.warning("Notebook‑review mode not implemented yet.")

    with btn_cols[1]:
        if st.button("Browse", key="nb_browse_btn", disabled=sel_nb_id is None):
            st.session_state.selected_notebook_id = sel_nb_id
            st.rerun()

    with btn_cols[2]:
        if sel_nb_id is not None:
            notes_data = get_notes(sel_nb_id)
            nb_json = json.dumps(
                {
                    "name": sel_nb_name,
                    "notes": [
                        {"tab_name": n[1], "content": n[2]} for n in notes_data
                    ],
                },
                indent=2,
            )
            st.download_button(
                label="Export",
                data=nb_json,
                file_name=f"{sel_nb_name}.json",
                mime="application/json",
                key=f"download_nb_{sel_nb_id}",
            )
        else:
            st.button("Export", disabled=True, key="nb_export_btn_disabled")

    with btn_cols[3]:
        if st.button("Delete", key="nb_delete_btn", disabled=sel_nb_id is None):
            st.session_state.notebook_pending_delete = sel_nb_id
            st.rerun()

    pending_nb_id = st.session_state.get("notebook_pending_delete")
    if pending_nb_id is not None and pending_nb_id == sel_nb_id:
        st.info(f"Delete notebook **{sel_nb_name}**?")
        c_yes, c_no = st.columns(2)
        if c_yes.button("Yes – delete it", key="nb_delete_btn_yes"):
            delete_notebook(sel_nb_id)
            st.session_state.notebook_pending_delete = None
            st.success("Deleted ✅")
            st.rerun()
        if c_no.button("No – keep it", key="nb_delete_btn_no"):
            st.session_state.notebook_pending_delete = None
            st.rerun()

    if st.button("Import Notebook"):
        import_notebook_dialog()

def _clear_new_row(df_key: str, row_idx):
    """
    Blank the Deck field and uncheck Select for the row at row_idx
    in st.session_state[df_key] (where df_key is 'decks_editor' or 'notebooks_editor').
    """
    ss_df = st.session_state[df_key]
    ss_df.at[row_idx, "Deck"] = ""
    if "Select" in ss_df.columns:
        ss_df.at[row_idx, "Select"] = False

# --------------------------------------------------------------
#         Notebook Detail (Browse Selected Notebook)
# --------------------------------------------------------------

def render_notebook_detail(notebook_id: int):
    """Shows a single notebook page with Back, Add, Delete, and tab‑by‑tab content or editing, now with GraphViz preview."""
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
    tab_labels = [n[1] for n in notes]
    tab_objects = st.tabs(tab_labels)

    for i, (note_id, tab_name, content) in enumerate(notes):
        with tab_objects[i]:
            is_editing = (st.session_state.editing_tab_id == note_id)

            if not is_editing:
                # -------------------- VIEW MODE -------------------------
                code = _extract_graphviz(content)
                if code:
                    st.graphviz_chart(code, use_container_width=True)
                else:
                    st.markdown(content if content else "*[Empty note]*", unsafe_allow_html=True)
                st.write("")
                if st.button("Edit", key=f"edit_tab_btn_{note_id}"):
                    st.session_state.editing_tab_id = note_id
                    st.rerun()
            else:
                # -------------------- EDIT MODE -------------------------
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
        st.markdown("## Generate Study Material")

        # pick study‑material type
        study_types = st.multiselect(
            "Select study material type(s)",
            options=[
                "Flashcards",
                "Notebooks", # traditional markdown notes
                "Mind Maps",
            ],
            key="gen_study_types",
        )

        # dynamically show target multiselect
        # Flashcard decks selection
        if "Flashcards" in study_types:
            decks = get_decks()
            if not decks:
                st.error("No decks available. Please create a deck first.")
                return
            deck_opts = {dname: did for did, dname in decks}
            st.session_state.gen_target_deck_ids = st.multiselect(
                "Target deck(s)",
                options=list(deck_opts.keys()),
                default=list(deck_opts.keys())[:1],
                key="gen_deck_select",
            )
            st.session_state.gen_target_deck_ids = [
                deck_opts[name] for name in st.session_state.gen_target_deck_ids
            ]
        else:
            st.session_state.pop("gen_target_deck_ids", None)

        # ALL notebook‑bound study types (notes *and* graphs)
        needs_notebooks = any(
            t in study_types for t in ["Notebooks", "Mind Maps"]
        )
        if needs_notebooks:
            notebooks = get_notebooks()
            if not notebooks:
                st.error("No notebooks available. Please create one first.")
                return
            nb_opts = {nname: nid for nid, nname in notebooks}
            st.session_state.gen_target_nb_ids = st.multiselect(
                "Target notebook(s)",
                options=list(nb_opts.keys()),
                default=list(nb_opts.keys())[:1],
                key="gen_nb_select",
            )
            st.session_state.gen_target_nb_ids = [
                nb_opts[name] for name in st.session_state.gen_target_nb_ids
            ]
        else:
            st.session_state.pop("gen_target_nb_ids", None)

        # shared content inputs
        file_helper = FileHelper()

        uploaded_file = st.file_uploader(
            label="Upload a .txt, .pdf, or image file",
            type=["txt", "pdf", "png", "jpg", "jpeg", "gif"],
            key="gen_file_uploader",
        )

        page_range = None
        if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
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

        # GENERATE button
        if st.button("Generate", key="gen_button", use_container_width=True):
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
                return
            
            # run the pipelines
            if "Flashcards" in study_types:
                flashcard_models = file_helper.generate_flashcards_pipeline(final_text)
                st.session_state.generated_cards = [
                    fc
                    for m in flashcard_models
                    if hasattr(m, "flashcards")
                    for fc in m.flashcards
                ]
            else:
                st.session_state.pop("generated_cards", None)

            if "Notebooks" in study_types:
                note_models = file_helper.generate_notes_pipeline(final_text)
                st.session_state.generated_notes = [
                    nt for m in note_models if hasattr(m, "notes") for nt in m.notes
                ]
            else:
                st.session_state.pop("generated_notes", None)

            # Mind Maps
            graph_models: List[dict] = []
            if "Mind Maps" in study_types:
                graph_models.extend(
                    [
                        {
                            "item": g,
                            "type": "mind_map",
                        }
                        for g in file_helper.generate_graphs_pipeline(final_text, "mind_map")
                    ]
                )

            if graph_models:
                st.session_state.generated_graphs = graph_models
            else:
                st.session_state.pop("generated_graphs", None)

            if not (
                st.session_state.get("generated_cards")
                or st.session_state.get("generated_notes")
                or st.session_state.get("generated_graphs")
            ):
                st.info("Nothing was generated.")
                return

            # save previous UI context & open dedicated viewer
            if not st.session_state.generated_view:
                st.session_state.pre_gen_state = {
                    "selected_deck_id": st.session_state.get("selected_deck_id"),
                    "selected_deck_mode": st.session_state.get("selected_deck_mode"),
                    "selected_notebook_id": st.session_state.get("selected_notebook_id"),
                }
                st.session_state.generated_view = True
                st.rerun()

# --------------------------------------------------------------
#   Dedicated Window for Viewing Generated Items (cards & notes)
# --------------------------------------------------------------
def render_generated_items_window():
    top_cols = st.columns([2, 8])
    if top_cols[0].button("Back", key="gen_back_btn", use_container_width=True):
        if st.session_state.pre_gen_state:
            for k, v in st.session_state.pre_gen_state.items():
                st.session_state[k] = v
        st.session_state.generated_view = False
        st.session_state.pre_gen_state = None
        st.rerun()

    top_cols[1].markdown("<h2 style='text-align:left;'>Generated Items</h2>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # ----------  A.  FLASHCARDS  ----------
    if st.session_state.get("generated_cards"):
        st.markdown("<h2 style='text-align:center;'>Flashcards</h2>", unsafe_allow_html=True)
        _render_generated_flashcards_section()

    st.text("")
    st.text("")
    st.text("")
    st.text("")

    # ----------  B.  NOTES  ----------
    if st.session_state.get("generated_notes"):
        st.markdown("<h2 style='text-align:center;'>Notes</h2>", unsafe_allow_html=True)
        _render_generated_notes_section()

    if not (st.session_state.get("generated_cards") or st.session_state.get("generated_notes")):
        st.info("No generated items to display.")

# ================= helper: flashcards =========================

def render_generated_items_window():
    top_cols = st.columns([2, 8])
    if top_cols[0].button("Back", key="gen_back_btn", use_container_width=True):
        if st.session_state.pre_gen_state:
            for k, v in st.session_state.pre_gen_state.items():
                st.session_state[k] = v
        st.session_state.generated_view = False
        st.session_state.pre_gen_state = None
        st.rerun()

    top_cols[1].markdown("<h2 style='text-align:left;'>Generated Items</h2>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # FLASHCARDS
    if st.session_state.get("generated_cards"):
        st.markdown("<h2 style='text-align:center;'>Flashcards</h2>", unsafe_allow_html=True)
        _render_generated_flashcards_section()

    st.text("")
    st.text("")
    st.text("")
    st.text("")

    # NOTES
    if st.session_state.get("generated_notes"):
        st.markdown("<h2 style='text-align:center;'>Notes</h2>", unsafe_allow_html=True)
        _render_generated_notes_section()

    st.text("")
    st.text("")
    st.text("")
    st.text("")

    # GRAPHS
    if st.session_state.get("generated_graphs"):
        st.markdown("<h2 style='text-align:center;'>Graphs</h2>", unsafe_allow_html=True)
        _render_generated_graphs_section()

    if not (
        st.session_state.get("generated_cards")
        or st.session_state.get("generated_notes")
        or st.session_state.get("generated_graphs")
    ):
        st.info("No generated items to display.")

# ================= helper: flashcards =========================
def _render_generated_flashcards_section():
    target_ids = st.session_state.get("gen_target_deck_ids", [])
    if not target_ids:
        st.error("Target deck(s) not found – please re‑run generation.")
        return

    col_a, col_b = st.columns(2)
    if col_a.button("Add All Flashcards", use_container_width=True):
        for deck_id in target_ids:
            for card in st.session_state.generated_cards:
                add_card(deck_id, card.front, card.back, extra_fields=None)
        st.success("Imported all flashcards!")
        st.session_state.generated_cards = []
        st.rerun()
    if col_b.button("Delete All Flashcards", use_container_width=True):
        st.session_state.generated_cards = []
        st.rerun()

    for i, card in enumerate(st.session_state.generated_cards):
        _render_flashcard_container(card, i)

def _render_flashcard_container(card, idx):
    ccols = st.columns([1, 6, 1])
    with ccols[1]:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: left; font-size: 16px;"><strong>Flashcard {idx+1}</strong></div>',
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

            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_fc_{idx}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                for deck_id in st.session_state.get("gen_target_deck_ids", []):
                    add_card(deck_id, card.front, card.back, extra_fields=None)
                st.session_state.generated_cards.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_fc_{idx}", type="tertiary", icon=":material/cached:", use_container_width=True):
                new_card = FileHelper().regenerate_flashcard(card)
                st.session_state.generated_cards[idx] = new_card
                st.rerun()
            if b3.button("", key=f"del_fc_{idx}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_cards.pop(idx)
                st.rerun()

# ================= helper: notes ==============================
def _render_generated_notes_section():
    nb_ids = st.session_state.get("gen_target_nb_ids", [])
    if not nb_ids:
        st.error("Target notebook(s) not found – please re‑run generation.")
        return

    col_a, col_b = st.columns(2)
    if col_a.button("Add All Notes", use_container_width=True):
        for nb_id in nb_ids:
            for note in st.session_state.generated_notes:
                create_note(nb_id, note.title, note.content)
        st.success("Imported all notes!")
        st.session_state.generated_notes = []
        st.rerun()
    if col_b.button("Delete All Notes", use_container_width=True):
        st.session_state.generated_notes = []
        st.rerun()

    for i, note in enumerate(st.session_state.generated_notes):
        _render_note_container(note, i)

def _render_note_container(note, idx):
    ccols = st.columns([1, 6, 1])
    with ccols[1]:
        with st.container(border=True):
            st.markdown(
                f"<div style='text-align: left; font-size: 16px;'><strong>Note {idx+1}</strong></div>",
                unsafe_allow_html=True,
            )
            st.text("")
            st.markdown(
                f"<div style='text-align: center;'><h3><u>{note.title}</u></h3></div>",
                unsafe_allow_html=True,
            )
            code = _extract_graphviz(note.content)
            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.markdown(note.content, unsafe_allow_html=True)

            st.divider()
            b1, b2, b3 = st.columns(3)
            # buttons unchanged except regen now works with note regeneration prompt
            if b1.button("", key=f"add_nt_{idx}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                for nb_id in st.session_state.get("gen_target_nb_ids", []):
                    create_note(nb_id, note.title, note.content)
                st.session_state.generated_notes.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_nt_{idx}", type="tertiary", icon=":material/cached:", use_container_width=True):
                new_note = FileHelper().regenerate_note(note)
                st.session_state.generated_notes[idx] = new_note
                st.rerun()
            if b3.button("", key=f"del_nt_{idx}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_notes.pop(idx)
                st.rerun()

# ================= helper: graphs ===========================================

def _extract_graphviz(content: str) -> str | None:
    """Return DOT if content contains a graphviz code block **or** looks like raw DOT."""
    m = re.search(r"```(?:graphviz|dot)\s+([\s\S]+?)```", content, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # fall‑back: raw DOT if it begins with graph keyword
    stripped = content.strip()
    if re.match(r"^(strict\s+)?(di)?graph\b", stripped, re.IGNORECASE):
        return stripped
    return None

def _render_generated_graphs_section():
    nb_ids = st.session_state.get("gen_target_nb_ids", [])
    if not nb_ids:
        st.error("Target notebook(s) not found – please re‑run generation.")
        return

    col_a, col_b = st.columns(2)
    if col_a.button("Add All Graphs", use_container_width=True):
        for nb_id in nb_ids:
            for gdict in st.session_state.generated_graphs:
                create_note(nb_id, gdict["item"].title, gdict["item"].content)
        st.success("Imported all graphs!")
        st.session_state.generated_graphs = []
        st.rerun()
    if col_b.button("Delete All Graphs", use_container_width=True):
        st.session_state.generated_graphs = []
        st.rerun()

    for i, gdict in enumerate(st.session_state.generated_graphs):
        _render_graph_container(gdict, i)

def _render_graph_container(gdict: dict, idx: int):
    graph_note = gdict["item"]
    gtype = gdict["type"]
    code = _extract_graphviz(graph_note.content)
    ccols = st.columns([1, 6, 1])
    with ccols[1]:
        with st.container(border=True):
            st.markdown(
                f"<div style='text-align: left; font-size: 16px;'><strong>Graph {idx+1} ({gtype.replace('_', ' ').title()})</strong></div>",
                unsafe_allow_html=True,
            )
            st.text("")
            st.markdown(
                f"<div style='text-align: center;'><h3><u>{graph_note.title}</u></h3></div>",
                unsafe_allow_html=True,
            )

            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.error("GraphViz block not detected – displaying raw content:")
                st.markdown(graph_note.content, unsafe_allow_html=True)

            st.divider()
            b1, b2, b3 = st.columns(3)
            if b1.button("", key=f"add_gr_{idx}", type="tertiary", icon=":material/add_circle:", use_container_width=True):
                for nb_id in st.session_state.get("gen_target_nb_ids", []):
                    create_note(nb_id, graph_note.title, graph_note.content)
                st.session_state.generated_graphs.pop(idx)
                st.rerun()
            if b2.button("", key=f"regen_gr_{idx}", type="tertiary", icon=":material/cached:", use_container_width=True):
                new_graph = FileHelper().regenerate_graph(graph_note, graph_type=gtype)
                st.session_state.generated_graphs[idx]["item"] = new_graph
                st.rerun()
            if b3.button("", key=f"del_gr_{idx}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                st.session_state.generated_graphs.pop(idx)
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
        render_generated_items_window()
        return

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
