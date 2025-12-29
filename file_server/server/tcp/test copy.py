import os, sys, socket, bcrypt

BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
sys.path.append(BASE_DIR)

from db.model import get_client

HOST = "0.0.0.0"
PORT = 8000

def start_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[TCP] Listening on {HOST}:{PORT}...")

    while True:
        conn, addr = server.accept()
        print(f"[CONNECTED] {addr}")

        data = conn.recv(1024).decode().strip()
        
        if data.startswith("LOGIN"):
            _, cid, pwd = data.split(" ", 2)
            client = get_client(cid)

            if client and bcrypt.checkpw(pwd.encode(), client["password_hash"].encode()):
                conn.sendall(b"OK AUTHORIZED\n")
            else:
                conn.sendall(b"ERROR INVALID_CREDENTIALS\n")
        else:
            conn.sendall(b"ERROR UNKNOWN_COMMAND\n")

        conn.close()

if __name__ == "__main__":
    start_tcp_server()
