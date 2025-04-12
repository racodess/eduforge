# flashcards_sm2.py

from datetime import datetime, timedelta
from utils.flashcards_db import get_card_by_id, c, conn

def update_sm2(card_id, quality):
    """
    quality: integer rating
      - "Again" = 0, "Hard" = 3, "Good" = 4, "Easy" = 5.
    """
    now = datetime.now()
    card = get_card_by_id(card_id)
    if not card:
        return None, None, None, None

    # card: (id, deck_id, front, back, next_review, interval, repetition, ef, extra_fields)
    interval = card[5] if card[5] is not None else 0
    repetition = card[6] if card[6] is not None else 0
    ef = card[7] if card[7] is not None else 2.5

    if quality < 3:
        # Failed review: next review in 1 minute
        repetition = 1
        interval = 1 / 1440  # 1 minute in days
        next_review = now + timedelta(minutes=1)
    else:
        new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if new_ef < 1.3:
            new_ef = 1.3
        ef = new_ef
        if repetition == 0:
            repetition = 1
            if quality == 3:
                # Hard: 6 minutes
                interval = 6 / 1440
                next_review = now + timedelta(minutes=6)
            elif quality == 4:
                # Good: 10 minutes
                interval = 10 / 1440
                next_review = now + timedelta(minutes=10)
            elif quality == 5:
                # Easy: 2 days
                interval = 2
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
    c.execute(
        "UPDATE cards SET next_review = ?, interval = ?, repetition = ?, ef = ? WHERE id = ?",
        (next_review_str, interval, repetition, ef, card_id)
    )
    conn.commit()
    return next_review, interval, repetition, ef

def project_interval(card, quality):
    """
    Return a timedelta for the *projected* next interval, without updating the DB.
    """
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
