from flask import Blueprint, render_template, request, redirect, url_for, session
import requests
from config import BACKEND_URL

login_bp = Blueprint("login", __name__)


# ========== LOAD PAGE ==========
@login_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        r = requests.post(
            f"{BACKEND_URL}/api/login",
            json={"username": username, "password": password},
        )

        # Authentication failed (invalid credentials)
        if r.status_code == 401:
            return render_template("login.html", error="Invalid username or password.")

        # Parse backend response
        data = r.json()

        # Successful login
        if data.get("status") == "ok":
            session["token"] = data.get("token")
            session["username"] = data.get("username")
            session["role"] = data.get("role")
            return redirect(url_for("client_monitor.client_monitor"))

        # Unknown or unexpected backend response
        return render_template(
            "login.html", error=data.get("error", "Login failed. Please try again.")
        )

    return render_template("login.html")


@login_bp.route("/logout")
def logout():
    # Clear user session and redirect to login page
    session.clear()
    return redirect(url_for("login.login"))
