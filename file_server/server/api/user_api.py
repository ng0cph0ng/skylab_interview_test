from flask import Blueprint, jsonify
from db.model import list_users

user_bp = Blueprint("user_api", __name__)

@user_bp.route("/users", methods=["GET"])
def api_list_users():
    users = list_users()
    result = [
        {
            "user_id": u["user_id"],
            "username": u["username"],
        } for u in users
    ]
    return jsonify({"status":"ok", "data":result}), 200
