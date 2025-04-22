# flashcards.py

"""
Manage flashcard decks and cards within the EduForge Streamlit app.
Provides interfaces for listing/creating/renaming/deleting decks,
viewing and editing cards, spaced-repetition review workflows,
and advanced field customization.
"""

import json
import streamlit as st

from dialogs import import_deck_dialog
from utils.flashcards_db import (
    add_card, create_deck, delete_card, get_card_by_id, get_cards,
    get_deck_stats, get_decks, rename_deck, reset_deck, trash_deck, update_card
)
from utils.flashcards_sm2 import update_sm2, project_interval, format_interval_short


def render_decks_section() -> None:
    """
    Display and edit the list of flashcard decks using a data_editor.
    Users can add, rename, select decks, and perform import/export/delete actions.
    """
    import pandas as pd

    # Section header
    st.markdown("<h2 style='text-align:center;'>Flashcard Decks</h2>", unsafe_allow_html=True)

    # Fetch raw deck data
    decks_raw = get_decks()
    if decks_raw:
        # Build DataFrame including stats for each deck
        df_orig = pd.DataFrame([
            {
                "id": d_id,
                "Select": False,
                "Deck": d_name,
                **get_deck_stats(d_id)  # live 'new', 'learn', 'due' counts
            }
            for d_id, d_name in decks_raw
        ])
    else:
        # Empty template to allow creation of first deck
        df_orig = pd.DataFrame(columns=["id", "Select", "Deck", "new", "learn", "due"])

    # Configure columns: disable stats and id, make Select a checkbox
    col_cfg = {
        "id": st.column_config.TextColumn(disabled=True),
        "new": st.column_config.NumberColumn("New", disabled=True),
        "learn": st.column_config.NumberColumn("Learn", disabled=True),
        "due": st.column_config.NumberColumn("Due", disabled=True),
        "Select": st.column_config.CheckboxColumn("Select")
    }

    # Render data editor for decks list
    edited_df = st.data_editor(
        df_orig,
        column_config=col_cfg,
        num_rows="dynamic",  # allow user to add rows
        hide_index=True,
        use_container_width=True,
        key="decks_editor"
    )

    # Persist data-editor changes
    # Handle new deck creation from rows without id
    new_rows = edited_df[edited_df["id"].isna() & edited_df["Deck"].notna()]
    created_any = False
    existing_names = {n.lower() for _, n in decks_raw}
    for _, row in new_rows.iterrows():
        new_name = row["Deck"].strip()
        if not new_name:
            continue  # skip blank entries
        if new_name.lower() in existing_names:
            st.error(f"Deck name '{new_name}' already exists.")
            continue
        create_deck(new_name)
        created_any = True
        existing_names.add(new_name.lower())

    # Handle renames: compare edited vs original names
    renamed = (
        edited_df[edited_df["id"].notna()]
        .merge(df_orig[["id", "Deck"]], on="id", suffixes=("_new", "_old"))
    )
    for _, r in renamed.iterrows():
        old = r["Deck_old"].strip()
        new = r["Deck_new"].strip()
        if new == old:
            continue  # no change
        if new.lower() in existing_names:
            st.error(f"Deck name '{new}' already exists.")
            continue
        rename_deck(int(r["id"]), new)
        existing_names.discard(old.lower())
        existing_names.add(new.lower())

    # If any deck was created, rerun to refresh stats
    if created_any:
        st.rerun()

    # Determine selected deck (first checked row)
    sel_rows = edited_df[edited_df["Select"].fillna(False)]
    sel_deck_id = int(sel_rows.iloc[0]["id"]) if not sel_rows.empty else None
    sel_deck_name = sel_rows.iloc[0]["Deck"] if not sel_rows.empty else None

    # Action buttons
    with st.container():
        col_review, col_browse, col_import, col_export, col_delete = st.columns(5)

        # Review button: enter spaced-repetition review mode
        if col_review.button(
            "", key="deck_review_btn",
            type="tertiary", icon=":material/play_arrow:",
            use_container_width=True,
            disabled=sel_deck_id is None
        ):
            st.session_state.update(
                selected_deck_id=sel_deck_id,
                selected_deck_mode="review",
                review_card_id=None,
                review_show_answer=False,
                review_edit_mode=False,
            )
            st.rerun()

        # Browse button: show deck detail view
        if col_browse.button(
            "", key="deck_browse_btn",
            type="tertiary", icon=":material/visibility:",
            use_container_width=True,
            disabled=sel_deck_id is None
        ):
            st.session_state.selected_deck_id = sel_deck_id
            st.session_state.selected_deck_mode = "browse"
            st.rerun()

        # Import button: open import dialog
        if col_import.button(
            "", key="deck_import_btn",
            type="tertiary", icon=":material/upload:",
            use_container_width=True
        ):
            import_deck_dialog()

        # Export button: download deck JSON if selected
        if sel_deck_id is not None:
            deck_json = json.dumps(
                {
                    "name": sel_deck_name,
                    "cards": [
                        {"front": c[1], "back": c[2]} for c in get_cards(sel_deck_id)
                    ]
                }, indent=2
            )
            col_export.download_button(
                label="", data=deck_json,
                file_name=f"{sel_deck_name}.json",
                mime="application/json",
                key=f"download_deck_{sel_deck_id}",
                type="tertiary", icon=":material/download:",
                use_container_width=True
            )
        else:
            col_export.button(
                "", disabled=True,
                key="deck_export_btn_disabled",
                type="tertiary", icon=":material/download:",
                use_container_width=True
            )

        # Delete button: mark deck pending deletion
        if col_delete.button(
            "", key="deck_delete_btn",
            type="tertiary", icon=":material/delete:",
            use_container_width=True,
            disabled=sel_deck_id is None
        ):
            st.session_state.deck_pending_delete = sel_deck_id
            st.rerun()

    # Deletion confirmation
    pending_deck_id = st.session_state.get("deck_pending_delete")
    if pending_deck_id is not None:
        # Look up deck name for display
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


