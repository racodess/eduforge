# flashcards_db.py

"""
SQLite-based persistence for flashcard decks and cards.
Provides initialization, schema migrations, and CRUD operations,
plus utilities for resetting schedules and gathering statistics for spaced repetition.
"""

import sqlite3
import os
from datetime import datetime

# Define database file path in current working directory
DB_PATH = os.path.join(os.getcwd(), "flashcards.db")

# Establish a SQLite connection and cursor for global use
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()


def init_db() -> None:
    """
    Create decks and cards tables if they do not exist.
    Ensures a fresh database schema for storing flashcard data.
    """
    # Create a table for decks with unique names
    c.execute('''
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    # Create a table for cards, including scheduling metadata for SM-2
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

    # Persist schema changes
    conn.commit()


def update_db_schema() -> None:
    """
    Add missing columns to the cards table for SM-2 fields.
    Useful when upgrading an existing database schema.
    """
    # Inspect existing columns in the cards table
    c.execute("PRAGMA table_info(cards)")
    columns = [info[1] for info in c.fetchall()]

    # Conditionally apply ALTER TABLE statements
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

    # Commit any schema updates
    conn.commit()


def reset_deck(deck_id: int) -> None:
    """
    Reset all scheduling data for a given deck.
    Sets next_review to NULL and resets SM-2 fields to defaults.
    """
    c.execute(
        """
        UPDATE cards
           SET next_review = NULL,
               interval     = 0,
               repetition   = 0,
               ef           = 2.5
         WHERE deck_id = ?
        """,
        (deck_id,)
    )
    conn.commit()


def get_decks() -> list[tuple[int, str]]:
    """
    Retrieve all decks as a list of (id, name) tuples.
    """
    c.execute("SELECT id, name FROM decks")
    return c.fetchall()


def create_deck(deck_name: str) -> None:
    """
    Insert a new deck into the database.
    Displays a success or error message via Streamlit on failure.
    """
    import streamlit as st
    try:
        c.execute("INSERT INTO decks (name) VALUES (?)", (deck_name,))
        conn.commit()
        st.success(f"Deck '{deck_name}' created!")
    except sqlite3.IntegrityError:
        # Unique constraint violation if name already exists
        st.error("A deck with that name already exists!")


def rename_deck(deck_id: int, new_name: str) -> None:
    """
    Change the name of an existing deck identified by deck_id.
    """
    c.execute(
        "UPDATE decks SET name = ? WHERE id = ?", (new_name, deck_id)
    )
    conn.commit()


def get_cards(deck_id: int) -> list[tuple[int, str, str]]:
    """
    Fetch all cards for a given deck as (id, front, back) tuples.
    """
    c.execute(
        "SELECT id, front, back FROM cards WHERE deck_id = ?", (deck_id,)
    )
    return c.fetchall()


def get_card_by_id(card_id: int) -> tuple | None:
    """
    Retrieve full card data by its ID, including SM-2 fields and extras.
    Returns a tuple or None if not found.
    """
    c.execute(
        "SELECT id, deck_id, front, back, next_review, interval, repetition, ef, extra_fields"
        " FROM cards WHERE id = ?", (card_id,)
    )
    return c.fetchone()


def add_card(
    deck_id: int,
    front: str,
    back: str,
    extra_fields: dict | None = None
) -> None:
    """
    Insert a new card into a deck, initializing SM-2 metadata.
    extra_fields can hold JSON-serializable additional data.
    """
    import json

    # Serialize extra_fields dict to JSON or use None
    extra_fields_json = json.dumps(extra_fields) if extra_fields else None
    c.execute(
        """
        INSERT INTO cards
            (deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (deck_id, front, back, None, 0, 0, 2.5, extra_fields_json)
    )
    conn.commit()


def delete_card(card_id: int) -> None:
    """
    Permanently remove a card from the database by its ID.
    """
    c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()


def update_card(
    card_id: int,
    front: str,
    back: str,
    extra_fields: dict | None = None
) -> None:
    """
    Update front, back, and extra_fields of an existing card.
    """
    import json
    extra_fields_json = json.dumps(extra_fields) if extra_fields else None
    c.execute(
        """
        UPDATE cards
           SET front = ?, back = ?, extra_fields = ?
         WHERE id = ?
        """,
        (front, back, extra_fields_json, card_id)
    )
    conn.commit()


def trash_deck(deck_id: int) -> None:
    """
    Delete a deck and all its associated cards permanently.
    """
    c.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    c.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
    conn.commit()


def get_deck_stats(deck_id: int) -> dict[str, int]:
    """
    Compute new, learn, and due counts for a deck to drive dashboard metrics.

    - new: cards never reviewed (repetition = 0 or next_review IS NULL)
    - due: cards with next_review <= now
    - learn: cards with next_review > now

    Returns a dict with keys 'new', 'learn', 'due'.
    """
    now_str = datetime.now().isoformat()

    # Count new cards
    c.execute(
        "SELECT COUNT(*) FROM cards"
        " WHERE deck_id = ? AND (repetition = 0 OR next_review IS NULL)",
        (deck_id,)
    )
    new = c.fetchone()[0]

    # Count due cards
    c.execute(
        "SELECT COUNT(*) FROM cards"
        " WHERE deck_id = ? AND next_review IS NOT NULL AND next_review <= ?",
        (deck_id, now_str)
    )
    due = c.fetchone()[0]
    
    # Count cards in learning phase
    c.execute(
        "SELECT COUNT(*) FROM cards"
        " WHERE deck_id = ? AND next_review IS NOT NULL AND next_review > ?",
        (deck_id, now_str)
    )
    learn = c.fetchone()[0]
    return {"new": new, "learn": learn, "due": due}
