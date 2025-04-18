# utils/notes_sm2.py

from datetime import datetime, timedelta
from utils.notes_db import get_note_by_id, c, conn

# Columns in notes table:
# 0 id | 1 notebook_id | 2 tab_name | 3 content |
# 4 next_review | 5 interval | 6 repetition | 7 ef

def update_sm2(note_id: int, quality: int):
    """
    Apply SM‑2 to a notebook note.
    quality: 0 (“Again”), 3 (“Hard”), 4 (“Good”), 5 (“Easy”)
    """
    now = datetime.now()
    note = get_note_by_id(note_id)
    if not note:
        return None

    interval   = note[5] or 0
    repetition = note[6] or 0
    ef         = note[7] or 2.5

    if quality < 3:
        repetition = 1
        interval   = 1/1440
        next_rev   = now + timedelta(minutes=1)
    else:
        ef = max(1.3, ef + (0.1 - (5-quality)*(0.08 + (5-quality)*0.02)))
        if repetition == 0:
            repetition = 1
            if quality == 3:   interval, next_rev = 6/1440,  now + timedelta(minutes=6)
            elif quality == 4: interval, next_rev = 10/1440, now + timedelta(minutes=10)
            else:              interval, next_rev = 2,       now + timedelta(days=2)
        else:
            repetition += 1
            base = interval if interval >= 1 else 1
            if quality == 3:   interval = round(base * ef * 0.9)
            elif quality == 4: interval = round(base * ef)
            else:              interval = round(base * ef * 1.3)
            next_rev = now + timedelta(days=interval)

    c.execute("""UPDATE notes
                    SET next_review=?, interval=?, repetition=?, ef=?
                 WHERE id=?""",
              (next_rev.isoformat(), interval, repetition, ef, note_id))
    conn.commit()
    return next_rev, interval, repetition, ef

def project_interval(note_row, quality):
    """Return a *timedelta* for what the interval *would* be."""
    from utils.flashcards_sm2 import project_interval  # reuse core math
    # Build a fake “card” tuple matching flashcard layout so we can reuse:
    fake = (None,None,None,None, note_row[4], note_row[5], note_row[6], note_row[7], None)
    return project_interval(fake, quality)

from utils.flashcards_sm2 import format_interval_short   # identical helper
