from flask import Blueprint, render_template, request, redirect, url_for, flash
import requests
from utils.autho import admin_required
from config import BACKEND_URL

client_manager_bp = Blueprint("client_manager", __name__)


# ========== LOAD PAGE ==========
@client_manager_bp.route("/client-manager")
@admin_required
def client_manager():
    r_clients = requests.get(f"{BACKEND_URL}/api/clients")
    clients = r_clients.json().get("data", []) if r_clients.status_code == 200 else []

    r_users = requests.get(f"{BACKEND_URL}/api/users")
    users = r_users.json().get("data", []) if r_users.status_code == 200 else []

    return render_template("client_manager.html", clients=clients, users=users)


# ========== ADD CLIENT ==========
@client_manager_bp.route("/client-manager/add", methods=["POST"])
@admin_required
def client_add():
    data = {
        "client_id": request.form.get("client_id"),
        "password": request.form.get("password"),
        "capacity": request.form.get("capacity"),
        "user_owner": request.form.get("user_owner"),
    }

    response = requests.post(f"{BACKEND_URL}/api/clients", json=data)

    if response.status_code == 409:  # duplicate
        flash("Client ID already exists. Please choose another.", "error")
        return render_template(
            "client_manager.html",
            clients=requests.get(f"{BACKEND_URL}/api/clients").json().get("data", []),
            users=requests.get(f"{BACKEND_URL}/api/users").json().get("data", []),
            add_error="Client ID already exists. Please choose another.",
            show_add_modal=True,
        )

    if response.status_code == 201:
        flash("Client successfully added!", "success")
        return redirect(url_for("client_manager.client_manager"))

    flash("Unexpected error occurred.", "error")
    return redirect(url_for("client_manager.client_manager"))


# ========== EDIT PASSWORD ==========
@client_manager_bp.route("/client-manager/edit/<client_id>", methods=["POST"])
@admin_required
def client_edit(client_id):
    password = request.form.get("password")

    if not password.strip():
        flash("Password cannot be empty.", "error")
        return redirect(url_for("client_manager.client_manager"))

    response = requests.put(
        f"{BACKEND_URL}/api/clients/{client_id}", json={"password": password}
    )

    flash(
        (
            "Password updated successfully."
            if response.status_code == 200
            else "Failed to update password."
        ),
        "success" if response.status_code == 200 else "error",
    )
    return redirect(url_for("client_manager.client_manager"))


# ========== DELETE ==========
@client_manager_bp.route("/client-manager/delete/<client_id>", methods=["POST"])
@admin_required
def client_delete(client_id):
    r = requests.delete(f"{BACKEND_URL}/api/clients/{client_id}")

    flash(
        (
            "Client removed."
            if r.status_code == 200
            else (
                "Client not found."
                if r.status_code == 404
                else "Unable to delete client."
            )
        ),
        "success" if r.status_code == 200 else "error",
    )
    return redirect(url_for("client_manager.client_manager"))
