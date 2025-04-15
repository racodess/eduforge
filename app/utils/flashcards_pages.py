import json
from datetime import datetime
import streamlit as st

from utils.flashcards_db import (
    get_decks, create_deck, trash_deck, reset_deck, get_deck_stats,
    get_cards, get_card_by_id, delete_card, update_card, add_card
)
from utils.flashcards_sm2 import update_sm2, project_interval, format_interval_short
from utils.flashcards_ui import render_card_visual, render_card_form
from utils.file_helper import FileHelper

def render_deck_row(deck_id, deck_name, stats):
    row_cols = st.columns([2, 1, 1, 1, 6])
    row_cols[0].write(deck_name)
    row_cols[1].write(stats["new"])
    row_cols[2].write(stats["learn"])
    row_cols[3].write(stats["due"])

    with row_cols[4]:
        action_cols = st.columns(4)
        # Review
        if action_cols[0].button("Review", key=f"review_deck_{deck_id}", use_container_width=True):
            st.session_state.selected_deck_id = deck_id
            st.session_state.selected_deck_mode = "review"
            st.session_state.review_card_id = None
            st.session_state.review_show_answer = False
            st.session_state.review_edit_mode = False
            st.rerun()

        # Browse
        if action_cols[1].button("Browse", key=f"browse_deck_{deck_id}", use_container_width=True):
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
            key=f"export_deck_{deck_id}",
            use_container_width=True
        )

        # Delete
        if action_cols[3].button("Delete", key=f"delete_deck_{deck_id}", use_container_width=True):
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
                if confirm_cols[0].button("Yes", key=f"confirm_delete_yes_{deck_id}", use_container_width=True):
                    trash_deck(deck_id)
                    st.success(f"Deck '{deck_name}' deleted!")
                    st.session_state.deck_pending_delete = None
                    st.rerun()
                if confirm_cols[1].button("No", key=f"confirm_delete_no_{deck_id}", use_container_width=True):
                    st.session_state.deck_pending_delete = None
                    st.rerun()
    else:
        st.info("No decks found. Create one below.")

    st.divider()
    new_deck_name = st.text_input("Create New Deck", "")
    if st.button("Create Deck", use_container_width=True):
        if new_deck_name.strip():
            create_deck(new_deck_name.strip())
            st.rerun()
        else:
            st.error("Please provide a valid deck name.")

    st.divider()
    imported_file = st.file_uploader("Import Deck", type=["json"], key="import_deck")
    if st.button("Import", use_container_width=True):
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

    st.divider()
    render_ai_import_section(st.session_state.selected_deck_id)

