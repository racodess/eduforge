# notebooks.py

"""
Provides notebook and note management UIs for the EduForge study platform.
Includes listing, creating, renaming, deleting notebooks and notes,
detailed note editing, preview, and spaced-repetition review workflows.
"""

import json
import streamlit as st

from generated_items import _extract_graphviz
from utils.notes_db import (
    get_notebooks, create_notebook, delete_notebook, rename_notebook,
    get_notes, create_note, update_note, rename_note, delete_note,
    get_notebook_stats, get_note_by_id, get_notes_full
)
from utils.flashcards_sm2 import format_interval_short
from utils.notes_sm2 import update_sm2 as update_sm2_note, project_interval as project_interval_note

# Default content for a new notebook note when none exist
DEFAULT_NOTE_CONTENT = """\
# Welcome to Your Notebook!

This is your *default* note. Each notebook must always have at least one note.

## Quick Guide
- **Add** creates a new note and immediately opens it in an edit form so you can name it and add notes. 
  - If you have only a single "Default" note, it’s automatically removed right after the new one is created.
- **Edit** a note to rename or modify it. You will see a "Save" and "Cancel" button for that note.
- **Delete** a note from the notebook-level "Delete" button (opens a dialog).
  
All notes support **GitHub-Flavored Markdown** (headings, bold, italics, bullet lists, etc.). 
"""


def render_notebooks_section() -> None:
    """
    Display a table of all notebooks with stats, allow creating/renaming/deleting,
    and provide action buttons for review, browse, import, export, and delete.
    """
    import pandas as pd
    from dialogs import import_notebook_dialog

    # Section header
    st.markdown("<h2 style='text-align:center;'>Notebooks</h2>", unsafe_allow_html=True)

    # Fetch existing notebooks
    notebooks_raw = get_notebooks()
    if notebooks_raw:
        # Build DataFrame with id, name, selection checkbox, and stats
        df_orig = pd.DataFrame([
            {
                "id": nb_id,
                "Select": False,
                "Notebook": nb_name,
                **get_notebook_stats(nb_id)  # live new/learn/due counts
            }
            for nb_id, nb_name in notebooks_raw
        ])
    else:
        # Empty frame with expected columns if no notebooks
        df_orig = pd.DataFrame(columns=["id", "Select", "Notebook", "new", "learn", "due"])

    # Configure how each column should render in data_editor
    col_cfg = {
        "id": None,
        "new": st.column_config.NumberColumn("New", disabled=True),
        "learn": st.column_config.NumberColumn("Learn", disabled=True),
        "due": st.column_config.NumberColumn("Due", disabled=True),
        "Select": st.column_config.CheckboxColumn("Select"),
    }

    # Render editable table for notebook management
    edited_df = st.data_editor(
        df_orig,
        column_config=col_cfg,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="notebooks_editor",
    )

    # Handle new notebook creation: rows without id
    new_rows = edited_df[edited_df["id"].isna() & edited_df["Notebook"].notna()]
    created_any = False
    existing_names = {n.lower() for _, n in notebooks_raw}
    for _, row in new_rows.iterrows():
        new_name = row["Notebook"].strip()
        if not new_name:
            continue # skip blank names
        if new_name.lower() in existing_names:
            st.error(f"Notebook name '{new_name}' already exists.")
            continue
        create_notebook(new_name)
        created_any = True
        existing_names.add(new_name.lower())

    # Handle notebook renames: compare edited vs original names
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

    # If any notebooks were created, rerun to refresh table
    if created_any:
        st.rerun()

    # Determine selected notebook from checkbox
    sel_rows = edited_df[edited_df["Select"].fillna(False)]
    sel_nb_id = int(sel_rows.iloc[0]["id"]) if not sel_rows.empty else None
    sel_nb_name = sel_rows.iloc[0]["Notebook"] if not sel_rows.empty else None

    # Action buttons: Review, Browse, Import, Export, Delete
    with st.container():
        btn_cols = st.columns(5)
        # REVIEW button
        if btn_cols[0].button("", key="nb_review_btn", type="secondary",
                               icon=":material/play_arrow:", use_container_width=True,
                               disabled=sel_nb_id is None):
            # Set state for review mode and reboot UI
            st.session_state.update(
                selected_notebook_id=sel_nb_id,
                selected_notebook_mode="review",
                review_note_id=None,
                review_note_edit_mode=False,
            )
            st.rerun()

        # Browse button
        if btn_cols[1].button("", key="nb_browse_btn", type="secondary",
                               icon=":material/folder_open:", use_container_width=True,
                               disabled=sel_nb_id is None):
            st.session_state.selected_notebook_id = sel_nb_id
            st.rerun()

        # Import button
        if btn_cols[2].button("", key="nb_import_btn", type="secondary",
                               icon=":material/upload:", use_container_width=True):
            import_notebook_dialog()

        # Excport button (JSON download) if selection exists
        if sel_nb_id is not None:
            nb_json = json.dumps(
                {
                    "name": sel_nb_name,
                    "notes": [
                        {"note_name": n[1], "content": n[2]} for n in get_notes(sel_nb_id)
                    ],
                }, indent=2
            )
            btn_cols[3].download_button(
                label="", data=nb_json,
                file_name=f"{sel_nb_name}.json",
                mime="application/json", key=f"download_nb_{sel_nb_id}",
                type="secondary", icon=":material/download:",
                use_container_width=True
            )
        else:
            btn_cols[3].button("", disabled=True, key="nb_export_btn_disabled",
                                type="secondary", icon=":material/download:",
                                use_container_width=True)

        # Delete button with confirmation
        if btn_cols[4].button("", key="nb_delete_btn", type="secondary",
                               icon=":material/delete:", use_container_width=True,
                               disabled=sel_nb_id is None):
            st.session_state.notebook_pending_delete = sel_nb_id
            st.rerun()

    # Handle delete confirmation dialog
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


