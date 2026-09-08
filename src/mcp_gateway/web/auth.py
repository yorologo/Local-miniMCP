"""Authentication, session management, and rate limiting for Admin Console."""

from functools import wraps
import time
from typing import Dict, Tuple
from flask import session, request, redirect, url_for, flash, current_app, abort

try:
    from werkzeug.security import check_password_hash
except ImportError:
    import hashlib
    def check_password_hash(p_hash: str, password: str) -> bool:
        if p_hash.startswith("pbkdf2:sha256:"):
            parts = p_hash.split("$")
            salt = parts[0].split(":")[-1]
            digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
            return digest == parts[-1]
        return False


# In-memory rate limiting: (key -> (failure_count, last_failure_timestamp, lockout_until))
_FAILED_LOGINS: Dict[str, Tuple[int, float, float]] = {}
MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 300.0  # 5 minutes
LOCKOUT_SECONDS = 60.0          # 1 minute lockout after 5 failures


def is_rate_limited(key: str) -> bool:
    """Check if the key (IP or username) is currently locked out."""
    now = time.time()
    record = _FAILED_LOGINS.get(key)
    if not record:
        return False
    count, last_time, lockout_until = record
    if now < lockout_until:
        return True
    if now - last_time > FAILURE_WINDOW_SECONDS:
        # Window expired, reset
        _FAILED_LOGINS.pop(key, None)
        return False
    return False


def record_login_failure(key: str):
    """Record a failed login attempt and set lockout if threshold is exceeded."""
    now = time.time()
    record = _FAILED_LOGINS.get(key)
    if not record or (now - record[1] > FAILURE_WINDOW_SECONDS):
        _FAILED_LOGINS[key] = (1, now, 0.0)
    else:
        new_count = record[0] + 1
        lockout_until = now + LOCKOUT_SECONDS if new_count >= MAX_FAILED_ATTEMPTS else 0.0
        _FAILED_LOGINS[key] = (new_count, now, lockout_until)


def reset_login_failures(key: str):
    """Clear failed login attempts upon successful login."""
    _FAILED_LOGINS.pop(key, None)


def login_required(f):
    """Decorator to require an active authenticated admin session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        if not user:
            return redirect(url_for("auth.login", next=request.path))

        # Check session timeout (default 30 minutes)
        last_active = session.get("last_active")
        now = time.time()
        timeout = 1800  # 30 minutes
        if last_active and (now - last_active > timeout):
            session.clear()
            flash("Session expired due to inactivity. Please log in again.", "warning")
            return redirect(url_for("auth.login", next=request.path))

        session["last_active"] = now
        return f(*args, **kwargs)
    return decorated_function
