import uuid


def parse_uuid(value):
    """Return a UUID for a query-string value, or None if it is missing/invalid (avoids 500s on bad input)."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def parse_date(value):
    import datetime as dt
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def proper_name(value):
    """A person's name with a capital letter at the start of each word: "dechen LHAM" -> "Dechen Lham". A word that already mixes
    capitals and small letters ("McDonald") is kept, only its first letter is made a capital. Extra spaces are removed."""
    words = []
    for w in str(value or "").split():
        words.append(w.capitalize() if (w.islower() or w.isupper()) else w[0].upper() + w[1:])
    return " ".join(words)