def render_notebook_detail(nb_id: int) -> None:
    """
    Show detail view of a single notebook, listing notes (notes) with editing,
    preview, and spaced-repetition review workflows.
    """
    import pandas as pd
    from utils.notes_db import c as notes_c, conn as notes_conn

    # Load notebook name or error if missing
    notes_c.execute("SELECT name FROM notebooks WHERE id = ?", (nb_id,))
    row = notes_c.fetchone()
    if not row:
        st.error("Notebook missing.")
        st.session_state.selected_notebook_id = None
        return
    nb_name = row[0]

    if "add_new_note" not in st.session_state: st.session_state.add_new_note = False
    if "editing_note_id" not in st.session_state: st.session_state.editing_note_id = None

    # Header with notebook title
    st.markdown(f"<h2 style='text-align:center;'>{nb_name}</h2>", unsafe_allow_html=True)

    # Back and Reset Stats buttons
    hcols = st.columns(2)
    if hcols[0].button("", type="secondary", icon=":material/arrow_back:", use_container_width=True):
        st.session_state.update(
            selected_notebook_id=None,
            selected_notebook_mode=None,
            editing_note_id=None,
            add_new_note=False,
            selected_stats_note_id=None,
        )
        st.rerun()

    # Ask for confirmation before wiping SM-2 stats
    if hcols[1].button("Reset Stats", type="secondary", icon=":material/delete_history:", use_container_width=True):
        st.session_state.notebook_pending_reset = nb_id
        st.rerun()

    # Confirmation dialog for SM-2 stats reset
    if st.session_state.get("notebook_pending_reset") == nb_id:
        st.info("Permanently reset all SM-2 data for this notebook?")
        c1, c2 = st.columns(2)
        if c1.button("Yes, reset", use_container_width=True):
            _reset_notebook_stats(nb_id, notes_c, notes_conn)
            st.success("Notebook stats reset!")
            st.session_state.notebook_pending_reset = None
            st.rerun()
        if c2.button("No, cancel", use_container_width=True):
            st.session_state.notebook_pending_reset = None
            st.rerun()

    # Spacing
    st.text("")
    st.text("")

    # Fetch or initialize notes for this notebook
    notes = get_notes(nb_id)
    if not notes:
        create_note(nb_id, "Default", DEFAULT_NOTE_CONTENT)
        st.rerun()

    # Build DataFrame for notes with id and name
    df_notes = pd.DataFrame([
        {"id": nid, "Note": t}
        for nid, t, _ in notes
    ])

    # Configure how each column should render in data_editor
    col_cfg = {
        "id": None,
    }

    # Show as selectable table using st.dataframe
    state = st.dataframe(
        df_notes,
        use_container_width=True,
        column_config=col_cfg,
        hide_index=True,
        key=f"notes_df_{nb_id}",
        on_select="rerun",
        selection_mode="single-row"
    )

    # Determine selected note id and record selection
    selected_indices = state.selection.rows
    sel_id = None

    if selected_indices:
        row_idx = selected_indices[0]
        sel_id = int(df_notes.iloc[row_idx]["id"])
        sel_note = st.session_state.editing_note_id
        if sel_note is not None: st.session_state.editing_note_id= sel_id
    else:
        st.session_state.editing_note_id = None

    # Buttons: Add Note, Edit, Stats, Delete
    bcols = st.columns(4)
    if bcols[0].button("", type="secondary", icon=":material/add:", use_container_width=True):
        cur = st.session_state.get("add_new_note")
        st.session_state.add_new_note = False if cur is True else True
        st.session_state.editing_note_id = None
        st.rerun()
    if bcols[1].button("", disabled=sel_id is None, type="secondary", icon=":material/edit:", use_container_width=True):
        cur = st.session_state.get("editing_note_id")
        st.session_state.editing_note_id = None if cur == sel_id else sel_id
        st.session_state.add_new_note = False
        st.rerun()
    if bcols[2].button("", disabled=sel_id is None, type="secondary", icon=":material/query_stats:", use_container_width=True):
        cur = st.session_state.get("selected_stats_note_id")
        st.session_state.selected_stats_note_id = None if cur == sel_id else sel_id
        st.session_state.add_new_note = False
        st.rerun()
    if bcols[3].button("", disabled=sel_id is None, type="secondary", icon=":material/close:", use_container_width=True):
        delete_note(sel_id)
        st.success("Deleted.")
        st.rerun()

    # Spacing
    st.text("")
    st.text("")

    # Add-Note workflow
    if st.session_state.get("add_new_note"):
        render_note_form(nb_id, editing=False, note_data=None)
        return

    # Edit-Note workflow
    if st.session_state.get("editing_note_id"):
        note_row = get_note_by_id(st.session_state.editing_note_id)
        if note_row:
            render_note_form(nb_id, editing=True, note_data=note_row)
        return

    # Preview mode
    selected_note = next((n for n in notes if n[0] == sel_id), None)
    if selected_note:
        _, note, body = selected_note
        with st.container(border=True):
            render_note_visual(note, body)

            st.text("")
            st.text("")

            # Show SM-2 stats line if toggled
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
        st.markdown(
            "<h3 style='text-align:center;'>Select a note to preview.</h3>",
            unsafe_allow_html=True
        )


