from rest_framework.authentication import SessionAuthentication


class CsrfOnlyAuthentication(SessionAuthentication):
    """Enforces CSRF on unauthenticated unsafe requests (e.g. login) without authenticating."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        return None
