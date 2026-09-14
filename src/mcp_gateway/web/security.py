"""Security middleware for MCP Gateway Admin Console."""

from flask import Response, abort, current_app, request


def check_trusted_host() -> None:
    """Reject unexpected Host headers before authentication or CSRF processing."""
    allowed = {
        str(host).strip().lower()
        for host in current_app.config.get("ADMIN_ALLOWED_HOSTS", set())
        if str(host).strip()
    }
    host = (request.host or "").split(":", 1)[0].strip("[]").lower()
    if allowed and host not in allowed:
        abort(403, description="Untrusted Host header")


def apply_security_headers(response: Response) -> Response:
    """Apply strict security and privacy headers to all HTTP responses."""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self'; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
