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

# Rendering a card's front/back + extras with st.image where needed
def render_card_visual(front, back, extras=None, show_back=False):
    """
    Renders the card's front, and optionally back + extras.
    Any embedded data URIs are extracted and displayed via st.image().
    """
    # --- FRONT ---
    st.markdown("<h1 style='text-align:center;'>Front</h1>", unsafe_allow_html=True)
    text_front = front
    st.markdown(text_front)

    if show_back:
        st.divider()
        # --- BACK ---
        st.markdown("<h1 style='text-align:center;'>Back</h1>", unsafe_allow_html=True)
        text_back = back
        st.markdown(text_back)

    # --- EXTRAS ---
    if extras and len(extras) > 0:
        st.divider()
        for field_name, field_value in extras.items():
            st.markdown(f"### {field_name}")
            text_extra = field_value
            st.markdown(text_extra)

# Main form: Add/Edit a card
def render_card_form(deck_id, editing=False, card_data=None, allow_image_attach=False):
    """
    Renders a form for adding or editing a card.
    If editing=True and card_data is given, fields are pre-populated.
    The 'allow_image_attach' flag determines whether the image-upload
    and removal UI is shown.
    """

    if "card_form_values" not in st.session_state:
        st.session_state.card_form_values = {}
    if deck_id not in st.session_state.card_form_values:
        st.session_state.card_form_values[deck_id] = {}

    # ------------------ Load existing data (if editing) ------------------
    if editing and card_data:
        db_front = card_data[2]  # front
        db_back  = card_data[3]  # back
        db_extra_json = card_data[8]

        if db_extra_json:
            try:
                db_extra_data = json.loads(db_extra_json)
            except:
                db_extra_data = {}
        else:
            db_extra_data = {}

        for field in st.session_state.deck_fields[deck_id]:
            if field == "Front":
                st.session_state.card_form_values[deck_id][field] = db_front
            elif field == "Back":
                st.session_state.card_form_values[deck_id][field] = db_back
            else:
                st.session_state.card_form_values[deck_id][field] = db_extra_data.get(field, "")
    else:
        # Clear fields if adding new
        for field in st.session_state.deck_fields[deck_id]:
            if field not in st.session_state.card_form_values[deck_id]:
                st.session_state.card_form_values[deck_id][field] = ""

    # ------------------ FORM ------------------
    with st.form(f"card_form_{deck_id}"):
        # Text fields
        for field in st.session_state.deck_fields[deck_id]:
            st.session_state.card_form_values[deck_id][field] = st.text_area(
                label=field,
                value=st.session_state.card_form_values[deck_id][field],
                placeholder=f"Enter {field} here",
                key=f"card_field_{deck_id}_{field}",
                height=80
            )

        # --- Live preview ---
        front_val = st.session_state.card_form_values[deck_id].get("Front", "")
        back_val  = st.session_state.card_form_values[deck_id].get("Back", "")
        extras_val = {
            f: st.session_state.card_form_values[deck_id][f]
            for f in st.session_state.deck_fields[deck_id]
            if f not in ("Front", "Back")
        }

        st.markdown("---")
        st.markdown("<h6 style='text-align:center;'>Preview</h6>", unsafe_allow_html=True)
        render_card_visual(front_val, back_val, extras=extras_val, show_back=True)

        # --- Submit / Edit fields buttons ---
        btn_cols = st.columns([1, 1])
        submit_label = "Update Card" if editing else "Add Card"
        submitted = btn_cols[0].form_submit_button(submit_label, use_container_width=True)
        edit_pressed = btn_cols[1].form_submit_button("Edit Fields", use_container_width=True)

        if edit_pressed:
            st.session_state.edit_fields = True
            st.stop()

        if submitted:
            if front_val.strip() and back_val.strip():
                new_extras_data = {
                    f: st.session_state.card_form_values[deck_id][f]
                    for f in st.session_state.deck_fields[deck_id]
                    if f not in ("Front", "Back")
                }
                if editing and card_data:
                    card_id = card_data[0]
                    update_card(card_id, front_val.strip(), back_val.strip(), new_extras_data)
                    st.success("Flashcard updated!")
                    st.session_state.selected_card_id = None
                else:
                    add_card(deck_id, front_val.strip(), back_val.strip(), new_extras_data)
                    st.success("Flashcard added!")

                st.session_state.card_form_values[deck_id].clear()
                st.rerun()
            else:
                st.error("Please provide both Front and Back text.")
