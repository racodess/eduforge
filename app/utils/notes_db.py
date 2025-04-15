# notes_db.py

import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), "notes.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''
        CREATE TABLE IF NOT EXISTS notebooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER,
            tab_name TEXT,
            content TEXT,
            FOREIGN KEY (notebook_id) REFERENCES notebooks (id)
        )
    ''')
    conn.commit()

def get_notebooks():
    c.execute("SELECT id, name FROM notebooks")
    return c.fetchall()

def create_notebook(name):
    try:
        c.execute("INSERT INTO notebooks (name) VALUES (?)", (name,))
        conn.commit()
        notebook_id = c.lastrowid
        # Create a default tab for every new notebook.
        create_note(notebook_id, "Default", "")
        return notebook_id
    except Exception as e:
        print(f"Error creating notebook: {e}")
        return None

def delete_notebook(notebook_id):
    c.execute("DELETE FROM notebooks WHERE id = ?", (notebook_id,))
    c.execute("DELETE FROM notes WHERE notebook_id = ?", (notebook_id,))
    conn.commit()

def rename_notebook(notebook_id, new_name):
    c.execute("UPDATE notebooks SET name = ? WHERE id = ?", (new_name, notebook_id))
    conn.commit()

def get_notes(notebook_id):
    c.execute("SELECT id, tab_name, content FROM notes WHERE notebook_id = ?", (notebook_id,))
    return c.fetchall()

def create_note(notebook_id, tab_name, content):
    c.execute("INSERT INTO notes (notebook_id, tab_name, content) VALUES (?, ?, ?)", (notebook_id, tab_name, content))
    conn.commit()
    return c.lastrowid

def update_note(note_id, content):
    c.execute("UPDATE notes SET content = ? WHERE id = ?", (content, note_id))
    conn.commit()

def rename_note(note_id, new_tab_name):
    c.execute("UPDATE notes SET tab_name = ? WHERE id = ?", (new_tab_name, note_id))
    conn.commit()

def delete_note(note_id):
    c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
