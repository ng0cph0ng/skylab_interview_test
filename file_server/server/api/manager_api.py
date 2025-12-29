from flask import Blueprint, request, jsonify
from db.model import list_clients, list_users, add_client, update_client, delete_client
from db.model import get_client
import bcrypt

manager_bp = Blueprint("manager_api", __name__)


# ========== GET CLIENT LIST ==========
@manager_bp.route("/clients", methods=["GET"])
def api_list_clients():
    clients = list_clients()
    return jsonify({"status": "ok", "data": clients}), 200


# ========== ADD CLIENT ==========
@manager_bp.route("/clients", methods=["POST"])
def api_add_client():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "error", "error": "missing-body"}), 400

    client_id = data.get("client_id")
    password = data.get("password")
    capacity = data.get("capacity")
    user_owner = data.get("user_owner")

    if not client_id or not password or not capacity or not user_owner:
        return jsonify({"status": "error", "error": "missing-fields"}), 400

    # Check duplicate
    if get_client(client_id):
        return jsonify({"status": "error", "error": "client-exists"}), 409

    # Hash password in backend
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    try:
        add_client(client_id, password_hash, capacity, user_owner)
        return jsonify({"status": "ok", "message": "client-added"}), 201
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ========== UPDATE PASSWORD ==========
@manager_bp.route("/clients/<client_id>", methods=["PUT"])
def api_update_client(client_id):
    data = request.get_json(silent=True)

    if not data or "password" not in data:
        return jsonify({"status": "error", "error": "missing-password"}), 400

    password = data.get("password")
    if not password or password.strip() == "":
        return jsonify({"status": "error", "error": "empty-password"}), 400

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    update_client(client_id, password_hash, None, None)
    return jsonify({"status": "ok", "message": "password-updated"}), 200


# ========== DELETE CLIENT ==========
@manager_bp.route("/clients/<client_id>", methods=["DELETE"])
def api_delete_client(client_id):
    if not get_client(client_id):
        return jsonify({"status": "error", "error": "not-found"}), 404

    delete_client(client_id)
    return jsonify({"status": "ok", "message": "client-deleted"}), 200
