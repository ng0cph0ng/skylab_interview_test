from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Check token from new API login system
        if "token" not in session:
            return redirect(url_for("login.login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Must be logged in
        if "token" not in session:
            return redirect(url_for("login.login"))

        # Role must be ADMIN
        if session.get("role") != "ADMIN":
            return redirect(url_for("dashboard.dashboard"))
        return f(*args, **kwargs)
    return wrapper
