from flask import Blueprint, request, jsonify
from db.database import get_connection
from db.model import get_user_by_username
import bcrypt
import secrets

login_bp = Blueprint("login", __name__)


# ========== LOGIN ==========
@login_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not data or "username" not in data or "password" not in data:
        return jsonify({"status": "error", "error": "missing-credentials"}), 400

    username = data["username"].strip()
    password = data["password"]

    user = get_user_by_username(username)
    if not user:
        return jsonify({"status": "error", "error": "user-not-found"}), 401

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"status": "error", "error": "invalid-password"}), 401

    token = secrets.token_hex(32)

    return (
        jsonify(
            {
                "status": "ok",
                "message": "login-success",
                "token": token,
                "username": user["username"],
                "role": user["role"],
            }
        ),
        200,
    )
