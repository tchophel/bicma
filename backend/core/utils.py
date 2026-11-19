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
