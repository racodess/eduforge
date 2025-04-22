# notebooks.py

"""
Provides notebook and note management UIs for the EduForge study platform.
Includes listing, creating, renaming, deleting notebooks and tabs,
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

# Default content for a new notebook tab when none exist
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
        "id": st.column_config.TextColumn(disabled=True),
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
        if btn_cols[0].button("", key="nb_review_btn", type="tertiary",
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
        if btn_cols[1].button("", key="nb_browse_btn", type="tertiary",
                               icon=":material/visibility:", use_container_width=True,
                               disabled=sel_nb_id is None):
            st.session_state.selected_notebook_id = sel_nb_id
            st.rerun()

        # Import button
        if btn_cols[2].button("", key="nb_import_btn", type="tertiary",
                               icon=":material/upload:", use_container_width=True):
            import_notebook_dialog()

        # Excport button (JSON download) if selection exists
        if sel_nb_id is not None:
            nb_json = json.dumps(
                {
                    "name": sel_nb_name,
                    "notes": [
                        {"tab_name": n[1], "content": n[2]} for n in get_notes(sel_nb_id)
                    ],
                }, indent=2
            )
            btn_cols[3].download_button(
                label="", data=nb_json,
                file_name=f"{sel_nb_name}.json",
                mime="application/json", key=f"download_nb_{sel_nb_id}",
                type="tertiary", icon=":material/download:",
                use_container_width=True
            )
        else:
            btn_cols[3].button("", disabled=True, key="nb_export_btn_disabled",
                                type="tertiary", icon=":material/download:",
                                use_container_width=True)

        # Delete button with confirmation
        if btn_cols[4].button("", key="nb_delete_btn", type="tertiary",
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
    Show detail view of a single notebook, listing tabs (notes) with editing,
    preview, rename, delete, and reset stats options.
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

    # Header with notebook title
    st.markdown(f"<h2 style='text-align:center;'>{nb_name}</h2>", unsafe_allow_html=True)

    # Back and Reset Stats buttons
    hcols = st.columns(2)
    if hcols[0].button("Back", use_container_width=True):
        st.session_state.selected_notebook_id = None
        st.rerun()
    if hcols[1].button("Reset Stats", use_container_width=True):
        _reset_notebook_stats(nb_id, notes_c, notes_conn)
        st.success("All SM‑2 data reset.")
        st.rerun()

    # Fetch or initialize notes for this notebook
    notes = get_notes(nb_id)
    if not notes:
        create_note(nb_id, "Default", DEFAULT_TAB_CONTENT)
        st.rerun()

    # Build DataFrame for tabs with id, selection, and tab name
    df_orig = pd.DataFrame([{"id": nid, "Select": False, "Tab": t} for nid, t, _ in notes])
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

    # Inline renaming: detect changed Tab names and update DB
    delta = (
        edited.merge(df_orig, on="id", suffixes=("_new", "_old"))
             .query("Tab_new != Tab_old")
    )
    for _, r in delta.iterrows():
        rename_note(int(r["id"]), r["Tab_new"].strip())

    # If currently editing a tab, render the form and exit
    if st.session_state.get("editing_tab_id"):
        _render_tab_edit_form(nb_id)
        return

    # Determine selected tab row for preview/edit/delete
    sel = edited[edited["Select"].fillna(False)]
    sel_id = int(sel.iloc[0]["id"]) if not sel.empty else None
    selected_note = next((n for n in notes if n[0] == sel_id), None)

    # Buttons: Add Tab, Edit, Stats, Delete
    bcols = st.columns(4)
    if bcols[0].button("Add Tab", use_container_width=True):
        new_id = create_note(nb_id, "New Tab", "")
        st.session_state.editing_tab_id = new_id
        st.rerun()
    if bcols[1].button("Edit", disabled=sel_id is None, use_container_width=True):
        st.session_state.editing_tab_id = sel_id
        st.rerun()
    if bcols[2].button("Stats", disabled=sel_id is None, use_container_width=True):
        cur = st.session_state.get("selected_stats_note_id")
        st.session_state.selected_stats_note_id = None if cur == sel_id else sel_id
        st.rerun()
    if bcols[3].button("Delete", disabled=sel_id is None, use_container_width=True):
        delete_note(sel_id)
        st.success("Deleted.")
        st.rerun()

    # Preview or show stats for selected tab
    if selected_note:
        _, tab, body = selected_note
        with st.container(border=True):
            st.markdown(f"### {tab}", unsafe_allow_html=True)
            # Render Graphviz if detected, else markdown content
            code = _extract_graphviz(body)
            if code:
                st.graphviz_chart(code, use_container_width=True)
            else:
                st.markdown(body or "*[Empty]*", unsafe_allow_html=True)

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
            "<p style='text-align:center;'>Select a tab to preview.</p>",
            unsafe_allow_html=True
        )


def _render_tab_edit_form(nb_id: int) -> None:
    """
    Inline form to rename and edit a single notebook tab.
    Provides Save and Cancel buttons to commit or abort changes.
    """
    note_id = st.session_state.editing_tab_id
    note = get_note_by_id(note_id)
    if not note:
        st.error("Note not found.")
        st.session_state.editing_tab_id = None
        return
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
                st.success("Saved!")
                st.rerun()
            if c2.form_submit_button("Cancel", use_container_width=True):
                st.session_state.editing_tab_id = None
                st.rerun()


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
    """
    Present a spaced-repetition review interface for a notebook's notes.
    Includes grading buttons (Again, Hard, Good, Easy) and next-review projections.
    """
    # Header with back button and title/stats
    top = st.columns([2, 8])
    if top[0].button("Back", key="nb_rev_back", use_container_width=True):
        st.session_state.update(
            selected_notebook_id=None,
            selected_notebook_mode=None,
            review_note_id=None,
            review_note_edit_mode=False,
        )
        st.rerun()

    stats = get_notebook_stats(nb_id)
    name = next(n for n in get_notebooks() if n[0] == nb_id)[1]
    top[1].markdown(
        f"<h2 style='text-align:left;'>{name} — Review</h2>"
        f"<p>New: {stats['new']} | Due: {stats['due']}</p>",
        unsafe_allow_html=True
    )

    # If nothing to review, show success message
    if stats["new"] == 0 and stats["due"] == 0:
        st.success("🎉  Nothing to review right now!")
        return

    # Load full notes with SM-2 data
    notes = get_notes_full(nb_id)
    if not notes:
        st.info("Notebook is empty.")
        return

    # Initialize or fetch current review note id
    if st.session_state.review_note_id is None:
        st.session_state.review_note_id = notes[0][0]
    note = get_note_by_id(st.session_state.review_note_id)
    if not note:
        st.error("Note not found.")
        return

    note_id, _, tab_name, content, nr, interval, repetition, ef = note
    st.markdown(f"### {tab_name}")

    # Edit mode for current note review
    if st.session_state.review_note_edit_mode:
        with st.form("edit_note_review", clear_on_submit=False):
            new_tab = st.text_input("Tab Name", value=tab_name)
            new_body = st.text_area("Content", value=content, height=300)
            e1, e2 = st.columns(2)
            with e2:
                if st.form_submit_button("Save"):
                    rename_note(note_id, new_tab)
                    update_note(note_id, new_body)
                    st.success("Updated!")
                    st.session_state.review_note_edit_mode = False
                    st.rerun()
            with e1:
                if st.form_submit_button("Cancel"):
                    st.session_state.review_note_edit_mode = False
                    st.rerun()
        return

    # View mode: render content or graphviz
    code = _extract_graphviz(content)
    if code:
        st.graphviz_chart(code, use_container_width=True)
    else:
        st.markdown(content if content.strip() else "*[Empty note]*", unsafe_allow_html=True)

    st.divider()

    # Show next-review projections for grading buttons
    proj_a = format_interval_short(project_interval_note(note, 0))
    proj_h = format_interval_short(project_interval_note(note, 3))
    proj_g = format_interval_short(project_interval_note(note, 4))
    proj_e = format_interval_short(project_interval_note(note, 5))

    ph = st.columns([2, 1, 1, 1, 1])
    ph[1].markdown(proj_a)
    ph[2].markdown(proj_h)
    ph[3].markdown(proj_g)
    ph[4].markdown(proj_e)

    # Grading buttons: Again, Hard, Good, Easy
    pb = st.columns([2, 1, 1, 1, 1])
    if pb[0].button("Edit", key="nb_rev_edit"):
        st.session_state.review_note_edit_mode = True
        st.rerun()
    if pb[1].button("Again"):
        update_sm2_note(note_id, 0)
        _next_note(nb_id)
    if pb[2].button("Hard"):
        update_sm2_note(note_id, 3)
        _next_note(nb_id)
    if pb[3].button("Good"):
        update_sm2_note(note_id, 4)
        _next_note(nb_id)
    if pb[4].button("Easy"):
        update_sm2_note(note_id, 5)
        _next_note(nb_id)


def _next_note(nb_id: int) -> None:
    """
    Advance to the next note in review, cycling through list.
    Resets edit mode and reruns UI.
    """
    from utils.notes_db import get_notes_full
    notes = get_notes_full(nb_id)
    if not notes:
        return
    ids = [n[0] for n in notes]
    cur = st.session_state.review_note_id
    idx = ids.index(cur) if cur in ids else -1

    # Cycle to next note id
    st.session_state.review_note_id = ids[(idx + 1) % len(ids)]
    st.session_state.review_note_edit_mode = False
    st.rerun()