def render_deck_detail(deck_id: int) -> None:
    """
    Show card list for a specific deck in either browse or edit mode.
    Allow inline editing, addition, deletion, and SM-2 reset.
    """
    import pandas as pd
    from utils.flashcards_db import c

    # Load deck name from DB
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("Deck not found.")
        st.session_state.update(selected_deck_id=None, selected_deck_mode=None)
        return
    deck_name = row[0]

    # Header with Back and Reset buttons
    st.markdown(f"<h2 style='text-align:center;'>{deck_name}</h2>", unsafe_allow_html=True)
    hcols = st.columns(2)
    if hcols[0].button("Back", use_container_width=True):
        # Clear deck selection state
        st.session_state.update(
            selected_deck_id=None,
            selected_deck_mode=None,
            selected_card_id=None,
            add_new_card=False
        )
        st.rerun()
    if hcols[1].button("Reset Deck", use_container_width=True):
        st.session_state.deck_pending_reset = deck_id
        st.rerun()

    # Confirm reset action
    if st.session_state.get("deck_pending_reset") == deck_id:
        st.info("Permanently reset all SM‑2 data?")
        c1, c2 = st.columns(2)
        if c1.button("Yes, reset", use_container_width=True):
            reset_deck(deck_id)
            st.success("Deck reset!")
            st.session_state.deck_pending_reset = None
            st.rerun()
        if c2.button("No, cancel", use_container_width=True):
            st.session_state.deck_pending_reset = None
            st.rerun()

    # Fetch cards for this deck
    cards_raw = get_cards(deck_id)
    if not cards_raw:
        st.info("No cards yet.")
        return

    # Build DataFrame for cards list
    df_orig = pd.DataFrame([
        {"id": cid, "Select": False, "Front": f, "Back": b}
        for cid, f, b in cards_raw
    ])
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
        key=f"cards_editor_{deck_id}"
    )

    # Inline edits: detect changes in Front or Back and update
    delta = (
        edited.merge(df_orig, on="id", suffixes=("_new", "_old"))
              .query("Front_new != Front_old or Back_new != Back_old")
    )
    for _, r in delta.iterrows():
        update_card(int(r["id"]), r["Front_new"].strip(), r["Back_new"].strip())

    # Determine selected card for actions
    sel = edited[edited["Select"].fillna(False)]
    sel_id = int(sel.iloc[0]["id"]) if not sel.empty else None

    # Buttons: Add New, Edit, Stats, Delete
    bcols = st.columns(4)
    if bcols[0].button("Add New Card", use_container_width=True):
        st.session_state.add_new_card = True
        st.session_state.selected_card_id = None
        st.rerun()
    if bcols[1].button("Edit", disabled=sel_id is None, use_container_width=True):
        st.session_state.selected_card_id = sel_id
        st.session_state.add_new_card = False
        st.rerun()
    if bcols[2].button("Stats", disabled=sel_id is None, use_container_width=True):
        cur = st.session_state.get("selected_stats_card_id")
        st.session_state.selected_stats_card_id = None if cur == sel_id else sel_id
        st.session_state.add_new_card = False
        st.rerun()
    if bcols[3].button("Delete", disabled=sel_id is None, use_container_width=True):
        delete_card(sel_id)
        st.success("Deleted.")
        st.rerun()

    # Preview or form
    with st.container(border=True):
        # Add mode: show form for new card
        if st.session_state.get("add_new_card"):
            render_card_form(deck_id, editing=False, card_data=None)
            return
        
        # Edit mode: populate form with existing card data
        if st.session_state.get("selected_card_id"):
            cd = get_card_by_id(st.session_state.selected_card_id)
            if cd:
                render_card_form(deck_id, editing=True, card_data=cd)
            return
        
        # Preview mode: display selected card visually
        if sel_id:
            card = get_card_by_id(sel_id)
            if card:
                _, _, ftxt, btxt, *_ = card
                render_card_visual(ftxt, btxt, show_back=True)

                # Show SM-2 stats if toggled
                if st.session_state.get("selected_stats_card_id") == sel_id:
                    _, _, _, _, nr, interval, rep, ef, _ = card
                    nr_str = nr.split("T")[0] if nr else "—"
                    st.markdown(
                        f"<p style='text-align:center;'><em>"
                        f"Next {nr_str} | {interval} d | Rep {rep} | EF {ef:.2f}</em></p>",
                        unsafe_allow_html=True
                    )
        else:
            st.markdown("<p style='text-align:center;'>Select a card to preview.</p>", unsafe_allow_html=True)


