import socket, ssl, threading, os, sys, time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from db.model import (
    get_client,
    add_file,
    update_file_status,
    get_pending_actions_by_client,
    set_action_status,
    update_client_status,
    get_file,
)
from utils.hash import verify_password

HOST = "0.0.0.0"
PORT = 8000

CERT_PATH = os.path.join(os.path.dirname(__file__), "cert.pem")
KEY_PATH = os.path.join(os.path.dirname(__file__), "key.pem")

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(CERT_PATH, KEY_PATH)

STORAGE_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

last_seen = {}


def get_unique_filename(folder, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new = filename
    while os.path.exists(os.path.join(folder, new)):
        new = f"{base} ({counter}){ext}"
        counter += 1
    return new


def handle_client(conn, addr):
    print(f"[CONNECTED] {addr}")
    cid = None

    try:
        # ========== LOGIN ==========
        data = conn.recv(1024).decode().strip()
        if not data.startswith("LOGIN"):
            conn.send(b"ERROR UNKNOWN_COMMAND\n")
            return

        _, cid, pwd = data.split(" ", 2)
        user = get_client(cid)

        if not user or not verify_password(pwd, user["password_hash"]):
            conn.send(b"ERROR INVALID_CREDENTIALS\n")
            return

        conn.send(b"OK AUTHORIZED\n")
        update_client_status(cid, "ONLINE")
        last_seen[cid] = time.time()
        print(f"[AUTH] {cid} LOGIN")

        # ========== MAIN LOOP ==========
        waiting_for_path = False
        current_action = None

        while True:

            if not waiting_for_path:  # chỉ timeout khi không chờ path
                if time.time() - last_seen.get(cid, 0) > 12:
                    print(f"[TIMEOUT] {cid} => OFFLINE")
                    update_client_status(cid, "OFFLINE")
                    break

            conn.settimeout(None if waiting_for_path else 1.0)

            try:
                data = conn.recv(4096).decode().strip()
            except socket.timeout:
                data = ""

            # ❤️ HEARTBEAT
            if not waiting_for_path and data.startswith("PING"):
                last_seen[cid] = time.time()
                update_client_status(cid, "ONLINE")
                continue

            # ========== CHECK ACTION FROM UI ==========
            actions = get_pending_actions_by_client(cid)
            if actions and not waiting_for_path:
                current_action = actions[0]

                action_type = current_action.get("action_type")  # 👈 DÙNG ĐÚNG SCHEMA

                if not action_type:
                    print("❗ Missing action_type, skip this action")
                    set_action_status(current_action["action_id"], "CANCELED")
                    continue

                if current_action["status"] in ("DONE", "CANCELED"):
                    continue

                waiting_for_path = True
                set_action_status(current_action["action_id"], "RUNNING")
                last_seen[cid] = time.time()

                if action_type == "UPLOAD":
                    conn.send(
                        b"\nUpload request from UI\nEnter file path (or 'cancel'):\n\n"
                    )

                elif action_type == "DOWNLOAD":
                    conn.send(
                        b"\nDownload request from UI\nEnter save path (or 'cancel'):\n\n"
                    )

                continue

            # ========== 📤 UPLOAD FLOW ==========
            if (
                waiting_for_path
                and current_action
                and current_action["action_type"] == "UPLOAD"
                and data
            ):
                req = data.strip()

                if req.lower() == "cancel":
                    set_action_status(current_action["action_id"], "CANCELED")
                    conn.send(b"Upload canceled.\n")
                    waiting_for_path = False
                    continue

                filename = os.path.basename(req)
                folder = os.path.join(STORAGE_DIR, cid)
                os.makedirs(folder, exist_ok=True)
                filename = get_unique_filename(folder, filename)

                conn.send(b"OK START_UPLOAD\n")
                size_raw = conn.recv(4096).decode().strip()
                file_size = int(size_raw)
                file_id = add_file(cid, filename, file_size, "UPLOADING")

                save_path = os.path.join(folder, filename)
                received = 0

                with open(save_path, "wb") as f:
                    while received < file_size:
                        chunk = conn.recv(min(4096, file_size - received))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)

                update_file_status(file_id, "UPLOADED")
                set_action_status(current_action["action_id"], "DONE")
                conn.send(b"\nUpload completed!\n")

                waiting_for_path = False
                last_seen[cid] = time.time()
                continue

            # ========== 📥 DOWNLOAD FLOW ==========
            if (
                waiting_for_path
                and current_action
                and current_action["action_type"] == "DOWNLOAD"
                and data
            ):
                req = data.strip()

                if req.lower() == "cancel":
                    set_action_status(current_action["action_id"], "CANCELED")
                    conn.send(b"Download canceled.\n")
                    waiting_for_path = False
                    continue

                file_info = get_file(current_action["file_id"])
                file_path = os.path.join(STORAGE_DIR, cid, file_info["filename"])

                if not os.path.exists(file_path):
                    conn.send(b"ERROR FILE NOT FOUND ON SERVER\n")
                    waiting_for_path = False
                    continue

                file_size = os.path.getsize(file_path)
                file_name = file_info["filename"]
                conn.send(f"{file_size}|{file_name}\n".encode())

                with open(file_path, "rb") as f:
                    conn.sendfile(f)

                conn.send(b"\nDownload completed!\n")
                set_action_status(current_action["action_id"], "DONE")

                waiting_for_path = False
                last_seen[cid] = time.time()
                continue

    except Exception as e:
        print(f"[ERROR] {cid} crashed: {e}")

    finally:
        if cid:
            update_client_status(cid, "OFFLINE")
        conn.close()
        print(f"[DISCONNECTED] {addr}")


def start_secure_server():
    print(f"[TCP] Listening on {HOST}:{PORT} (SSL ENABLED)")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()

    while True:
        client, addr = sock.accept()
        conn = context.wrap_socket(client, server_side=True)
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_secure_server()