def render_edit_fields(deck_id):
    st.markdown("### Edit Card Fields")
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
            if col2.button("Delete", key=f"delete_field_{deck_id}_{i}", use_container_width=True):
                st.session_state.deck_fields[deck_id].pop(i)
                st.rerun()

    new_field = st.text_input("New Field Name", key=f"new_field_input_{deck_id}")
    if st.button("Add Field", key=f"add_field_button_{deck_id}", use_container_width=True):
        if new_field and new_field not in st.session_state.deck_fields[deck_id]:
            st.session_state.deck_fields[deck_id].append(new_field)
            st.rerun()

    if st.button("Done Editing Fields", key=f"done_edit_fields_{deck_id}", use_container_width=True):
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

    if top_row[0].button("Back", use_container_width=True):
        st.session_state.selected_deck_id = None
        st.session_state.selected_deck_mode = None
        st.rerun()

    top_row[1].markdown(f"<h2 style='text-align:left;'>{deck_name}</h2>", unsafe_allow_html=True)

    if top_row[2].button("Reset Deck", use_container_width=True):
        st.session_state.deck_pending_reset = deck_id
        st.rerun()

    if st.session_state.deck_pending_reset == deck_id:
        st.info("Are you sure you want to permanently reset the SM‑2 stats for this deck?")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("Yes", key=f"confirm_reset_yes_{deck_id}", use_container_width=True):
            reset_deck(deck_id)
            st.success("Deck reset successfully!")
            st.session_state.deck_pending_reset = None
            st.rerun()
        if confirm_cols[1].button("No", key=f"confirm_reset_no_{deck_id}", use_container_width=True):
            st.session_state.deck_pending_reset = None
            st.rerun()

    if deck_id not in st.session_state.deck_fields:
        st.session_state.deck_fields[deck_id] = ["Front", "Back"]

    if st.session_state.get("edit_fields", False):
        render_edit_fields(deck_id)
        return

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
            if st.button("Done", use_container_width=True):
                st.session_state.view_card_id = None
                st.session_state.view_show_answer = False
            return
        else:
            st.session_state.view_card_id = None
            st.session_state.view_show_answer = False

    if st.session_state.get("selected_card_id") is not None:
        editing = True
        card_to_edit = get_card_by_id(st.session_state.selected_card_id)
    else:
        editing = False
        card_to_edit = None

    render_card_form(deck_id, editing, card_to_edit)
    st.divider()

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
            if row_cols[2].button("View", key=f"view_{card_id}", use_container_width=True):
                if st.session_state.view_card_id == card_id:
                    st.session_state.view_card_id = None
                    st.session_state.view_show_answer = False
                else:
                    st.session_state.view_card_id = card_id
                    st.session_state.view_show_answer = False
                st.rerun()
            if row_cols[3].button("Edit", key=f"select_{card_id}", use_container_width=True):
                st.session_state.selected_card_id = card_id
                st.rerun()
            if row_cols[4].button("Stats", key=f"stats_{card_id}", use_container_width=True):
                if st.session_state.get("selected_stats_card_id") == card_id:
                    st.session_state.selected_stats_card_id = None
                else:
                    st.session_state.selected_stats_card_id = card_id
                st.rerun()
            if row_cols[5].button("Delete", key=f"delete_{card_id}", use_container_width=True):
                delete_card(card_id)
                st.success("Card deleted!")
                st.rerun()

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
    if top_row[0].button("Back", use_container_width=True):
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

    if st.session_state.review_edit_mode:
        with st.form("edit_review_form", clear_on_submit=False):
            new_front = st.text_area("Edit Front", value=front)
            new_back = st.text_area("Edit Back", value=back)
            col1, col2 = st.columns(2)
            if col2.form_submit_button("Save", use_container_width=True):
                if new_front.strip() and new_back.strip():
                    update_card(card_id, new_front.strip(), new_back.strip())
                    st.success("Card updated!")
                    st.session_state.review_edit_mode = False
                    st.rerun()
                else:
                    st.error("Both front and back must have content.")
            if col1.form_submit_button("Cancel", use_container_width=True):
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
        if st.button("Show Answer", use_container_width=True):
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
        if btn_cols[0].button("Edit", key="edit_card", use_container_width=True):
            st.session_state.review_edit_mode = True
            st.rerun()
        with btn_cols[1]:
            if st.button("Again", key="again", use_container_width=True):
                update_sm2(card_id, 0)
                go_to_next_card(deck_id)
                st.rerun()
        with btn_cols[2]:
            if st.button("Hard", key="hard", use_container_width=True):
                update_sm2(card_id, 3)
                go_to_next_card(deck_id)
                st.rerun()
        with btn_cols[3]:
            if st.button("Good", key="good", use_container_width=True):
                update_sm2(card_id, 4)
                go_to_next_card(deck_id)
                st.rerun()
        with btn_cols[4]:
            if st.button("Easy", key="easy", use_container_width=True):
                update_sm2(card_id, 5)
                go_to_next_card(deck_id)
                st.rerun()

