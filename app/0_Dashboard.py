# 2_Study.py

import re
import json
import os
from datetime import datetime
import streamlit as st
from openai import OpenAI

from utils.flashcards_db import (
    init_db as init_flashcards_db,
    update_db_schema,
    get_decks, create_deck, rename_deck, trash_deck, reset_deck, get_deck_stats,
    get_cards, get_card_by_id, delete_card, update_card, add_card
)
from utils.notes_db import (
    init_db as init_notes_db,
    get_notebooks, create_notebook, delete_notebook, rename_notebook,
    get_notes, create_note, update_note, rename_note, delete_note,
    get_notebook_stats, get_note_by_id, get_notes_full
)
from utils.flashcards_sm2 import update_sm2, project_interval, format_interval_short
from utils.notes_sm2 import update_sm2 as update_sm2_note, project_interval as project_interval_note
from utils.flashcards_ui import render_card_visual, render_card_form
from utils.file_helper import FileHelper
from utils.quiz_section import render_quiz_section

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

    st.markdown("<h2 style='text-align:center;'>Flashcard Decks</h2>", unsafe_allow_html=True)

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
    with st.container():
        col_review, col_browse, col_import, col_export, col_delete = st.columns(5)

        # ── Review ────────────────────────────────
        if col_review.button(
            "", key="deck_review_btn",
            type="tertiary", icon=":material/play_arrow:",
            use_container_width=True,
            disabled=sel_deck_id is None
        ):
            st.session_state.update(
                selected_deck_id   = sel_deck_id,
                selected_deck_mode = "review",
                review_card_id     = None,
                review_show_answer = False,
                review_edit_mode   = False,
            )
            st.rerun()

        # ── Browse ────────────────────────────────
        if col_browse.button(
            "", key="deck_browse_btn",
            type="tertiary", icon=":material/visibility:",
            use_container_width=True,
            disabled=sel_deck_id is None
        ):
            st.session_state.selected_deck_id   = sel_deck_id
            st.session_state.selected_deck_mode = "browse"
            st.rerun()

        # ── Import ────────────────────────────────
        if col_import.button(
            "", key="deck_import_btn",
            type="tertiary", icon=":material/upload:",
            use_container_width=True
        ):
            import_deck_dialog()

        # ── Export ────────────────────────────────
        if sel_deck_id is not None:
            deck_json = json.dumps(
                {
                    "name":  sel_deck_name,
                    "cards": [
                        {"front": c[1], "back": c[2]} for c in get_cards(sel_deck_id)
                    ],
                },
                indent=2,
            )
            col_export.download_button(
                label="",
                data=deck_json,
                file_name=f"{sel_deck_name}.json",
                mime="application/json",
                key=f"download_deck_{sel_deck_id}",
                type="tertiary",
                icon=":material/download:",
                use_container_width=True
            )
        else:
            col_export.button(
                "", disabled=True, key="deck_export_btn_disabled",
                type="tertiary", icon=":material/download:",
                use_container_width=True
            )

        # ── Delete ────────────────────────────────
        if col_delete.button(
            "", key="deck_delete_btn",
            type="tertiary", icon=":material/delete:",
            use_container_width=True,
            disabled=sel_deck_id is None
        ):
            st.session_state.deck_pending_delete = sel_deck_id
            st.rerun()

    # -------- Deletion confirmation --------
    pending_deck_id = st.session_state.get("deck_pending_delete")
    if pending_deck_id is not None:
        # look up the deck’s name so we can still show it even if the row isn’t selected
        pending_name = next(
            (name for d_id, name in decks_raw if d_id == pending_deck_id),
            "this deck"
        )
        st.info(f"Delete deck **{pending_name}**?")
        c_yes, c_no = st.columns(2)

        if c_yes.button("Yes – delete it", key="deck_delete_btn_yes", use_container_width=True):
            trash_deck(pending_deck_id)
            st.session_state.deck_pending_delete = None
            st.success("Deleted ✅")
            st.rerun()

        if c_no.button("No – keep it", key="deck_delete_btn_no", use_container_width=True):
            st.session_state.deck_pending_delete = None
            st.rerun()

