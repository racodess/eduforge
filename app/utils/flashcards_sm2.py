# flashcards_sm2.py

"""
Implements the SM-2 spaced repetition algorithm for flashcards.
Provides functions to update card review schedules based on user feedback
and to project next intervals without persisting changes.
Also includes a helper to format intervals concisely for UI display.
"""

from datetime import datetime, timedelta
from utils.flashcards_db import get_card_by_id, c, conn


def update_sm2(card_id: int, quality: int):
    """
    Apply the SM-2 algorithm to update a flashcard's scheduling metadata.

    Parameters:
        card_id: ID of the card to update.
        quality: integer rating of review performance:
            0 = Again, 3 = Hard, 4 = Good, 5 = Easy.

    Returns:
        Tuple (next_review_datetime, interval_days, repetition_count, ef)
        or (None, None, None, None) if card not found.
    """
    now = datetime.now()
    card = get_card_by_id(card_id)
    if not card:
        # No card retrieved; abort update
        return None, None, None, None

    # Unpack existing SM-2 fields or use defaults
    # card format: (id, deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
    interval = card[5] if card[5] is not None else 0
    repetition = card[6] if card[6] is not None else 0
    ef = card[7] if card[7] is not None else 2.5

    if quality < 3:
        # Treat as failed review: reset repetition and schedule soon
        repetition = 1
        interval = 1 / 1440  # 1 minute expressed in days
        next_review = now + timedelta(minutes=1)
    else:
        # Successful review: adjust easiness factor
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(new_ef, 1.3)  # EF should not drop below 1.3

        if repetition == 0:
            # First time passing: set initial intervals
            repetition = 1
            if quality == 3:
                # Hard: review after 6 minutes
                interval = 6 / 1440
                next_review = now + timedelta(minutes=6)
            elif quality == 4:
                # Good: review after 10 minutes
                interval = 10 / 1440
                next_review = now + timedelta(minutes=10)
            else:
                # Easy: review after 2 days
                interval = 2
                next_review = now + timedelta(days=2)
        else:
            # Subsequent repetition: multiply by EF
            repetition += 1
            base = interval if interval >= 1 else 1
            if quality == 3:
                interval = round(base * ef * 0.9)
            elif quality == 4:
                interval = round(base * ef)
            else:
                interval = round(base * ef * 1.3)

            # Schedule next review after computed days
            next_review = now + timedelta(days=interval)

    # Persist updated scheduling back to the database
    next_review_str = next_review.isoformat()
    c.execute(
        "UPDATE cards SET next_review = ?, interval = ?, repetition = ?, ef = ? WHERE id = ?",
        (next_review_str, interval, repetition, ef, card_id)
    )
    conn.commit()
    return next_review, interval, repetition, ef


def project_interval(card: tuple, quality: int) -> timedelta:
    """
    Compute the next review interval for a card without saving changes.

    Parameters:
        card: tuple from get_card_by_id containing scheduling fields.
        quality: integer rating as in update_sm2.

    Returns:
        A timedelta until the next review.
    """
    # Extract SM-2 values or use defaults
    interval = card[5] if card[5] is not None else 0
    repetition = card[6] if card[6] is not None else 0
    ef = card[7] if card[7] is not None else 2.5

    if quality < 3:
        # If review failed: next review in 1 minute
        return timedelta(minutes=1)
    
    # Adjust EF for successful review
    new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(new_ef, 1.3)

    if repetition == 0:
        # First pass intervals
        if quality == 3:
            return timedelta(minutes=6)
        elif quality == 4:
            return timedelta(minutes=10)
        else:
            return timedelta(days=2)
        
    # Subsequent passes: scale base interval
    base = interval if interval >= 1 else 1
    
    if quality == 3:
        new_interval = round(base * new_ef * 0.9)
    elif quality == 4:
        new_interval = round(base * new_ef)
    else:
        new_interval = round(base * new_ef * 1.3)
    return timedelta(days=new_interval)


def format_interval_short(td: timedelta) -> str:
    """
    Format a timedelta into a short string for display:
      - '<Xm' for minutes under 60
      - '<Xh' for hours under 24
      - '<Xd' for days
    """
    total_minutes = td.total_seconds() / 60
    if total_minutes < 60:
        # Display in minutes, at least 1m
        minutes = max(int(total_minutes), 1)
        return f"<{minutes}m"
    elif total_minutes < 1440:
        # Display in hours
        hours = round(total_minutes / 60)
        return f"<{hours}h"
    else:
        # Display in days
        days = td.days
        return f"<{days}d"