def render_ai_import_section(deck_id: int):
    """
    Adds a section where the user can upload a file, paste text, or provide a URL
    for generating new flashcards with AI. Also displays generated flashcards with
    options to add, delete, or regenerate them individually, as well as add all or delete all.
    """
    import json
    from utils.flashcards_db import add_card, get_decks
    from utils.model_schemas import FlashcardItem  # Import the Pydantic model
    from utils.file_helper import FileHelper

    st.markdown(
        f'<div style="text-align: center; font-size: 36px;"><strong>Generate</strong></div>',
        unsafe_allow_html=True
    )

    st.text("")      
    st.text("")

    # Initialize generated_cards in session state if not already set.
    if "generated_cards" not in st.session_state:
        st.session_state.generated_cards = []

    # Create an instance of our AI flashcard importer
    file_helper = FileHelper()

    # --- Deck Selection Dropdown ---
    available_decks = get_decks()
    if not available_decks:
        st.error("No decks available. Please create a deck first.")
        return
    deck_options = { deck_name: deck_id for deck_id, deck_name in available_decks }
    default_deck = None
    if st.session_state.get("selected_deck_id"):
        default_deck_id = st.session_state.selected_deck_id
        for name, did in deck_options.items():
            if did == default_deck_id:
                default_deck = name
                break
    if not default_deck:
        default_deck = list(deck_options.keys())[0]
    selected_deck_name = st.selectbox("Select Deck to Add Flashcards", options=list(deck_options.keys()), index=list(deck_options.keys()).index(default_deck))
    target_deck_id = deck_options[selected_deck_name]

    # 1) File uploader (supporting .txt, .pdf, and images)
    uploaded_file = st.file_uploader(
        label="Upload a .txt, .pdf, or image file",
        type=["txt", "pdf", "png", "jpg", "jpeg", "gif"],
        help="Provide a text file, PDF, or image with the content you want to convert into flashcards."
    )

    # PDF Page Range Form
    page_range = None
    if uploaded_file is not None and uploaded_file.name.lower().endswith('.pdf'):
        try:
            from PyPDF2 import PdfReader
            uploaded_file.seek(0)
            pdf_reader = PdfReader(uploaded_file)
            total_pages = len(pdf_reader.pages)
            uploaded_file.seek(0)
        except Exception as e:
            total_pages = 0
        col1, col2 = st.columns(2)
        start_page = col1.number_input("Start Page", min_value=1, max_value=total_pages if total_pages > 0 else 1, value=1, step=1)
        end_page = col2.number_input("End Page", min_value=1, max_value=total_pages if total_pages > 0 else 1, value=total_pages if total_pages > 0 else 1, step=1)
        page_range = (start_page, end_page)

    # 2) Text area for pasted content
    text_input = st.text_area(
        "Or paste text content here",
        "",
        help="You can directly paste your notes or content here."
    )

    # 3) URL input
    url_input = st.text_input(
        "Or provide a URL",
        "",
        help="If you want to pull text from a URL, enter it here."
    )

    if st.button("Generate Flashcards", use_container_width=True):
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
            st.warning("No valid content provided. Please upload a file, paste text, or enter a URL.")
        else:
            # Use the new pipeline method.
            generated_models = file_helper.generate_flashcards_pipeline(final_text)
            generated_cards = []
            # Each model returned from the pipeline can include multiple flashcards.
            for model_instance in generated_models:
                if hasattr(model_instance, "flashcards"):
                    generated_cards.extend(model_instance.flashcards)
            st.session_state.generated_cards = generated_cards
            if generated_cards:
                st.success(f"Generated {len(generated_cards)} flashcards!")
            else:
                st.info("No flashcards were generated.")

    # Display generated flashcards (if any)
    if st.session_state.get("generated_cards"):
        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown(
            "<h2 style='text-align: center;'>Generated Flashcards</h2>",
            unsafe_allow_html=True
        )

        # --- Move the Add All and Delete All buttons to the top ---
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

        # --- Render each flashcard inside its own centered box ---
        for i, card in enumerate(st.session_state.generated_cards):
            center_cols = st.columns([1, 6, 1])
            with center_cols[1]:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="text-align: left; font-size: 16px;"><strong>Flashcard {i+1}</strong></div>',
                        unsafe_allow_html=True
                    )
                    st.text("")
                    st.markdown(
                        '<div style="text-align: center;"><h3>Front</h3></div>',
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f'<div style="text-align: center;">{card.front}</div>',
                        unsafe_allow_html=True
                    )
                    st.text("")
                    st.text("")
                    st.markdown(
                        '<div style="text-align: center;"><h3>Back</h3></div>',
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f'<div style="text-align: center;">{card.back}</div>',
                        unsafe_allow_html=True
                    )
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
                            new_card = file_helper.regenerate_flashcard(card)
                            st.session_state.generated_cards[i] = new_card
                            st.rerun()
                    with btn_cols[3]:
                        if st.button("", key=f"gen_delete_{i}", type="tertiary", icon=":material/cancel:", use_container_width=True):
                            st.session_state.generated_cards.pop(i)
                            st.rerun()

def main():
    st.title("Flashcards")
    
    if st.session_state.selected_deck_id is None:
        render_deck_list()
    else:
        if st.session_state.selected_deck_mode == "browse":
            render_deck_detail(st.session_state.selected_deck_id)
        elif st.session_state.selected_deck_mode == "review":
            render_deck_review(st.session_state.selected_deck_id)

if __name__ == "__main__":
    main()
