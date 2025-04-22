# notes_db.py

"""
SQLite-backed persistence layer for notebooks and notes.
Defines initialization, schema migrations, and CRUD operations,
plus statistics aggregation for SM‑2 scheduling.
"""

import sqlite3
import os
import datetime

# Determine database path relative to current working directory
DB_PATH = os.path.join(os.getcwd(), "notes.db")

# Create a connection and cursor for global use
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Init & Schema Updates
def init_db() -> None:
    """
    Initialize the notebooks and notes tables if they don't exist,
    then apply any necessary schema updates for SM‑2 columns.
    """
    # Create notebooks table (id, unique name)
    c.execute(
        '''CREATE TABLE IF NOT EXISTS notebooks (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               name TEXT UNIQUE
           )'''
    )

    # Create notes table with fields for content and SM‑2 scheduling
    c.execute(
        '''CREATE TABLE IF NOT EXISTS notes (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               notebook_id INTEGER,
               tab_name     TEXT,
               content      TEXT,
               next_review  TEXT,     -- ISO timestamp or NULL
               interval     REAL,     -- days until next review
               repetition   INTEGER,  -- number of successful reviews
               ef           REAL,     -- easiness factor
               FOREIGN KEY (notebook_id) REFERENCES notebooks(id)
           )'''
    )
    # Commit table creation
    conn.commit()

    # Ensure SM‑2 columns exist on older databases
    _update_schema_if_needed()


def _update_schema_if_needed() -> None:
    """
    Inspect the notes table and add any missing SM‑2 columns.
    This handles migrations for existing databases.
    """
    # Retrieve current column names
    c.execute("PRAGMA table_info(notes)")
    existing_cols = {row[1] for row in c.fetchall()}

    # Prepare ALTER statements for missing columns
    alter_statements = []
    if "next_review" not in existing_cols:
        alter_statements.append("ADD COLUMN next_review TEXT")
    if "interval" not in existing_cols:
        alter_statements.append("ADD COLUMN interval REAL DEFAULT 0")
    if "repetition" not in existing_cols:
        alter_statements.append("ADD COLUMN repetition INTEGER DEFAULT 0")
    if "ef" not in existing_cols:
        alter_statements.append("ADD COLUMN ef REAL DEFAULT 2.5")

    # Apply each schema update
    for stmt in alter_statements:
        c.execute(f"ALTER TABLE notes {stmt}")
    if alter_statements:
        conn.commit()

# CRUD helpers
def get_notebooks() -> list[tuple[int, str]]:
    """
    Retrieve all notebooks as a list of (id, name) tuples.
    """
    c.execute("SELECT id, name FROM notebooks")
    return c.fetchall()


def create_notebook(name: str) -> int:
    """
    Create a new notebook with the given name and an initial default tab.

    Returns the new notebook's ID.
    """
    c.execute(
        "INSERT INTO notebooks (name) VALUES (?)", (name,)
    )
    conn.commit()
    nb_id = c.lastrowid

    # Create a default note/tab for the new notebook
    create_note(nb_id, "Default", "")
    return nb_id


def delete_notebook(nb_id: int) -> None:
    """
    Delete a notebook and all its associated notes.
    """
    c.execute(
        "DELETE FROM notes WHERE notebook_id = ?", (nb_id,)
    )
    c.execute(
        "DELETE FROM notebooks WHERE id = ?", (nb_id,)
    )
    conn.commit()


def rename_notebook(nb_id: int, new_name: str) -> None:
    """
    Rename an existing notebook.
    """
    c.execute(
        "UPDATE notebooks SET name = ? WHERE id = ?", (new_name, nb_id)
    )
    conn.commit()

# notes (compact rows, for browsing)
def get_notes(nb_id: int) -> list[tuple[int, str, str]]:
    """
    Retrieve basic note info for a notebook: (id, tab_name, content).
    Used for listing and simple UIs.
    """
    c.execute(
        "SELECT id, tab_name, content FROM notes WHERE notebook_id = ?", (nb_id,)
    )
    return c.fetchall()

# notes (full row, for SM‑2 / review)
def get_note_by_id(note_id: int) -> tuple | None:
    """
    Fetch a single note record by its ID.
    Returns all fields needed for review and editing.
    """
    c.execute(
        "SELECT * FROM notes WHERE id = ?", (note_id,)
    )
    return c.fetchone()


def get_notes_full(nb_id: int) -> list[tuple]:
    """
    Retrieve full note data including SM‑2 fields for review sessions.
    Returns tuples: (id, tab_name, content, next_review, interval, repetition, ef).
    """
    c.execute(
        """
        SELECT id, tab_name, content,
               next_review, interval, repetition, ef
        FROM notes WHERE notebook_id = ?
        """,
        (nb_id,)
    )
    return c.fetchall()


def create_note(nb_id: int, tab_name: str, content: str) -> int:
    """
    Insert a new note/tab into a notebook, initializing SM‑2 metadata.

    Returns the new note's ID.
    """
    c.execute(
        """
        INSERT INTO notes
            (notebook_id, tab_name, content,
             next_review, interval, repetition, ef)
        VALUES (?, ?, ?, NULL, 0, 0, 2.5)
        """,
        (nb_id, tab_name, content)
    )
    conn.commit()
    return c.lastrowid


def update_note(note_id: int, content: str) -> None:
    """
    Update the content field of an existing note.
    """
    c.execute(
        "UPDATE notes SET content = ? WHERE id = ?", (content, note_id)
    )
    conn.commit()


def rename_note(note_id: int, new_tab_name: str) -> None:
    """
    Rename the tab_name of a note.
    """
    c.execute(
        "UPDATE notes SET tab_name = ? WHERE id = ?", (new_tab_name, note_id)
    )
    conn.commit()


def delete_note(note_id: int) -> None:
    """
    Remove a note/tab from its notebook permanently.
    """
    c.execute(
        "DELETE FROM notes WHERE id = ?", (note_id,)
    )
    conn.commit()


def get_notebook_stats(nb_id: int) -> dict[str, int]:
    """
    Compute counts for notebook dashboard:
      - 'new'   : notes never reviewed (repetition = 0)
      - 'learn' : notes reviewed but not yet due (next_review in future)
      - 'due'   : notes reviewed and due now or overdue

    Returns a dict with keys 'new', 'learn', and 'due'.
    """
    now_iso = datetime.datetime.now().isoformat()

    c.execute(
        """
        SELECT
            SUM(CASE WHEN repetition = 0                      THEN 1 END) AS new,
            SUM(CASE WHEN repetition > 0 AND next_review > ?  THEN 1 END) AS learn,
            SUM(CASE WHEN repetition > 0 AND next_review <= ? THEN 1 END) AS due
        FROM notes
        WHERE notebook_id = ?
        """,
        (now_iso, now_iso, nb_id)
    )
    new, learn, due = c.fetchone() or (0, 0, 0)

    # Ensure integer results, defaulting to zero
    return {
        "new":   new or 0,
        "learn": learn or 0,
        "due":   due or 0,
    }