# --------------------------------------------------------------
#                   Notebooks Section
# --------------------------------------------------------------
def render_notebooks_section() -> None:
    """
    Notebook list in a Streamlit data_editor.
    """
    import pandas as pd

    st.markdown("<h2 style='text-align:center;'>Notebooks</h2>", unsafe_allow_html=True)

    notebooks_raw = get_notebooks()            # [(id, name), …]
    if notebooks_raw:
        df_orig = pd.DataFrame(
            [
                {
                    "id": nb_id,
                    "Select": False,
                    "Notebook": nb_name,
                    **get_notebook_stats(nb_id)              # ← live New / Due figures
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

    # -------- Action buttons --------
    with st.container():
        btn_cols = st.columns(5)

        # Review
        if btn_cols[0].button("", key="nb_review_btn",
                            type="tertiary", icon=":material/play_arrow:",
                            use_container_width=True,
                            disabled=sel_nb_id is None):
            st.session_state.update(
                selected_notebook_id = sel_nb_id,
                selected_notebook_mode = "review",
                review_note_id = None,
                review_note_edit_mode = False,
            ); st.rerun()

        # Browse
        if btn_cols[1].button("", key="nb_browse_btn",
                            type="tertiary", icon=":material/visibility:",
                            use_container_width=True,
                            disabled=sel_nb_id is None):
            st.session_state.selected_notebook_id = sel_nb_id; st.rerun()

        # Import
        if btn_cols[2].button("", key="nb_import_btn",
                            type="tertiary", icon=":material/upload:",
                            use_container_width=True):
            import_notebook_dialog()

        # Export
        if sel_nb_id is not None:
            nb_json = json.dumps(
                {
                    "name": sel_nb_name,
                    "notes": [{"tab_name": n[1], "content": n[2]} for n in get_notes(sel_nb_id)],
                },
                indent=2,
            )
            btn_cols[3].download_button(
                label="",
                data=nb_json,
                file_name=f"{sel_nb_name}.json",
                mime="application/json",
                key=f"download_nb_{sel_nb_id}",
                type="tertiary",
                icon=":material/download:",
                use_container_width=True,
            )
        else:
            btn_cols[3].button("", disabled=True, key="nb_export_btn_disabled",
                            type="tertiary", icon=":material/download:",
                            use_container_width=True)

        # Delete
        if btn_cols[4].button("", key="nb_delete_btn",
                            type="tertiary", icon=":material/delete:",
                            use_container_width=True,
                            disabled=sel_nb_id is None):
            st.session_state.notebook_pending_delete = sel_nb_id; st.rerun()


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

def render_notebook_detail(nb_id: int):
    import pandas as pd
    from utils.notes_db import c as notes_c, conn as notes_conn

    # ---------- load ----------
    notes_c.execute("SELECT name FROM notebooks WHERE id = ?", (nb_id,))
    row = notes_c.fetchone()
    if not row:
        st.error("Notebook missing."); st.session_state.selected_notebook_id = None; return
    nb_name = row[0]

    st.markdown(f"<h2 style='text-align:center;'>{nb_name}</h2>", unsafe_allow_html=True)

    # ---------- Back / Reset Stats ----------
    hcols = st.columns(2)
    if hcols[0].button("Back", use_container_width=True):
        st.session_state.selected_notebook_id = None; st.rerun()
    if hcols[1].button("Reset Stats", use_container_width=True):
        _reset_notebook_stats(nb_id, notes_c, notes_conn)
        st.success("All SM‑2 data reset."); st.rerun()

    # ---------- notes list ----------
    notes = get_notes(nb_id)
    if not notes:
        create_note(nb_id, "Default", DEFAULT_TAB_CONTENT); st.rerun()

    df_orig = pd.DataFrame(
        [{"id": nid, "Select": False, "Tab": t} for nid, t, _ in notes]
    )
    edited = st.data_editor(
        df_orig,
        column_config={
            "id":     st.column_config.TextColumn(disabled=True),
            "Select": st.column_config.CheckboxColumn("Select"),
            "Tab":    st.column_config.TextColumn("Tab Name"),
        },
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        key=f"nb_editor_{nb_id}",
    )

    # inline rename
    delta = (edited.merge(df_orig, on="id", suffixes=("_new", "_old"))
                    .query("Tab_new != Tab_old"))
    for _, r in delta.iterrows():
        rename_note(int(r["id"]), r["Tab_new"].strip())

    # ---------- existing edit‑mode? ----------
    if st.session_state.get("editing_tab_id"):
        _render_tab_edit_form(nb_id)  # defined just below
        return

    # ---------- selection ----------
    sel = edited[edited["Select"].fillna(False)]
    sel_id = int(sel.iloc[0]["id"]) if not sel.empty else None
    selected_note = next((n for n in notes if n[0] == sel_id), None)

    # ---------- button bar (Add‑Tab left of Edit) ----------
    bcols = st.columns(4)
    if bcols[0].button("Add Tab", use_container_width=True):
        new_id = create_note(nb_id, "New Tab", "")
        st.session_state.editing_tab_id = new_id; st.rerun()

    if bcols[1].button("Edit", disabled=sel_id is None, use_container_width=True):
        st.session_state.editing_tab_id = sel_id; st.rerun()

    if bcols[2].button("Stats", disabled=sel_id is None, use_container_width=True):
        cur = st.session_state.get("selected_stats_note_id")
        st.session_state.selected_stats_note_id = None if cur == sel_id else sel_id
        st.rerun()

    if bcols[3].button("Delete", disabled=sel_id is None, use_container_width=True):
        delete_note(sel_id); st.success("Deleted."); st.rerun()

    # ---------- preview / stats ----------
    if selected_note:
        _, tab, body = selected_note
        with st.container(border=True):
            st.markdown(f"### {tab}", unsafe_allow_html=True)
            code = _extract_graphviz(body)
            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.markdown(body or "*[Empty]*", unsafe_allow_html=True)

            if st.session_state.get("selected_stats_note_id") == sel_id:
                _, _, _, _, nr, interval, rep, ef = get_note_by_id(sel_id)
                nr_str = nr.split("T")[0] if nr else "—"
                st.markdown(
                    f"<p style='text-align:center;'><em>"
                    f"Next {nr_str} &nbsp;|&nbsp; {interval} d &nbsp;|&nbsp; "
                    f"Rep {rep} &nbsp;|&nbsp; EF {ef:.2f}</em></p>",
                    unsafe_allow_html=True
                )
    else:
        st.markdown("<p style='text-align:center;'>Select a tab to preview.</p>",
                    unsafe_allow_html=True)


# ---------- inline tab‑edit helper ----------
def _render_tab_edit_form(nb_id: int):
    note_id = st.session_state.editing_tab_id
    note = get_note_by_id(note_id)
    if not note:
        st.error("Note not found."); st.session_state.editing_tab_id = None; return
    _, _, tab_name, content, *_ = note

    with st.container(border=True):
        with st.form(f"edit_tab_{note_id}", clear_on_submit=False):
            new_tab = st.text_input("Tab Name", value=tab_name)
            new_body = st.text_area("Content", value=content, height=300)
            c1, c2 = st.columns(2)
            if c1.form_submit_button("Save", use_container_width=True):
                rename_note(note_id, new_tab)
                update_note(note_id, new_body)
                st.session_state.editing_tab_id = None
                st.success("Saved!"); st.rerun()
            if c2.form_submit_button("Cancel", use_container_width=True):
                st.session_state.editing_tab_id = None; st.rerun()

        
def _reset_notebook_stats(nb_id: int, notes_c, notes_conn):
    notes_c.execute(
        """
        UPDATE notes
           SET next_review = NULL,
               interval     = 0,
               repetition   = 0,
               ef           = 2.5
         WHERE notebook_id = ?
        """,
        (nb_id,)
    )
    notes_conn.commit()

def render_notebook_review(nb_id: int):
    # --- Header & back ----
    top = st.columns([2,8])
    if top[0].button("Back", key="nb_rev_back", use_container_width=True):
        st.session_state.update(
            selected_notebook_id=None,
            selected_notebook_mode=None,
            review_note_id=None,
            review_note_edit_mode=False,
        )
        st.rerun()

    # notebook title & counters
    stats = get_notebook_stats(nb_id)
    name = [n for n in get_notebooks() if n[0]==nb_id][0][1]
    top[1].markdown(
        f"<h2 style='text-align:left;'>{name} — Review</h2>"
        f"<p>New: {stats['new']} | Due: {stats['due']}</p>",
        unsafe_allow_html=True)

    if stats["new"]==0 and stats["due"]==0:
        st.success("🎉  Nothing to review right now!")
        return

    notes = get_notes_full(nb_id)
    if not notes:
        st.info("Notebook is empty.")
        return

    # pick current note
    if st.session_state.review_note_id is None:
        st.session_state.review_note_id = notes[0][0]
    note = get_note_by_id(st.session_state.review_note_id)
    if not note:
        st.error("Note not found."); return

    note_id, _, tab_name, content, nr, interval, repetition, ef = note
    st.markdown(f"### {tab_name}")

    # -------- EDIT MODE ----------------------------
    if st.session_state.review_note_edit_mode:
        with st.form("edit_note_review", clear_on_submit=False):
            new_tab = st.text_input("Tab Name", value=tab_name)
            new_body= st.text_area("Content", value=content, height=300)
            e1,e2 = st.columns(2)
            with e2:
                if st.form_submit_button("Save"):
                    rename_note(note_id, new_tab)
                    update_note(note_id, new_body)
                    st.success("Updated!")
                    st.session_state.review_note_edit_mode=False
                    st.rerun()
            with e1:
                if st.form_submit_button("Cancel"):
                    st.session_state.review_note_edit_mode=False
                    st.rerun()
        return  # stop, the form already rendered
    # -------- VIEW MODE ----------------------------
    code = _extract_graphviz(content)
    if code:
        st.graphviz_chart(code, use_container_width=True)
    else:
        st.markdown(content if content.strip() else "*[Empty note]*",
                    unsafe_allow_html=True)

    st.divider()

    # ---- grading projections row ---------------
    proj_a = format_interval_short(project_interval_note(note, 0))
    proj_h = format_interval_short(project_interval_note(note, 3))
    proj_g = format_interval_short(project_interval_note(note, 4))
    proj_e = format_interval_short(project_interval_note(note, 5))

    ph = st.columns([2,1,1,1,1])
    ph[1].markdown(proj_a); ph[2].markdown(proj_h)
    ph[3].markdown(proj_g); ph[4].markdown(proj_e)

    pb = st.columns([2,1,1,1,1])
    if pb[0].button("Edit", key="nb_rev_edit"):
        st.session_state.review_note_edit_mode=True; st.rerun()
    if pb[1].button("Again"):
        update_sm2_note(note_id, 0); _next_note(nb_id)
    if pb[2].button("Hard"):
        update_sm2_note(note_id, 3); _next_note(nb_id)
    if pb[3].button("Good"):
        update_sm2_note(note_id, 4); _next_note(nb_id)
    if pb[4].button("Easy"):
        update_sm2_note(note_id, 5); _next_note(nb_id)

def _next_note(nb_id):
    from utils.notes_db import get_notes_full
    notes = get_notes_full(nb_id)
    if not notes: return
    ids = [n[0] for n in notes]
    cur = st.session_state.review_note_id
    idx = ids.index(cur) if cur in ids else -1
    st.session_state.review_note_id = ids[(idx+1)%len(ids)]
    st.session_state.review_note_edit_mode=False
    st.rerun()

# --------------------------------------------------------------
#         Deck Detail (Browse Selected Deck) & Review
# --------------------------------------------------------------
# --------------------------------------------------------------
#            Deck Detail (Browse Selected Deck)  FINAL
# --------------------------------------------------------------
def render_deck_detail(deck_id: int):
    import pandas as pd
    from utils.flashcards_db import c

    # ---------- load deck ----------
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("Deck not found.")
        st.session_state.update(selected_deck_id=None, selected_deck_mode=None)
        return
    deck_name = row[0]

    # ---------- header ----------
    st.markdown(f"<h2 style='text-align:center;'>{deck_name}</h2>", unsafe_allow_html=True)
    hcols = st.columns(2)
    if hcols[0].button("Back", use_container_width=True):
        st.session_state.update(selected_deck_id=None,
                                selected_deck_mode=None,
                                selected_card_id=None,
                                add_new_card=False)
        st.rerun()
    if hcols[1].button("Reset Deck", use_container_width=True):
        st.session_state.deck_pending_reset = deck_id; st.rerun()

    if st.session_state.get("deck_pending_reset") == deck_id:
        st.info("Permanently reset all SM‑2 data?")
        c1, c2 = st.columns(2)
        if c1.button("Yes, reset", use_container_width=True):
            reset_deck(deck_id); st.success("Deck reset!")
            st.session_state.deck_pending_reset = None; st.rerun()
        if c2.button("No, cancel", use_container_width=True):
            st.session_state.deck_pending_reset = None; st.rerun()

    # ---------- data table ----------
    cards_raw = get_cards(deck_id)
    if not cards_raw:
        st.info("No cards yet."); return

    df_orig = pd.DataFrame(
        [{"id": cid, "Select": False, "Front": f, "Back": b} for cid, f, b in cards_raw]
    )
    edited = st.data_editor(
        df_orig,
        column_config={
            "id":     st.column_config.TextColumn(disabled=True),
            "Select": st.column_config.CheckboxColumn("Select"),
            "Front":  st.column_config.TextColumn("Front"),
            "Back":   st.column_config.TextColumn("Back"),
        },
        num_rows="fixed",
        hide_index=True,
        use_container_width=True,
        key=f"cards_editor_{deck_id}",
    )

    # inline name/side edits
    delta = (edited.merge(df_orig, on="id", suffixes=("_new", "_old"))
                    .query("Front_new != Front_old or Back_new != Back_old"))
    for _, r in delta.iterrows():
        update_card(int(r["id"]), r["Front_new"].strip(), r["Back_new"].strip())

    # ---------- selection ----------
    sel = edited[edited["Select"].fillna(False)]
    sel_id = int(sel.iloc[0]["id"]) if not sel.empty else None

    # ---------- buttons (Add left of Edit) ----------
    bcols = st.columns(4)
    if bcols[0].button("Add New Card", use_container_width=True):
        st.session_state.add_new_card = True
        st.session_state.selected_card_id = None; st.rerun()

    if bcols[1].button("Edit", disabled=sel_id is None, use_container_width=True):
        st.session_state.selected_card_id = sel_id
        st.session_state.add_new_card = False; st.rerun()

    if bcols[2].button("Stats", disabled=sel_id is None, use_container_width=True):
        cur = st.session_state.get("selected_stats_card_id")
        st.session_state.selected_stats_card_id = None if cur == sel_id else sel_id
        st.session_state.add_new_card = False; st.rerun()

    if bcols[3].button("Delete", disabled=sel_id is None, use_container_width=True):
        delete_card(sel_id); st.success("Deleted."); st.rerun()

    # ---------- preview / form area ----------
    with st.container(border=True):
        # ADD mode
        if st.session_state.get("add_new_card"):
            render_card_form(deck_id, editing=False, card_data=None)
            return

        # EDIT mode
        if st.session_state.get("selected_card_id"):
            cd = get_card_by_id(st.session_state.selected_card_id)
            if cd:
                render_card_form(deck_id, editing=True, card_data=cd)
            return

        # PREVIEW mode
        if sel_id:
            card = get_card_by_id(sel_id)
            if card:
                _, _, ftxt, btxt, *_ = card
                render_card_visual(ftxt, btxt, show_back=True)
                if st.session_state.get("selected_stats_card_id") == sel_id:
                    _, _, _, _, nr, interval, rep, ef, _ = card
                    nr_str = nr.split("T")[0] if nr else "—"
                    st.markdown(
                        f"<p style='text-align:center;'><em>"
                        f"Next {nr_str} &nbsp;|&nbsp; {interval} d &nbsp;|&nbsp; "
                        f"Rep {rep} &nbsp;|&nbsp; EF {ef:.2f}</em></p>",
                        unsafe_allow_html=True
                    )
        else:
            st.markdown("<p style='text-align:center;'>Select a card to preview.</p>",
                        unsafe_allow_html=True)

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

        render_chatbot_sidebar()

# ---------------------------------------------------------------------
#                       Chatbot (Sidebar)
# ---------------------------------------------------------------------
def render_chatbot_sidebar():
    """
    Fully‑featured OpenAI chatbot.
    (Logic copied from 4_Chatbot.py – only the location changed.)
    """
    st.divider()                      # ← required divider under Generate
    st.markdown("## Chatbot 💬")

    openai_api_key = os.getenv("OPENAI_API_KEY")

    # Initialise chat history once
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "How can I help you?"}
        ]

    # Display history
    for m in st.session_state.messages:
        st.chat_message(m["role"]).write(m["content"])

    # Handle new user input
    if prompt := st.chat_input("Ask me anything…"):
        if not openai_api_key:
            st.info("Please add an OpenAI API key to continue.")
            st.stop()

        client = OpenAI(api_key=openai_api_key)

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.messages,
        )
        reply = resp.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").write(reply)

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
