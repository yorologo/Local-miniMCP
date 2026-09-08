"""CSRF protection module for MCP Gateway Admin Console."""

import hmac
import secrets
from flask import session, request, abort


def get_csrf_token() -> str:
    """Retrieve current session CSRF token or generate a new cryptographically secure token."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_token(token: str) -> bool:
    """Validate submitted CSRF token against session token using constant-time comparison."""
    session_token = session.get("csrf_token")
    if not session_token or not token:
        return False
    return hmac.compare_digest(session_token, token)


def check_csrf():
    """Verify CSRF token for state-mutating requests (POST, PUT, DELETE, PATCH)."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not token or not validate_csrf_token(token):
            abort(403, description="CSRF token missing or invalid")
