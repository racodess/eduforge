# utils/notes_sm2.py

"""
Implements SM-2 spaced repetition algorithm for notebook notes.
Provides functions to update review scheduling and to project next intervals.
"""

from datetime import datetime, timedelta
from utils.notes_db import get_note_by_id, c, conn

# notes table columns: id, notebook_id, tab_name, content,
# next_review, interval, repetition, ef


def update_sm2(note_id: int, quality: int):
    """
    Apply the SM-2 algorithm to schedule the next review for a note.

    Parameters:
        note_id: ID of the note to update.
        quality: Review quality score (0=Again, 3=Hard, 4=Good, 5=Easy).

    Returns:
        A tuple (next_review_datetime, interval_days, repetition_count, updated_ef)
        or None if note not found.
    """
    now = datetime.now()
    note = get_note_by_id(note_id)
    if not note:
        # No such note; nothing to update
        return None

    # Unpack stored SM-2 parameters or use defaults
    interval   = note[5] or 0 # days until next review (may be fractional)
    repetition = note[6] or 0 # number of successful repetitions so far
    ef         = note[7] or 2.5 # easiness factor

    # If quality below threshold, reset repetition and schedule soon
    if quality < 3:
        repetition = 1

        # tiny interval (1 minute) encoded as fraction of day
        interval   = 1 / 1440
        next_rev   = now + timedelta(minutes=1)
    else:
        # Update easiness factor, ensuring it doesn't drop below 1.3
        ef = max(
            1.3,
            ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        )
        if repetition == 0:
            # First successful review: set base intervals
            repetition = 1
            if quality == 3:
                interval, next_rev = 6 / 1440, now + timedelta(minutes=6)
            elif quality == 4:
                interval, next_rev = 10 / 1440, now + timedelta(minutes=10)
            else:
                # Easy: interval measured in days
                interval, next_rev = 2, now + timedelta(days=2)
        else:
            # Subsequent reviews: multiply previous interval by EF
            repetition += 1

            # Ensure we multiply by at least 1 day
            base = interval if interval >= 1 else 1
            if quality == 3:
                interval = round(base * ef * 0.9)
            elif quality == 4:
                interval = round(base * ef)
            else:
                interval = round(base * ef * 1.3)
            next_rev = now + timedelta(days=interval)

    # Save updated scheduling back to database
    c.execute(
        """
        UPDATE notes
           SET next_review = ?,
               interval     = ?,
               repetition   = ?,
               ef           = ?
         WHERE id = ?
        """,
        (next_rev.isoformat(), interval, repetition, ef, note_id)
    )
    conn.commit()
    return next_rev, interval, repetition, ef


def project_interval(note_row, quality):
    """
    Compute what the next interval would be, without saving changes.
    Reuses the flashcards SM-2 projection logic for consistency.

    Parameters:
        note_row: tuple from get_note_by_id containing SM-2 fields.
        quality: integer quality rating (0,3,4,5).

    Returns:
        timedelta representing projected interval until next review.
    """
    from utils.flashcards_sm2 import project_interval as fc_project
    # Construct a fake flashcard record to leverage shared logic
    fake_card = (
        None, None, None, None,
        note_row[4], # next_review
        note_row[5], # interval
        note_row[6], # repetition
        note_row[7], # ef
        None
    )
    return fc_project(fake_card, quality)

# Reuse the same interval formatting helper from flashcards
from utils.flashcards_sm2 import format_interval_short
