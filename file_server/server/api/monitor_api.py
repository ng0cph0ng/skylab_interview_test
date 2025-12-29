from flask import Blueprint, request, jsonify
from db.model import list_clients, list_clients_by_user, get_files_by_client

monitor_bp = Blueprint("monitor", __name__)

def format_size(bytes_value):
    if bytes_value < 1000 * 1000:
        return f"{round(bytes_value / 1000, 2)} KB"
    if bytes_value < 1000 * 1000 * 1000:
        return f"{round(bytes_value / (1000 * 1000), 2)} MB"
    return f"{round(bytes_value / (1000 * 1000 * 1000), 2)} GB"


# ========== MONITOR ==========
@monitor_bp.route("clients/monitor", methods=["POST"])
def monitor_clients():
    data = request.get_json()
    role = data.get("role")
    username = data.get("username")

    if not role or not username:
        return jsonify({"status": "error", "message": "missing-auth-info"}), 400

    if role == "ADMIN":
        clients = list_clients()
    else:
        clients = list_clients_by_user(username)

    result = []
    for c in clients:
        files = get_files_by_client(c["client_id"])
        total_size = sum(f["size"] for f in files)

        result.append(
            {
                "client_id": c["client_id"],
                "owner": c["username"],
                "status": c.get("status", "OFFLINE"),
                "file_count": len(files),
                "used_storage": format_size(total_size),
                "capacity_max": f"{c['capacity_max']} GB",
            }
        )

    return jsonify({"status": "ok", "clients": result}), 200
