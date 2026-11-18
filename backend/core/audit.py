from .models import AuditLog


def client_ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


def log(request, action, actor=None, entity_type="", entity_id="", detail=None):
    """Record a security/business event. Never put passwords, tokens or free-text PII in `detail`."""
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        actor = user if user is not None and user.is_authenticated else None
    AuditLog.objects.create(
        actor=actor,
        actor_email=actor.email if actor else "",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        detail=detail or {},
        ip_address=client_ip(request),
    )