def _reset_notebook_stats(nb_id: int, notes_c, notes_conn) -> None:
    """
    Reset SM-2 spaced-repetition statistics for all notes in a notebook.
    """
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


def render_notebook_review(nb_id: int) -> None:
    """Render a spaced‑repetition review session for a notebook.

    The styling, spacing, and control layout now mirror the flashcard review
    view to provide a consistent user experience across study modalities.
    """

    st.markdown(
        "<h2 style='text-align:center;'>Notebook Review</h2>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        # Header section
        stats = get_notebook_stats(nb_id)
        name = next(nb for nb in get_notebooks() if nb[0] == nb_id)[1]

        # Back button (first column mirrors flashcards layout)
        top_row = st.columns([1, 1, 1, 1])
        if top_row[0].button("Back", key="nb_rev_back_btn", use_container_width=True):
            st.session_state.update(
                selected_notebook_id=None,
                selected_notebook_mode=None,
                review_note_id=None,
                review_note_edit_mode=False,
            )
            st.rerun()

        # Notebook title centred
        name_row = st.columns([1])
        name_row[0].markdown(
            f"<h2 style='text-align:center;'>{name}</h2>",
            unsafe_allow_html=True,
        )
        st.text("") # vertical breathing room

        # Review stats (colour‑coded like flashcards)
        stats_row = st.columns([1, 1, 1])
        stats_row[0].markdown(
            f"<p style='text-align:center; color:lime'>New: {stats['new']}</p>",
            unsafe_allow_html=True,
        )
        stats_row[1].markdown(
            f"<p style='text-align:center; color:yellow'>Learn: {stats['learn']}</p>",
            unsafe_allow_html=True,
        )
        stats_row[2].markdown(
            f"<p style='text-align:center; color:red'>Due: {stats['due']}</p>",
            unsafe_allow_html=True,
        )

        # If nothing is due/new, celebrate and exit early
        if stats["new"] == 0 and stats["due"] == 0:
            st.success("Congratulations! You have completed your review.")
            return

        # Divider for visual separation (mirrors flashcards)
        st.divider()

        # Note retrieval
        notes = get_notes_full(nb_id)
        if not notes:
            st.info("Notebook is empty.")
            return

        if st.session_state.review_note_id is None:
            st.session_state.review_note_id = notes[0][0]

        note = get_note_by_id(st.session_state.review_note_id)
        if not note:
            st.error("Note not found.")
            return

        note_id, _, note_name, content, nr, interval, repetition, ef = note
        render_note_visual(note_name, content)

        # extra whitespace before projections/buttons
        st.text("")
        st.text("")
        st.text("")
        st.text("")

        # Next review projections
        proj_again = format_interval_short(project_interval_note(note, 0))
        proj_hard = format_interval_short(project_interval_note(note, 3))
        proj_good = format_interval_short(project_interval_note(note, 4))
        proj_easy = format_interval_short(project_interval_note(note, 5))

        proj_cols = st.columns([1, 1, 1, 1]) # align with Edit column below
        proj_cols[0].markdown(
            f"<p style='text-align:center; color:lime;'>{proj_again}</p>",
            unsafe_allow_html=True,
        )
        proj_cols[1].markdown(
            f"<p style='text-align:center; color:red;'>{proj_hard}</p>",
            unsafe_allow_html=True,
        )
        proj_cols[2].markdown(
            f"<p style='text-align:center; color:yellow;'>{proj_good}</p>",
            unsafe_allow_html=True,
        )
        proj_cols[3].markdown(
            f"<p style='text-align:center; color:lime;'>{proj_easy}</p>",
            unsafe_allow_html=True,
        )

        def _next_note(nb_id) -> None:
            """Cycle to the next note in the review queue and rerun UI."""
            nxt_notes = get_notes_full(nb_id)
            if not nxt_notes:
                return
            ids = [n[0] for n in nxt_notes]
            cur = st.session_state.review_note_id
            idx = ids.index(cur) if cur in ids else -1
            st.session_state.review_note_id = ids[(idx + 1) % len(ids)]
            st.session_state.review_note_edit_mode = False
            st.rerun()

        # Buttons row
        btn_cols = st.columns([1, 1, 1, 1])
        if btn_cols[0].button("Again", use_container_width=True):
            update_sm2_note(note_id, 0)
            _next_note(nb_id)
        if btn_cols[1].button("Hard", use_container_width=True):
            update_sm2_note(note_id, 3)
            _next_note(nb_id)
        if btn_cols[2].button("Good", use_container_width=True):
            update_sm2_note(note_id, 4)
            _next_note(nb_id)
        if btn_cols[3].button("Easy", use_container_width=True):
            update_sm2_note(note_id, 5)
            _next_note(nb_id)

def render_note_visual(note_title: str, body: str) -> None:
    """
    Show a single note exactly once, honouring the same look-and-feel
    as flashcards.render_card_visual().
    """
    st.markdown(f"<h3 style='text-align:center;'>{note_title}</h3>",
                unsafe_allow_html=True)

    code = _extract_graphviz(body)
    if code:
        st.graphviz_chart(code, use_container_width=True)
    else:
        st.markdown(body or "*[Empty]*", unsafe_allow_html=True)


def render_note_form(nb_id: int, *, editing: bool = False,
                     note_data: tuple | None = None) -> None:
    """
    Add / edit a note and give a live preview – mirrors flashcards.render_card_form().
    `note_data` must be the DB row returned by get_note_by_id().
    """
    # Pull current values (or defaults)
    if editing and note_data:
        note_id, _, init_note, init_body, *_ = note_data
    else:
        note_id, init_note, init_body = None, "", ""

    form_key = f"note_form_{nb_id}_{note_id or 'new'}"
    with st.form(form_key, clear_on_submit=False):
        new_note = st.text_input("Note name", value=init_note,
                                key=f"{form_key}_note")
        new_body = st.text_area("Content (markdown / Graphviz)",
                                value=init_body, height=300,
                                key=f"{form_key}_body")

        # Spacing
        st.text("")
        st.text("")
        st.text("")
        st.text("")

        # Preview
        st.markdown("<h6 style='text-align:left;'>Preview</h6>", unsafe_allow_html=True)
        render_note_visual(new_note or "[Heading]", new_body)

        # Spacing
        st.text("")
        st.text("")
        st.text("")
        st.text("")

        c1, c2 = st.columns(2)
        
        if editing:
            submit_button = c1.form_submit_button("", type="secondary", icon=":material/done_all:", use_container_width=True)
        else:
            submit_button = c1.form_submit_button("", type="secondary", icon=":material/add:", use_container_width=True)

        if submit_button:
            if not new_note.strip():
                st.error("Note name cannot be empty.")
                st.stop()

            if editing and note_id: # update existing
                rename_note(note_id, new_note)
                update_note(note_id, new_body)
            else: # add new
                create_note(nb_id, new_note, new_body)
                st.session_state.add_new_note = False
            st.success("Note Updated!")
            st.session_state.editing_note_id = None
            st.rerun()

        if c2.form_submit_button("Refresh", type="secondary", icon=":material/refresh:", use_container_width=True):
            st.rerun()
