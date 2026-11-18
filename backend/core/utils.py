import uuid


def parse_uuid(value):
    """Return a UUID for a query-string value, or None if it is missing/invalid (avoids 500s on bad input)."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
