import socket, ssl, threading, os, sys, time, hashlib

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from db.model import (
    get_client,
    add_file,
    update_file_status,
    get_pending_actions_by_client,
    get_action_by_file,
    set_action_status,
    update_client_status,
    get_file,
    update_file_received,
    finish_file_upload,
    get_interrupted_action,
    attach_file_to_action,
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


def recv_text(sock, timeout=None):
    sock.settimeout(timeout)
    try:
        data = sock.recv(4096)
        if not data:
            return ""
        return data.decode(errors="ignore").strip()
    except socket.timeout:
        return ""
    except:
        return ""


def handle_client(conn, addr):
    print(f"[CONNECTED] {addr}")
    cid = None

    try:
        # ========== LOGIN ==========
        raw = conn.recv(1024)
        if not raw:
            return
        parts = raw.decode(errors="ignore").strip().split(" ", 2)

        if len(parts) != 3 or parts[0] != "LOGIN":
            conn.send(b"ERROR UNKNOWN_COMMAND\n")
            return

        _, cid, pwd = parts
        user = get_client(cid)

        if not user or not verify_password(pwd, user["password_hash"]):
            conn.send(b"ERROR INVALID_CREDENTIALS\n")
            return

        conn.send(b"OK AUTHORIZED\n")
        update_client_status(cid, "ONLINE")
        last_seen[cid] = time.time()
        print(f"[AUTH] {cid} LOGIN")

        waiting_for_path = False
        current_action = None
        upload_meta = None

        while True:
            if not waiting_for_path and (time.time() - last_seen.get(cid, 0)) > 12:
                print(f"[TIMEOUT] {cid} => OFFLINE")
                update_client_status(cid, "OFFLINE")
                break

            data = recv_text(conn, None if waiting_for_path else 1.0)

            # ========== HEARTBEAT ==========
            if not waiting_for_path and data.startswith("PING"):
                last_seen[cid] = time.time()
                update_client_status(cid, "ONLINE")
                continue

            # ========== RESUME ==========
            if not waiting_for_path:
                interrupted = get_interrupted_action(cid)
                if interrupted:
                    current_action = interrupted
                    file_info = get_file(current_action["file_id"])
                    if not file_info:
                        set_action_status(current_action["action_id"], "CANCELED")
                        continue

                    filename = file_info["filename"]
                    file_size = file_info["size"]
                    received = file_info["received"]

                    print(f"[RESUME DETECTED] {cid} {filename} {received}/{file_size}")

                    upload_meta = {"filename": filename, "size": file_size}
                    waiting_for_path = True
                    set_action_status(current_action["action_id"], "RUNNING")
                    conn.send(f"OFFSET {received}\n".encode())
                    last_seen[cid] = time.time()
                    continue

            # ========== NEW ACTION ==========
            actions = get_pending_actions_by_client(cid)
            if actions and not waiting_for_path:
                current_action = actions[0]
                action_type = current_action.get("action_type")

                if not action_type:
                    set_action_status(current_action["action_id"], "CANCELED")
                    continue

                if current_action["status"] in ("DONE", "CANCELED"):
                    continue

                waiting_for_path = True
                set_action_status(current_action["action_id"], "RUNNING")
                last_seen[cid] = time.time()

                if action_type == "UPLOAD":
                    conn.send(b"\nUpload request\nEnter file path:\n\n")
                elif action_type == "DOWNLOAD":
                    conn.send(b"\nDownload request\nEnter save path:\n\n")
                continue

            # ========== UPLOAD ==========
            if (
                waiting_for_path
                and current_action
                and current_action["action_type"] == "UPLOAD"
            ):

                folder = os.path.join(STORAGE_DIR, cid)
                os.makedirs(folder, exist_ok=True)

                # ========== RESUME ==========
                if upload_meta is not None:
                    filename = upload_meta["filename"]
                    file_size = upload_meta["size"]
                    info = get_file(current_action["file_id"])
                    received_now = info["received"]
                    save_path = os.path.join(folder, filename)

                    print(f"[RESUME] {cid} {filename} from {received_now}/{file_size}")

                    f = open(save_path, "ab")
                    h = hashlib.sha256()

                    with open(save_path, "rb") as existing:
                        while True:
                            b = existing.read(4096)
                            if not b:
                                break
                            h.update(b)

                    while received_now < file_size:
                        action = get_action_by_file(current_action["file_id"])
                        if action and action["status"] == "CANCELED":
                            print(f"[UPLOAD CANCELED] {cid}")
                            f.close()
                            try:
                                os.remove(save_path)
                            except:
                                pass
                            upload_meta = None
                            waiting_for_path = False
                            break

                        part = conn.recv(min(4096, file_size - received_now))
                        if not part:
                            print(f"[INTERRUPTED RESUME] {cid}")
                            set_action_status(
                                current_action["action_id"], "INTERRUPTED"
                            )
                            waiting_for_path = False
                            break

                        f.write(part)
                        h.update(part)
                        received_now += len(part)
                        update_file_received(current_action["file_id"], received_now)

                    f.close()

                    if received_now < file_size:
                        upload_meta = None
                        continue

                    ck_line = recv_text(conn, 2.0)
                    client_ck = ck_line.split(" ", 1)[1] if " " in ck_line else ""
                    server_ck = h.hexdigest()

                    if client_ck != server_ck:
                        update_file_status(current_action["file_id"], "CANCELED")
                        set_action_status(current_action["action_id"], "CANCELED")
                        conn.send(b"ERROR CHECKSUM MISMATCH\n")
                        waiting_for_path = False
                        upload_meta = None
                        continue

                    finish_file_upload(current_action["file_id"], server_ck)
                    set_action_status(current_action["action_id"], "DONE")
                    conn.send(b"\nUpload completed!\n")

                    upload_meta = None
                    waiting_for_path = False
                    last_seen[cid] = time.time()
                    continue

                # ========== NEW UPLOAD ==========
                if not data:
                    continue

                req = data.strip()
                if req.lower() == "cancel":
                    set_action_status(current_action["action_id"], "CANCELED")
                    conn.send(b"Upload canceled.\n")
                    waiting_for_path = False
                    continue

                clean = req.replace("\\", "/")
                filename = os.path.basename(clean)
                filename = get_unique_filename(folder, filename)

                conn.send(b"OK START_UPLOAD\n")

                size_line = recv_text(conn, 5.0)
                file_size = int(size_line)
                file_id = add_file(cid, filename, file_size, "UPLOADING")
                current_action["file_id"] = file_id
                attach_file_to_action(current_action["action_id"], file_id)

                save_path = os.path.join(folder, filename)
                upload_meta = {"filename": filename, "size": file_size}
                print(f"[NEW UPLOAD] {cid} uploading {filename}")

                conn.send(b"0\n")

                f = open(save_path, "wb")
                h = hashlib.sha256()
                received_now = 0

                while received_now < file_size:
                    action = get_action_by_file(current_action["file_id"])
                    if action and action["status"] == "CANCELED":
                        print(f"[UPLOAD CANCELED] {cid}")
                        f.close()
                        try:
                            os.remove(save_path)
                        except:
                            pass
                        upload_meta = None
                        waiting_for_path = False
                        break

                    part = conn.recv(min(4096, file_size - received_now))
                    if not part:
                        print(f"[INTERRUPTED NEW] {cid}")
                        set_action_status(current_action["action_id"], "INTERRUPTED")
                        waiting_for_path = False
                        break

                    f.write(part)
                    h.update(part)
                    received_now += len(part)
                    update_file_received(file_id, received_now)

                f.close()

                if received_now < file_size:
                    upload_meta = None
                    continue

                ck_line = recv_text(conn, 2.0)
                client_ck = ck_line.split(" ", 1)[1] if " " in ck_line else ""
                server_ck = h.hexdigest()

                if client_ck != server_ck:
                    update_file_status(file_id, "CANCELED")
                    set_action_status(current_action["action_id"], "CANCELED")
                    conn.send(b"ERROR CHECKSUM MISMATCH\n")
                    waiting_for_path = False
                    upload_meta = None
                    continue

                finish_file_upload(file_id, server_ck)
                set_action_status(current_action["action_id"], "DONE")
                conn.send(b"\nUpload completed!\n")

                upload_meta = None
                waiting_for_path = False
                last_seen[cid] = time.time()
                continue

            # ========== DOWNLOAD ==========
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
