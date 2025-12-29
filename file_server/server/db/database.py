import sqlite3
import os

DB_PATH = os.getenv("DATA_DB_PATH", "data/data.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ui_users
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS ui_users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('ADMIN', 'USER'))
    )
    """
    )

    # clients
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS clients (
        client_id TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        capacity_max INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('ONLINE', 'OFFLINE')),
        FOREIGN KEY (user_id) REFERENCES ui_users(user_id)
    )
    """
    )

    # files
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        size INTEGER NOT NULL,
        upload_time DATETIME NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('UPLOADING', 'UPLOADED')),
        FOREIGN KEY (client_id) REFERENCES clients(client_id)
    )
    """
    )

    # actions
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS actions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT NOT NULL,
        file_id INTEGER,
        action_type TEXT NOT NULL CHECK(action_type IN ('UPLOAD', 'DOWNLOAD')),
        status TEXT NOT NULL CHECK(status IN ('PENDING', 'RUNNING', 'DONE', 'CANCELED')),
        progress INTEGER,
        FOREIGN KEY (client_id) REFERENCES clients(client_id),
        FOREIGN KEY (file_id) REFERENCES files(file_id)
    )
    """
    )

    conn.commit()
    conn.close()
