# flashcards_pages.py

import json
from datetime import datetime
import streamlit as st

from utils.flashcards_db import (
    get_decks, create_deck, trash_deck, reset_deck, get_deck_stats,
    get_cards, get_card_by_id, delete_card, update_card
)
from utils.flashcards_sm2 import update_sm2, project_interval, format_interval_short
from utils.flashcards_ui import render_card_visual, render_card_form


def render_deck_row(deck_id, deck_name, stats):
    row_cols = st.columns([2, 1, 1, 1, 6])
    row_cols[0].write(deck_name)
    row_cols[1].write(stats["new"])
    row_cols[2].write(stats["learn"])
    row_cols[3].write(stats["due"])

    with row_cols[4]:
        action_cols = st.columns(4)
        # Review
        if action_cols[0].button("Review", key=f"review_deck_{deck_id}"):
            st.session_state.selected_deck_id = deck_id
            st.session_state.selected_deck_mode = "review"
            st.session_state.review_card_id = None
            st.session_state.review_show_answer = False
            st.session_state.review_edit_mode = False
            st.rerun()

        # Browse
        if action_cols[1].button("Browse", key=f"browse_deck_{deck_id}"):
            st.session_state.selected_deck_id = deck_id
            st.session_state.selected_deck_mode = "browse"
            st.rerun()

        # Export
        cards_data = get_cards(deck_id)
        deck_data = {
            "name": deck_name,
            "cards": [{"front": card[1], "back": card[2]} for card in cards_data]
        }
        deck_json = json.dumps(deck_data, indent=2)
        action_cols[2].download_button(
            "Export",
            deck_json,
            file_name=f"{deck_name}.json",
            mime="application/json",
            key=f"export_deck_{deck_id}"
        )

        # Delete
        if action_cols[3].button("Delete", key=f"delete_deck_{deck_id}"):
            st.session_state.deck_pending_delete = deck_id
            st.rerun()


