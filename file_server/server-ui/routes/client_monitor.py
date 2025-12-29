from flask import Blueprint, render_template, session, redirect, url_for
import requests
from config import BACKEND_URL
from utils.autho import login_required

client_monitor_bp = Blueprint("client_monitor", __name__)

# ========== LOAD PAGE ==========
@client_monitor_bp.route("/client-monitor")
@login_required
def client_monitor():
    username = session.get("username")
    role = session.get("role")

    r = requests.post(
        f"{BACKEND_URL}/api/clients/monitor",
        json={"username": username, "role": role},
    )

    if r.status_code != 200:
        return render_template(
            "client_monitor.html", clients=[], role=role, error="Backend not responding"
        )

    data = r.json()
    clients = data.get("clients", [])

    return render_template("client_monitor.html", clients=clients, role=role)