def render_deck_review(deck_id: int) -> None:
    """
    Conduct a spaced-repetition review session for a deck.
    Displays cards one-by-one, handles answer reveal, grading, and scheduling.
    """
    from utils.flashcards_db import c

    # Load deck name or abort
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("This deck does not exist.")
        st.session_state.selected_deck_id = None
        return
    deck_name = row[0]

    # Top row: Back button and deck title with stats
    top_row = st.columns([2, 8])
    if top_row[0].button("Back", key="review_deck_back_btn", use_container_width=True):
        st.session_state.update(
            selected_deck_id=None,
            selected_deck_mode=None,
            review_card_id=None,
            review_show_answer=False,
            review_edit_mode=False
        )
        st.rerun()

    stats = get_deck_stats(deck_id)
    top_row[1].markdown(
        f"<h2 style='text-align:left;'>{deck_name} — Review</h2>"
        f"<p>New: {stats['new']} | Learn: {stats['learn']} | Due: {stats['due']}</p>",
        unsafe_allow_html=True
    )

    # If no cards to review, show success message
    if stats['new'] == 0 and stats['due'] == 0:
        st.success("Congratulations! You have completed your review.")
        return

    st.divider()
    cards_data = get_cards(deck_id)
    if not cards_data:
        st.info("No cards to review.")
        return

    # Initialize current card if not set
    if st.session_state.review_card_id is None:
        st.session_state.review_card_id = cards_data[0][0]

    # Load the current card record
    card = get_card_by_id(st.session_state.review_card_id)
    if not card:
        st.error("Selected card not found.")
        return

    (card_id, _, front, back, next_rev, interval, repetition, ef, extra_json) = card

    # Edit mode: allow in-place editing of flashcard
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

    # Parse any extra JSON data for rendering
    extras = {}
    if extra_json:
        try:
            extras = json.loads(extra_json)
        except json.JSONDecodeError:
            extras = {}

    # Display card front/back and extras
    render_card_visual(front, back, extras=extras, show_back=st.session_state.review_show_answer)
    st.divider()

    # Show answer or grading buttons based on state
    if not st.session_state.review_show_answer:
        if st.button("Show Answer", key="show_answer_btn", use_container_width=True):
            st.session_state.review_show_answer = True
            st.rerun()
    else:
        # Compute projected intervals for each grade
        proj_again = format_interval_short(project_interval(card, 0))
        proj_hard  = format_interval_short(project_interval(card, 3))
        proj_good  = format_interval_short(project_interval(card, 4))
        proj_easy  = format_interval_short(project_interval(card, 5))

        # Display projections row
        h_cols = st.columns([2,1,1,1,1])
        h_cols[1].markdown(proj_again)
        h_cols[2].markdown(proj_hard)
        h_cols[3].markdown(proj_good)
        h_cols[4].markdown(proj_easy)

        # Grading buttons: apply SM-2 update and move to next card
        b_cols = st.columns([2,1,1,1,1])
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


