# notes_db.py

import sqlite3, os, datetime

DB_PATH = os.path.join(os.getcwd(), "notes.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ---------- 1)  INIT & SCHEMA UPDATES  -----------------------
def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS notebooks (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT UNIQUE)''')

    c.execute('''CREATE TABLE IF NOT EXISTS notes (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   notebook_id INTEGER,
                   tab_name     TEXT,
                   content      TEXT,
                   next_review  TEXT,      -- ISO str or NULL
                   interval     REAL,      -- days  (0 / NULL  -> “new”)
                   repetition   INTEGER,
                   ef           REAL,
                   FOREIGN KEY (notebook_id) REFERENCES notebooks(id))''')
    conn.commit()
    _update_schema_if_needed()

def _update_schema_if_needed():
    """Add the SM‑2 columns on existing DBs."""
    c.execute("PRAGMA table_info(notes)")
    cols = {row[1] for row in c.fetchall()}

    alter_stmts = []
    if "next_review" not in cols:
        alter_stmts.append("ADD COLUMN next_review TEXT")
    if "interval" not in cols:
        alter_stmts.append("ADD COLUMN interval REAL DEFAULT 0")
    if "repetition" not in cols:
        alter_stmts.append("ADD COLUMN repetition INTEGER DEFAULT 0")
    if "ef" not in cols:
        alter_stmts.append("ADD COLUMN ef REAL DEFAULT 2.5")

    for stmt in alter_stmts:
        c.execute(f"ALTER TABLE notes {stmt}")
    if alter_stmts:
        conn.commit()

# ---------- 2)  CRUD HELPERS  --------------------------------
def get_notebooks():
    c.execute("SELECT id, name FROM notebooks")
    return c.fetchall()

def create_notebook(name):
    c.execute("INSERT INTO notebooks (name) VALUES (?)", (name,))
    conn.commit()
    nb_id = c.lastrowid
    create_note(nb_id, "Default", "")
    return nb_id

def delete_notebook(nb_id):
    c.execute("DELETE FROM notes WHERE notebook_id = ?", (nb_id,))
    c.execute("DELETE FROM notebooks WHERE id = ?", (nb_id,))
    conn.commit()

def rename_notebook(nb_id, new_name):
    c.execute("UPDATE notebooks SET name=? WHERE id=?", (new_name, nb_id))
    conn.commit()

# ---- notes (compact rows, for browsing) ----
def get_notes(nb_id):
    c.execute("SELECT id, tab_name, content FROM notes WHERE notebook_id=?", (nb_id,))
    return c.fetchall()

# ---- notes (full row, for SM‑2 / review) ----
def get_note_by_id(note_id):
    c.execute("SELECT * FROM notes WHERE id=?", (note_id,))
    return c.fetchone()

def get_notes_full(nb_id):
    c.execute("""SELECT id, tab_name, content,
                        next_review, interval, repetition, ef
                 FROM notes WHERE notebook_id=?""", (nb_id,))
    return c.fetchall()

def create_note(nb_id, tab_name, content):
    c.execute("""INSERT INTO notes
                    (notebook_id, tab_name, content,
                     next_review, interval, repetition, ef)
                 VALUES (?, ?, ?, NULL, 0, 0, 2.5)""",
              (nb_id, tab_name, content))
    conn.commit()
    return c.lastrowid

def update_note(note_id, content):
    c.execute("UPDATE notes SET content=? WHERE id=?", (content, note_id))
    conn.commit()

def rename_note(note_id, new_tab_name):
    c.execute("UPDATE notes SET tab_name=? WHERE id=?", (new_tab_name, note_id))
    conn.commit()

def delete_note(note_id):
    c.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit()

def get_notebook_stats(nb_id: int) -> dict[str, int]:
    """
    Return counts that match the flash‑card dashboard:
      • new   – notes never reviewed (repetition = 0)
      • learn – reviewed ≥1× but *not* yet due  (next_review in the future)
      • due   – reviewed ≥1× and next_review is now or past‑due
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
        (now_iso, now_iso, nb_id),
    )
    new, learn, due = c.fetchone() or (0, 0, 0)
    return {
        "new":   new   or 0,
        "learn": learn or 0,
        "due":   due   or 0,
    }
