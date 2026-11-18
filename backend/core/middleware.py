import time

from . import logs


class ApiLogMiddleware:
    """Records each API request: method, path, status, time taken and who made it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/") or request.path.startswith(logs.SKIP_PREFIXES):
            return self.get_response(request)
        start = time.monotonic()
        status, error = 0, ""
        try:
            response = self.get_response(request)
            status = response.status_code
            return response
        except Exception as exc:
            status, error = 500, type(exc).__name__
            raise
        finally:
            user = getattr(request, "user", None)
            logs.api_call("in", request.method, request.path, status, (time.monotonic() - start) * 1000,
                          user.email if user is not None and user.is_authenticated else "", request.META.get("REMOTE_ADDR") or None, error)