def go_to_next_card(deck_id: int) -> None:
    """
    Advance review to the next card in the deck, cycling back if at end.
    Resets answer visibility and edit mode.
    """
    cards_data = get_cards(deck_id)
    if not cards_data:
        return
    ids = [c[0] for c in cards_data]
    cur = st.session_state.review_card_id
    if cur in ids:
        idx = ids.index(cur)
        st.session_state.review_card_id = ids[(idx + 1) % len(ids)]
        st.session_state.review_show_answer = False
        st.session_state.review_edit_mode = False
    st.rerun()


def render_edit_fields(deck_id: int) -> None:
    """
    Provide an interface for customizing additional card fields per deck.
    Mandatory fields Front/Back are fixed; extra fields can be added or removed.
    """
    st.markdown("### Edit Card Fields")
    # Iterate over existing fields
    for i, field in enumerate(st.session_state.deck_fields[deck_id].copy()):
        c1, c2 = st.columns([4,1])
        if field in ["Front", "Back"]:
            # Mandatory fields cannot be removed
            c1.text_input(f"Field {i+1} (Mandatory)", value=field, key=f"edit_field_{deck_id}_{i}", disabled=True)
        else:
            # Editable extra field
            new_val = c1.text_input(f"Field {i+1}", value=field, key=f"edit_field_{deck_id}_{i}")
            st.session_state.deck_fields[deck_id][i] = new_val
            if c2.button("Delete", key=f"delete_field_{deck_id}_{i}", use_container_width=True):
                st.session_state.deck_fields[deck_id].pop(i)
                st.rerun()

    # Add a new field
    nf = st.text_input("New Field Name", key=f"new_field_input_{deck_id}")
    if st.button("Add Field", key=f"add_field_button_{deck_id}", use_container_width=True):
        if nf and nf not in st.session_state.deck_fields[deck_id]:
            st.session_state.deck_fields[deck_id].append(nf)
            st.rerun()

    # Finish editing fields
    if st.button("Done Editing Fields", key=f"done_edit_fields_{deck_id}", use_container_width=True):
        st.session_state.edit_fields = False
        st.rerun()


