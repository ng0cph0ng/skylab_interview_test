from flask import Blueprint, jsonify
from db.model import list_clients

manager_bp = Blueprint("manager_api", __name__)

@manager_bp.route("/clients", methods=["GET"])
def api_list_clients():
    clients = list_clients()
    return jsonify({"status":"ok", "data":clients}), 200
