from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import requests
from config import BACKEND_URL
from utils.autho import login_required

client_storage_bp = Blueprint("client_storage", __name__)


# ========== LOAD PAGE ==========
@client_storage_bp.route("/client-storage/<client_id>")
@login_required
def client_storage(client_id):
    token = session.get("token")
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(f"{BACKEND_URL}/api/storage/{client_id}/files", headers=headers)

    if r.status_code != 200:
        flash("Failed to load file list.", "error")
        return render_template("client_storage.html", files=[], client_id=client_id)

    data = r.json()
    files = data.get("files", [])

    return render_template("client_storage.html", files=files, client_id=client_id)


# ========== REQUEST UPLOAD ==========
@client_storage_bp.route(
    "/client-storage/<client_id>/request-upload",
    methods=["POST"],
    endpoint="request_upload",
)
@login_required
def request_upload(client_id):
    token = session.get("token")
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(f"{BACKEND_URL}/api/storage/{client_id}/upload", headers=headers)

    if r.status_code == 201:
        flash("Upload request sent to client.", "success")
    else:
        flash("Failed to request upload.", "error")

    return redirect(url_for("client_storage.client_storage", client_id=client_id))


# ========== DOWNLOAD FILE ==========
@client_storage_bp.route("/client-storage/download/<int:file_id>", methods=["POST"])
@login_required
def download_file(file_id):
    token = session.get("token")
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(
        f"{BACKEND_URL}/api/storage/files/{file_id}/download", headers=headers
    )

    if r.status_code in (200, 202):
        flash("Download request sent to client.", "success")
    else:
        flash("Download request failed.", "error")

    return redirect(request.referrer)


# ========== CANCEL UPLOAD ==========
@client_storage_bp.route("/client-storage/cancel/<int:file_id>")
@login_required
def cancel_upload(file_id):
    token = session.get("token")
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(
        f"{BACKEND_URL}/api/storage/file/{file_id}/cancel", headers=headers
    )

    flash(
        "Upload canceled." if r.status_code == 200 else "Cancel failed.",
        "success" if r.status_code == 200 else "error",
    )

    return redirect(request.referrer)


# ========== DELETE FILE ==========
@client_storage_bp.route("/client-storage/delete/<int:file_id>", methods=["POST"])
@login_required
def delete_file(file_id):
    token = session.get("token")
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.delete(
        f"{BACKEND_URL}/api/storage/files/{file_id}/delete", headers=headers
    )

    if r.status_code == 200:
        flash("🗑 File deleted successfully.", "success")
    else:
        flash("❌ Delete failed.", "error")

    return redirect(request.referrer)