def render_card_visual(front: str, back: str, extras=None, show_back: bool=False) -> None:
    """
    Display a flashcard's front, optionally its back, and any extra fields.
    Uses markdown and headers for layout.
    """
    # Show Front side
    st.markdown("<h1 style='text-align:center;'>Front</h1>", unsafe_allow_html=True)
    st.markdown(front)

    if show_back:
        st.divider()
        st.markdown("<h1 style='text-align:center;'>Back</h1>", unsafe_allow_html=True)
        st.markdown(back)

    # Show any extra fields below
    if extras:
        st.divider()
        for name, value in extras.items():
            st.markdown(f"### {name}")
            st.markdown(value)


def render_card_form(deck_id: int, editing: bool=False, card_data=None, allow_image_attach: bool=False) -> None:
    """
    Render a form for adding or editing a flashcard.
    Pre-populates fields if editing, and provides live preview.
    """
    # Initialize form state storage
    if "card_form_values" not in st.session_state:
        st.session_state.card_form_values = {}
    if deck_id not in st.session_state.card_form_values:
        st.session_state.card_form_values[deck_id] = {}

    # Load existing card data into form values when editing
    if editing and card_data:
        db_front, db_back, extra_json = card_data[2], card_data[3], card_data[8]
        try:
            extra_data = json.loads(extra_json) if extra_json else {}
        except json.JSONDecodeError:
            extra_data = {}
        for field in st.session_state.deck_fields[deck_id]:
            if field == "Front":
                st.session_state.card_form_values[deck_id][field] = db_front
            elif field == "Back":
                st.session_state.card_form_values[deck_id][field] = db_back
            else:
                st.session_state.card_form_values[deck_id][field] = extra_data.get(field, "")
    else:
        # Clear values when adding new
        for field in st.session_state.deck_fields[deck_id]:
            st.session_state.card_form_values[deck_id].setdefault(field, "")

    # Render the form
    with st.form(f"card_form_{deck_id}"):
        # Text areas for each field
        for field in st.session_state.deck_fields[deck_id]:
            st.session_state.card_form_values[deck_id][field] = st.text_area(
                label=field,
                value=st.session_state.card_form_answers if False else st.session_state.card_form_values[deck_id][field],
                placeholder=f"Enter {field} here",
                key=f"card_field_{deck_id}_{field}",
                height=80
            )

        # Live preview of card
        front_val = st.session_state.card_form_values[deck_id].get("Front", "")
        back_val = st.session_state.card_form_values[deck_id].get("Back", "")
        extras_val = {
            f: st.session_state.card_form_values[deck_id][f]
            for f in st.session_state.deck_fields[deck_id]
            if f not in ("Front", "Back")
        }
        st.markdown("---")
        st.markdown("<h6 style='text-align:center;'>Preview</h6>", unsafe_allow_html=True)
        render_card_visual(front_val, back_val, extras=extras_val, show_back=True)

        # Submission and edit-fields buttons
        btn_cols = st.columns([1,1])
        submit_label = "Update Card" if editing else "Add Card"
        submitted = btn_cols[0].form_submit_button(submit_label, use_container_width=True)
        edit_pressed = btn_cols[1].form_submit_button("Edit Fields", use_container_width=True)

        if edit_pressed:
            st.session_state.edit_fields = True
            st.stop()

        if submitted:
            # Validate mandatory fields
            if front_val.strip() and back_val.strip():
                # Collect extra field data
                extras_to_save = {
                    f: st.session_state.card_form_values[deck_id][f]
                    for f in st.session_state.deck_fields[deck_id]
                    if f not in ("Front", "Back")
                }
                if editing and card_data:
                    card_id = card_data[0]
                    update_card(card_id, front_val.strip(), back_val.strip(), extras_to_save)
                    st.success("Flashcard updated!")
                    st.session_state.selected_card_id = None
                else:
                    add_card(deck_id, front_val.strip(), back_val.strip(), extras_to_save)
                    st.success("Flashcard added!")

                # Clear form values and rerun to reflect changes
                st.session_state.card_form_values[deck_id].clear()
                st.rerun()
            else:
                st.error("Please provide both Front and Back text.")