def render_deck_list():
    decks = get_decks()
    if decks:
        header_cols = st.columns([2, 1, 1, 1, 6])
        header_cols[0].markdown("**Deck**")
        header_cols[1].markdown("**New**")
        header_cols[2].markdown("**Learn**")
        header_cols[3].markdown("**Due**")

        for deck_id, deck_name in decks:
            stats = get_deck_stats(deck_id)
            render_deck_row(deck_id, deck_name, stats)

            # Confirm deck deletion
            if st.session_state.deck_pending_delete == deck_id:
                st.info("Are you sure you want to delete this deck?")
                confirm_cols = st.columns(2)
                if confirm_cols[0].button("Yes", key=f"confirm_delete_yes_{deck_id}"):
                    trash_deck(deck_id)
                    st.success(f"Deck '{deck_name}' deleted!")
                    st.session_state.deck_pending_delete = None
                    st.rerun()
                if confirm_cols[1].button("No", key=f"confirm_delete_no_{deck_id}"):
                    st.session_state.deck_pending_delete = None
                    st.rerun()
    else:
        st.info("No decks found. Create one below.")

    st.divider()
    st.subheader("Create New Deck")
    new_deck_name = st.text_input("Deck Name", "")
    if st.button("Create Deck"):
        if new_deck_name.strip():
            create_deck(new_deck_name.strip())
            st.rerun()
        else:
            st.error("Please provide a valid deck name.")

    st.divider()
    st.subheader("Import Deck")
    imported_file = st.file_uploader("Select a deck file (JSON)", type=["json"], key="import_deck")
    if st.button("Import"):
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
                            c.execute(
                                """INSERT INTO cards
                                   (deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                (new_deck_id, front, back, None, 0, 0, 2.5, None)
                            )
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
            st.error("Please select a deck file to import.")


def render_edit_fields(deck_id):
    st.markdown("### Edit Card Fields")
    # Copy the fields list to avoid mutating while iterating
    for i, field in enumerate(st.session_state.deck_fields[deck_id].copy()):
        col1, col2 = st.columns([4, 1])
        if field in ["Front", "Back"]:
            col1.text_input(
                f"Field {i+1} (Mandatory)",
                value=field,
                key=f"edit_field_{deck_id}_{i}",
                disabled=True
            )
        else:
            new_val = col1.text_input(
                f"Field {i+1}",
                value=field,
                key=f"edit_field_{deck_id}_{i}"
            )
            st.session_state.deck_fields[deck_id][i] = new_val
            if col2.button("Delete", key=f"delete_field_{deck_id}_{i}"):
                st.session_state.deck_fields[deck_id].pop(i)
                st.rerun()

    new_field = st.text_input("New Field Name", key=f"new_field_input_{deck_id}")
    if st.button("Add Field", key=f"add_field_button_{deck_id}"):
        if new_field and new_field not in st.session_state.deck_fields[deck_id]:
            st.session_state.deck_fields[deck_id].append(new_field)
            st.rerun()

    if st.button("Done Editing Fields", key=f"done_edit_fields_{deck_id}"):
        st.session_state.edit_fields = False
        st.rerun()


def render_deck_detail(deck_id):
    from utils.flashcards_db import c
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("This deck does not exist.")
        st.session_state.selected_deck_id = None
        st.stop()

    deck_name = row[0]
    top_row = st.columns([2, 8, 2])

    # Go back to deck list
    if top_row[0].button("Back"):
        st.session_state.selected_deck_id = None
        st.session_state.selected_deck_mode = None
        st.rerun()

    top_row[1].markdown(f"<h2 style='text-align:left;'>{deck_name}</h2>", unsafe_allow_html=True)

    # Reset deck’s SM-2 stats
    if top_row[2].button("Reset Deck"):
        st.session_state.deck_pending_reset = deck_id
        st.rerun()

    if st.session_state.deck_pending_reset == deck_id:
        st.info("Are you sure you want to permanently reset the SM‑2 stats for this deck?")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("Yes", key=f"confirm_reset_yes_{deck_id}"):
            reset_deck(deck_id)
            st.success("Deck reset successfully!")
            st.session_state.deck_pending_reset = None
            st.rerun()
        if confirm_cols[1].button("No", key=f"confirm_reset_no_{deck_id}"):
            st.session_state.deck_pending_reset = None
            st.rerun()

    # Initialize deck field definitions if not present
    if deck_id not in st.session_state.deck_fields:
        st.session_state.deck_fields[deck_id] = ["Front", "Back"]

    # If user is editing fields
    if st.session_state.get("edit_fields", False):
        render_edit_fields(deck_id)
        return

    # Viewing a single card in “View” mode
    if st.session_state.view_card_id:
        card_to_view = get_card_by_id(st.session_state.view_card_id)
        if card_to_view:
            _, _, front, back, _, _, _, _, extra_json = card_to_view
            extras = {}
            if extra_json:
                try:
                    extras = json.loads(extra_json)
                except:
                    extras = {}
            render_card_visual(front, back, extras=extras, show_back=True)
            if st.button("Done"):
                st.session_state.view_card_id = None
                st.session_state.view_show_answer = False
            return
        else:
            # Card not found or removed
            st.session_state.view_card_id = None
            st.session_state.view_show_answer = False

    # Normal form for adding or editing
    if st.session_state.get("selected_card_id") is not None:
        editing = True
        card_to_edit = get_card_by_id(st.session_state.selected_card_id)
    else:
        editing = False
        card_to_edit = None

    render_card_form(deck_id, editing, card_to_edit)
    st.divider()

    # List all cards in this deck
    cards_data = get_cards(deck_id)
    if not cards_data:
        st.info("No cards to display.")
        return

    center_cols = st.columns([1, 6])
    with center_cols[1]:
        header_cols = st.columns([1, 2, 1, 1, 1, 1])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Front**")

        for card_id, front, back in cards_data:
            row_cols = st.columns([1, 2, 1, 1, 1, 1])
            row_cols[0].write(card_id)
            row_cols[1].write(front)

            # View
            if row_cols[2].button("View", key=f"view_{card_id}"):
                if st.session_state.view_card_id == card_id:
                    st.session_state.view_card_id = None
                    st.session_state.view_show_answer = False
                else:
                    st.session_state.view_card_id = card_id
                    st.session_state.view_show_answer = False
                st.rerun()

            # Edit
            if row_cols[3].button("Edit", key=f"select_{card_id}"):
                st.session_state.selected_card_id = card_id
                st.rerun()

            # Stats
            if row_cols[4].button("Stats", key=f"stats_{card_id}"):
                if st.session_state.get("selected_stats_card_id") == card_id:
                    st.session_state.selected_stats_card_id = None
                else:
                    st.session_state.selected_stats_card_id = card_id
                st.rerun()

            # Delete
            if row_cols[5].button("Delete", key=f"delete_{card_id}"):
                delete_card(card_id)
                st.success("Card deleted!")
                st.rerun()

            # Show expanded stats if selected
            if st.session_state.get("selected_stats_card_id") == card_id:
                card_full = get_card_by_id(card_id)
                if card_full:
                    _, _, _, _, next_review, interval, repetition, ef, _ = card_full
                    if next_review:
                        nr_display = datetime.fromisoformat(next_review).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        nr_display = "Not scheduled"
                    st.markdown(
                        f"<div style='margin-left: 40px;'>"
                        f"<strong>Next Review:</strong> {nr_display}<br>"
                        f"<strong>Interval:</strong> {interval} day(s)<br>"
                        f"<strong>Repetition:</strong> {repetition}<br>"
                        f"<strong>Ease Factor:</strong> {ef:.2f}"
                        f"</div><br>",
                        unsafe_allow_html=True
                    )


def go_to_next_card(deck_id):
    cards_data = get_cards(deck_id)
    if not cards_data:
        return
    current_card_id = st.session_state.review_card_id
    card_ids = [c[0] for c in cards_data]
    if current_card_id in card_ids:
        index = card_ids.index(current_card_id)
        next_index = (index + 1) % len(card_ids)
        st.session_state.review_card_id = card_ids[next_index]
        st.session_state.review_show_answer = False
        st.session_state.review_edit_mode = False


def render_deck_review(deck_id):
    from utils.flashcards_db import c
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("This deck does not exist.")
        st.session_state.selected_deck_id = None
        st.stop()

    deck_name = row[0]

    top_row = st.columns([2, 8])
    if top_row[0].button("Back"):
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
        st.info("No cards to review in this deck.")
        return

    if st.session_state.review_card_id is None and cards_data:
        st.session_state.review_card_id = cards_data[0][0]

    card = get_card_by_id(st.session_state.review_card_id)
    if not card:
        st.error("Selected card not found.")
        return

    card_id, _, front, back, next_review, interval, repetition, ef, extra_json = card

    # Inline editing of a card during review
    if st.session_state.review_edit_mode:
        with st.form("edit_review_form", clear_on_submit=False):
            new_front = st.text_area("Edit Front", value=front)
            new_back = st.text_area("Edit Back", value=back)
            col1, col2 = st.columns(2)
            if col2.form_submit_button("Save"):
                if new_front.strip() and new_back.strip():
                    update_card(card_id, new_front.strip(), new_back.strip())
                    st.success("Card updated!")
                    st.session_state.review_edit_mode = False
                    st.rerun()
                else:
                    st.error("Both front and back must have content.")
            if col1.form_submit_button("Cancel"):
                st.session_state.review_edit_mode = False
                st.rerun()
        return

    # Otherwise, show card
    extras = {}
    if extra_json:
        try:
            extras = json.loads(extra_json)
        except:
            extras = {}

    render_card_visual(front, back, extras=extras, show_back=st.session_state.review_show_answer)

    st.divider()
    if not st.session_state.review_show_answer:
        if st.button("Show Answer"):
            st.session_state.review_show_answer = True
            st.rerun()
    else:
        proj_again = format_interval_short(project_interval(card, 0))
        proj_hard  = format_interval_short(project_interval(card, 3))
        proj_good  = format_interval_short(project_interval(card, 4))
        proj_easy  = format_interval_short(project_interval(card, 5))

        header_cols = st.columns([2, 1, 1, 1, 1])
        header_cols[1].markdown(proj_again)
        header_cols[2].markdown(proj_hard)
        header_cols[3].markdown(proj_good)
        header_cols[4].markdown(proj_easy)

        btn_cols = st.columns([2, 1, 1, 1, 1])
        # Inline edit
        if btn_cols[0].button("Edit", key="edit_card"):
            st.session_state.review_edit_mode = True
            st.rerun()

        with btn_cols[1]:
            if st.button("Again", key="again"):
                update_sm2(card_id, 0)
                go_to_next_card(deck_id)
                st.rerun()
        with btn_cols[2]:
            if st.button("Hard", key="hard"):
                update_sm2(card_id, 3)
                go_to_next_card(deck_id)
                st.rerun()
        with btn_cols[3]:
            if st.button("Good", key="good"):
                update_sm2(card_id, 4)
                go_to_next_card(deck_id)
                st.rerun()
        with btn_cols[4]:
            if st.button("Easy", key="easy"):
                update_sm2(card_id, 5)
                go_to_next_card(deck_id)
                st.rerun()
