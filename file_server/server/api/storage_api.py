import os
from flask import Blueprint, request, jsonify
from db.model import (
    get_files_by_client,
    get_file,
    update_file_status,
    delete_file,
    create_action,
    get_action_by_file,
    set_action_status,
)

storage_bp = Blueprint("storage", __name__)


# ========== CHECK TOKEN ==========
def check_token():
    auth = request.headers.get("Authorization")
    return auth.split(" ")[1] if auth and auth.startswith("Bearer ") else None


# ========== GET FILE LIST ==========
@storage_bp.route("/storage/<client_id>/files", methods=["GET"])
def list_files(client_id):
    if not check_token():
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    return jsonify({"status": "ok", "files": get_files_by_client(client_id)}), 200


# ========== REQUEST UPLOAD ==========
@storage_bp.route("/storage/<client_id>/upload", methods=["POST"])
def request_upload(client_id):
    if not check_token():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    action_id = create_action(client_id, None, "UPLOAD")

    return (
        jsonify(
            {
                "status": "ok",
                "message": "upload-request-created",
                "action_id": action_id,
            }
        ),
        201,
    )


# ========== REQUEST UPLOAD ==========
@storage_bp.route("/storage/file/<file_id>/cancel", methods=["POST"])
def cancel_upload(file_id):
    if not check_token():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    f = get_file(file_id)
    if not f:
        return jsonify({"status": "error", "message": "not-found"}), 404

    if f["status"] != "UPLOADING":
        return jsonify({"status": "error", "message": "not-active"}), 400

    action = get_action_by_file(file_id)
    if action:
        set_action_status(action["action_id"], "CANCELED")

    file_path = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage")),
        f["client_id"],
        f["filename"],
    )
    if os.path.exists(file_path):
        os.remove(file_path)

    delete_file(file_id)

    return jsonify({"status": "ok", "message": "upload-canceled"}), 200


# ========== DELETE ==========
@storage_bp.route("/storage/files/<file_id>/delete", methods=["DELETE"])
def remove_file(file_id):
    if not check_token():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    f = get_file(file_id)
    if not f:
        return jsonify({"status": "error", "message": "not-found"}), 404

    if f["status"] != "UPLOADED":
        return jsonify({"status": "error", "message": "not-allowed"}), 400

    file_path = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage")),
        f["client_id"],
        f["filename"],
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    delete_file(file_id)

    return jsonify({"status": "ok", "message": "file-deleted"}), 200


# ========== DOWNLOAD ==========
@storage_bp.route("/storage/files/<file_id>/download", methods=["POST"])
def request_download(file_id):
    if not check_token():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    f = get_file(file_id)
    if not f:
        return jsonify({"status": "error", "message": "file-not-found"}), 404

    action_id = create_action(f["client_id"], file_id, "DOWNLOAD")
    return (
        jsonify(
            {
                "status": "ok",
                "message": "download-request-created",
                "action_id": action_id,
            }
        ),
        202,
    )
