# flashcards_db.py

import sqlite3
import os
from datetime import datetime

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
            extra_fields TEXT,
            FOREIGN KEY(deck_id) REFERENCES decks(id)
        )
    ''')
    conn.commit()

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
    if "extra_fields" not in columns:
        c.execute("ALTER TABLE cards ADD COLUMN extra_fields TEXT")
    
    conn.commit()

def reset_deck(deck_id):
    c.execute(
        "UPDATE cards SET next_review = NULL, interval = 0, repetition = 0, ef = 2.5 WHERE deck_id = ?",
        (deck_id,)
    )
    conn.commit()

def get_decks():
    c.execute("SELECT id, name FROM decks")
    return c.fetchall()

def create_deck(deck_name):
    import streamlit as st
    try:
        c.execute("INSERT INTO decks (name) VALUES (?)", (deck_name,))
        conn.commit()
        st.success(f"Deck '{deck_name}' created!")
    except sqlite3.IntegrityError:
        st.error("A deck with that name already exists!")

def rename_deck(deck_id: int, new_name: str) -> None:
    """
    Change the name of an existing deck.
    """
    c.execute("UPDATE decks SET name = ? WHERE id = ?", (new_name, deck_id))
    conn.commit()

def get_cards(deck_id):
    c.execute("SELECT id, front, back FROM cards WHERE deck_id = ?", (deck_id,))
    return c.fetchall()

def get_card_by_id(card_id):
    c.execute("SELECT id, deck_id, front, back, next_review, interval, repetition, ef, extra_fields FROM cards WHERE id = ?", (card_id,))
    return c.fetchone()

def add_card(deck_id, front, back, extra_fields=None):
    import json
    extra_fields_json = json.dumps(extra_fields) if extra_fields else None
    c.execute("""
        INSERT INTO cards (deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (deck_id, front, back, None, 0, 0, 2.5, extra_fields_json))
    conn.commit()

def delete_card(card_id):
    c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()

def update_card(card_id, front, back, extra_fields=None):
    import json
    extra_fields_json = json.dumps(extra_fields) if extra_fields else None
    c.execute("""
        UPDATE cards
        SET front = ?, back = ?, extra_fields = ?
        WHERE id = ?
    """, (front, back, extra_fields_json, card_id))
    conn.commit()

def trash_deck(deck_id):
    c.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    c.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
    conn.commit()

def get_deck_stats(deck_id):
    now_str = datetime.now().isoformat()
    # new
    c.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND (repetition = 0 OR next_review IS NULL)", (deck_id,))
    new = c.fetchone()[0]
    # due
    c.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND next_review IS NOT NULL AND next_review <= ?", (deck_id, now_str))
    due = c.fetchone()[0]
    # learn
    c.execute("SELECT COUNT(*) FROM cards WHERE deck_id = ? AND next_review IS NOT NULL AND next_review > ?", (deck_id, now_str))
    learn = c.fetchone()[0]
    return {"new": new, "learn": learn, "due": due}
