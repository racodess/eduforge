import streamlit as st
import sqlite3
import os
import json
import time  # For delaying review feedback (no longer used for SM‑2 buttons)
from datetime import datetime, timedelta

# ------------- Database Setup -------------
DB_PATH = os.path.join(os.getcwd(), "flashcards.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    # Updated cards table with SM-2 fields
    c.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER,
            front TEXT,
            back TEXT,
            next_review TIMESTAMP,
            interval REAL,
            repetition INTEGER,
            ef REAL,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        )
    ''')
    conn.commit()

init_db()

# Optional: Update database schema if columns are missing
def update_db_schema():
    c.execute("PRAGMA table_info(cards)")
    columns = [info[1] for info in c.fetchall()]
    
    if "next_review" not in columns:
        c.execute("ALTER TABLE cards ADD COLUMN next_review TIMESTAMP")
    if "interval" not in columns:
        c.execute("ALTER TABLE cards ADD COLUMN interval REAL DEFAULT 0")
    if "repetition" not in columns:
        c.execute("ALTER TABLE cards ADD COLUMN repetition INTEGER DEFAULT 0")
    if "ef" not in columns:
        c.execute("ALTER TABLE cards ADD COLUMN ef REAL DEFAULT 2.5")
    
    conn.commit()

update_db_schema()

# New helper: Reset all SM‑2 values for cards in a deck.
def reset_deck(deck_id):
    c.execute(
        "UPDATE cards SET next_review = NULL, interval = 0, repetition = 0, ef = 2.5 WHERE deck_id = ?",
        (deck_id,)
    )
    conn.commit()

# ------------- Helper Functions -------------

def get_decks():
    c.execute("SELECT id, name FROM decks")
    return c.fetchall()

def create_deck(deck_name):
    try:
        c.execute("INSERT INTO decks (name) VALUES (?)", (deck_name,))
        conn.commit()
        st.success(f"Deck '{deck_name}' created!")
    except sqlite3.IntegrityError:
        st.error("A deck with that name already exists!")

def get_cards(deck_id):
    c.execute("SELECT id, front, back FROM cards WHERE deck_id = ?", (deck_id,))
    return c.fetchall()

def get_card_by_id(card_id):
    c.execute("SELECT id, deck_id, front, back, next_review, interval, repetition, ef FROM cards WHERE id = ?", (card_id,))
    return c.fetchone()

# New card additions include initial SM‑2 values.
def add_card(deck_id, front, back):
    c.execute("INSERT INTO cards (deck_id, front, back, next_review, interval, repetition, ef) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (deck_id, front, back, None, 0, 0, 2.5))
    conn.commit()

def delete_card(card_id):
    c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()

def update_card(card_id, front, back):
    c.execute("UPDATE cards SET front = ?, back = ? WHERE id = ?", (front, back, card_id))
    conn.commit()

def trash_deck(deck_id):
    c.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    c.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
    conn.commit()

def get_deck_stats(deck_id):
    now_str = datetime.now().isoformat()
    c.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND (repetition = 0 OR next_review IS NULL)", (deck_id,))
    new = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND next_review IS NOT NULL AND next_review <= ?", (deck_id, now_str))
    due = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND next_review IS NOT NULL AND next_review > ?", (deck_id, now_str))
    learn = c.fetchone()[0]
    return {"new": new, "learn": learn, "due": due}

def format_timedelta(delta):
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minutes"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hours"
    days = hours // 24
    return f"{days} days"

# ------------- SM‑2 Functions -------------

# The updated SM‑2 function applies different multipliers based on quality.
# For new cards (repetition == 0), we use learning steps:
#   - Hard: 6 minutes, Good: 10 minutes, Easy: 2 days.
# For subsequent reviews, we use multipliers:
#   - Hard: base * ef * 0.9, Good: base * ef, Easy: base * ef * 1.3.
def update_sm2(card_id, quality):
    """
    quality: integer rating
      - "Again" = 0, "Hard" = 3, "Good" = 4, "Easy" = 5.
    """
    now = datetime.now()
    card = get_card_by_id(card_id)
    if not card:
        return None, None, None, None
    # card: (id, deck_id, front, back, next_review, interval, repetition, ef)
    interval = card[5] if card[5] is not None else 0
    repetition = card[6] if card[6] is not None else 0
    ef = card[7] if card[7] is not None else 2.5

    if quality < 3:
        # Failed review: count as a review attempt.
        # If the card is new (repetition == 0), mark it as reviewed by setting repetition to 1.
        if repetition == 0:
            repetition = 1
        else:
            repetition = 1  # Always set to 1 on a failed review to count it as reviewed.
        interval = 1 / 1440  # 1 minute (in days)
        next_review = now + timedelta(minutes=1)
    else:
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if new_ef < 1.3:
            new_ef = 1.3
        ef = new_ef
        if repetition == 0:
            # New card: use learning step intervals.
            repetition = 1
            if quality == 3:
                interval = 6 / 1440  # 6 minutes
                next_review = now + timedelta(minutes=6)
            elif quality == 4:
                interval = 10 / 1440  # 10 minutes
                next_review = now + timedelta(minutes=10)
            elif quality == 5:
                interval = 2  # 2 days
                next_review = now + timedelta(days=2)
        else:
            repetition += 1
            base = interval if interval >= 1 else 1
            if quality == 3:
                interval = round(base * ef * 0.9)
            elif quality == 4:
                interval = round(base * ef)
            elif quality == 5:
                interval = round(base * ef * 1.3)
            next_review = now + timedelta(days=interval)

    next_review_str = next_review.isoformat()
    c.execute("UPDATE cards SET next_review = ?, interval = ?, repetition = ?, ef = ? WHERE id = ?",
              (next_review_str, interval, repetition, ef, card_id))
    conn.commit()
    return next_review, interval, repetition, ef

# Helper: Project what the next interval would be without updating the DB.
def project_interval(card, quality):
    now = datetime.now()
    interval = card[5] if card[5] is not None else 0
    repetition = card[6] if card[6] is not None else 0
    ef = card[7] if card[7] is not None else 2.5

    if quality < 3:
        return timedelta(minutes=1)
    else:
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if new_ef < 1.3:
            new_ef = 1.3
        if repetition == 0:
            if quality == 3:
                return timedelta(minutes=6)
            elif quality == 4:
                return timedelta(minutes=10)
            elif quality == 5:
                return timedelta(days=2)
        else:
            base = interval if interval >= 1 else 1
            if quality == 3:
                new_interval = round(base * new_ef * 0.9)
            elif quality == 4:
                new_interval = round(base * new_ef)
            elif quality == 5:
                new_interval = round(base * new_ef * 1.3)
            return timedelta(days=new_interval)

# Helper: Format a timedelta into a short string (e.g. "<6m" or "<2d").
def format_interval_short(td):
    total_minutes = td.total_seconds() / 60
    if total_minutes < 60:
        minutes = int(total_minutes)
        if minutes < 1:
            minutes = 1
        return f"<{minutes}m"
    elif total_minutes < 1440:
        hours = total_minutes / 60
        return f"<{round(hours)}h"
    else:
        return f"<{td.days}d"

# ------------- Session State Setup -------------
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

# ------------- Deck List View -------------
def render_deck_list():
    decks = get_decks()
    if decks:
        header_cols = st.columns([2, 1, 1, 1, 6])
        header_cols[0].markdown("**Deck**")
        header_cols[1].markdown("**New**")
        header_cols[2].markdown("**Learn**")
        header_cols[3].markdown("**Due**")
        
        for deck_id, deck_name in decks:
            with st.container():
                row_cols = st.columns([2, 1, 1, 1, 6])
                row_cols[0].write(deck_name)
                stats = get_deck_stats(deck_id)
                row_cols[1].write(stats["new"])
                row_cols[2].write(stats["learn"])
                row_cols[3].write(stats["due"])
                
                with row_cols[4]:
                    action_cols = st.columns(4)
                    if action_cols[0].button("Review", key=f"review_deck_{deck_id}"):
                        st.session_state.selected_deck_id = deck_id
                        st.session_state.selected_deck_mode = "review"
                        st.session_state.review_card_id = None
                        st.session_state.review_show_answer = False
                        st.session_state.review_edit_mode = False
                        st.rerun()
                    if action_cols[1].button("Browse", key=f"browse_deck_{deck_id}"):
                        st.session_state.selected_deck_id = deck_id
                        st.session_state.selected_deck_mode = "browse"
                        st.rerun()
                    cards_data = get_cards(deck_id)
                    deck_data = {
                        "name": deck_name,
                        "cards": [{"front": card[1], "back": card[2]} for card in cards_data]
                    }
                    deck_json = json.dumps(deck_data, indent=2)
                    action_cols[2].download_button(
                        "Export", deck_json,
                        file_name=f"{deck_name}.json",
                        mime="application/json",
                        key=f"export_deck_{deck_id}"
                    )
                    if action_cols[3].button("Delete", key=f"delete_deck_{deck_id}"):
                        st.session_state.deck_pending_delete = deck_id
                        st.rerun()
                        
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
                    try:
                        c.execute("INSERT INTO decks (name) VALUES (?)", (imported_deck_name,))
                        conn.commit()
                        new_deck_id = c.lastrowid
                        for card in cards_list:
                            front = card.get("front", "")
                            back = card.get("back", "")
                            c.execute("INSERT INTO cards (deck_id, front, back, next_review, interval, repetition, ef) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                      (new_deck_id, front, back, None, 0, 0, 2.5))
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

# ------------- Deck Detail (Browse) View -------------
def render_deck_detail(deck_id):
    c.execute("SELECT name FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    if not row:
        st.error("This deck does not exist.")
        st.session_state.selected_deck_id = None
        st.stop()
    deck_name = row[0]
    top_row = st.columns([2, 8, 2])
    if top_row[0].button("Back"):
        st.session_state.selected_deck_id = None
        st.session_state.selected_deck_mode = None
        st.rerun()
    top_row[1].markdown(f"<h2 style='text-align:left;'>{deck_name}</h2>", unsafe_allow_html=True)
    if top_row[2].button("Reset Deck"):
        st.session_state.deck_pending_reset = deck_id
        st.rerun()
    if st.session_state.deck_pending_reset == deck_id:
        st.info("Are you sure you want to permanently reset the SM‑2 stats (New, Learn, Due) for this deck?")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("Yes", key=f"confirm_reset_yes_{deck_id}"):
            reset_deck(deck_id)
            st.success("Deck reset successfully!")
            st.session_state.deck_pending_reset = None
            st.rerun()
        if confirm_cols[1].button("No", key=f"confirm_reset_no_{deck_id}"):
            st.session_state.deck_pending_reset = None
            st.rerun()

    if st.session_state.get("selected_card_id") is not None:
        editing = True
        card_to_edit = get_card_by_id(st.session_state.selected_card_id)
        if card_to_edit:
            pre_front = card_to_edit[2]
            pre_back = card_to_edit[3]
        else:
            pre_front = ""
            pre_back = ""
    else:
        editing = False
        pre_front = ""
        pre_back = ""

    with st.form("add_card_form", clear_on_submit=True):
        front_text = st.text_area("Front", value=pre_front, placeholder="Enter question or prompt here")
        back_text = st.text_area("Back", value=pre_back, placeholder="Enter answer or explanation here")
        _, submit_btn_col = st.columns([3, 1])
        if editing:
            submitted = submit_btn_col.form_submit_button("Update Card")
        else:
            submitted = submit_btn_col.form_submit_button("Add Card")
        if submitted:
            if front_text.strip() and back_text.strip():
                if editing:
                    update_card(st.session_state.selected_card_id, front_text.strip(), back_text.strip())
                    st.success("Flashcard updated!")
                    st.session_state.selected_card_id = None
                    st.rerun()
                else:
                    add_card(deck_id, front_text.strip(), back_text.strip())
                    st.success("Flashcard added!")
                    st.rerun()
            else:
                st.error("Please provide both front and back text.")

    st.divider()

    cards_data = get_cards(deck_id)
    if not cards_data:
        st.info("No cards to display.")
        return
    center_cols = st.columns([1, 6])
    with center_cols[1]:
        header_cols = st.columns([1, 2, 1, 1, 1])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Front**")
        for card in cards_data:
            card_id, front, back = card
            row_cols = st.columns([1, 2, 1, 1, 1])
            row_cols[0].write(card_id)
            row_cols[1].write(front)
            if row_cols[2].button("Edit", key=f"select_{card_id}"):
                st.session_state.selected_card_id = card_id
                st.rerun()
            if row_cols[3].button("Stats" if st.session_state.get("selected_stats_card_id") == card_id else "Stats",
                                  key=f"stats_{card_id}"):
                if st.session_state.get("selected_stats_card_id") == card_id:
                    st.session_state.selected_stats_card_id = None
                else:
                    st.session_state.selected_stats_card_id = card_id
                st.rerun()
            if row_cols[4].button("Delete", key=f"delete_{card_id}"):
                delete_card(card_id)
                st.success("Card deleted!")
                st.rerun()
            if st.session_state.get("selected_stats_card_id") == card_id:
                card_full = get_card_by_id(card_id)
                if card_full:
                    _, _, _, _, next_review, interval, repetition, ef = card_full
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
                        f"</div>"
                        f"<br>",
                        unsafe_allow_html=True
                    )

# ------------- Deck Review View -------------
def render_deck_review(deck_id):
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
    
    # If there are no due or new cards, show congratulations.
    if stats["new"] == 0 and stats["due"] == 0:
        st.success("Congratulations! You have completed your review.")
        return

    st.divider()
    
    cards_data = get_cards(deck_id)
    if not cards_data:
        st.info("No cards to review in this deck.")
        return
    
    if st.session_state.review_card_id is None:
        st.session_state.review_card_id = cards_data[0][0]
    
    card = get_card_by_id(st.session_state.review_card_id)
    if not card:
        st.error("Selected card not found.")
        return
    card_id, _, front, back, next_review, interval, repetition, ef = card

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

    st.subheader("Front")
    st.write(front)
    st.divider()
    
    if not st.session_state.review_show_answer:
        if st.button("Show Answer"):
            st.session_state.review_show_answer = True
            st.rerun()
    else:
        st.subheader("Back")
        st.write(back)
        st.divider()
        
        # Calculate projected intervals for each SM‑2 rating.
        proj_again = format_interval_short(project_interval(card, 0))
        proj_hard  = format_interval_short(project_interval(card, 3))
        proj_good  = format_interval_short(project_interval(card, 4))
        proj_easy  = format_interval_short(project_interval(card, 5))
        
        # Create header row for projected intervals so the Edit button is aligned.
        header_cols = st.columns([2, 1, 1, 1, 1])
        # No header for Edit, but for the others we display the projected intervals.
        header_cols[1].markdown(proj_again, unsafe_allow_html=True)
        header_cols[2].markdown(proj_hard, unsafe_allow_html=True)
        header_cols[3].markdown(proj_good, unsafe_allow_html=True)
        header_cols[4].markdown(proj_easy, unsafe_allow_html=True)
        
        # Create a row of buttons with the Edit button on the same row.
        btn_cols = st.columns([2, 1, 1, 1, 1])
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

# New helper: Move to the next card in the deck.
def go_to_next_card(deck_id):
    cards_data = get_cards(deck_id)
    if not cards_data:
        return
    current_card_id = st.session_state.review_card_id
    card_ids = [card[0] for card in cards_data]
    if current_card_id in card_ids:
        index = card_ids.index(current_card_id)
        next_index = (index + 1) % len(card_ids)
        st.session_state.review_card_id = card_ids[next_index]
        st.session_state.review_show_answer = False
        st.session_state.review_edit_mode = False

# ------------- Page Logic -------------
if st.session_state.selected_deck_id is None:
    render_deck_list()
else:
    if st.session_state.selected_deck_mode == "browse":
        render_deck_detail(st.session_state.selected_deck_id)
    elif st.session_state.selected_deck_mode == "review":
        render_deck_review(st.session_state.selected_deck_id)
