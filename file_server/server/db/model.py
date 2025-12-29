from datetime import datetime
from db.database import get_connection


# UI_USERS
def create_user(username, password_hash, role):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ui_users (username, password_hash, role)
        VALUES (?, ?, ?)
        """,
        (username, password_hash, role),
    )
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ui_users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM ui_users")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# CLIENTS
def add_client(client_id, password_hash, capacity_max, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO clients (client_id, password_hash, capacity_max, user_id, status)
        VALUES (?, ?, ?, ?, 'OFFLINE')
        """,
        (client_id, password_hash, capacity_max, user_id),
    )
    conn.commit()
    conn.close()


def update_client_status(client_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE clients
        SET status = ?
        WHERE client_id = ?
        """,
        (status, client_id),
    )
    conn.commit()
    conn.close()


def get_client(client_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_client(client_id, password_hash, capacity_max, user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE clients
        SET password_hash=?
        WHERE client_id=?
    """,
        (password_hash, client_id),
    )

    conn.commit()
    conn.close()


def delete_client(client_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE client_id=?", (client_id,))
    conn.commit()
    conn.close()


def list_clients():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            c.client_id,
            c.capacity_max,
            c.status,
            u.username,
            u.user_id
        FROM clients c
        JOIN ui_users u ON c.user_id = u.user_id
    """
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_clients_by_user(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            c.client_id,
            c.capacity_max,
            c.status,
            u.username,
            u.user_id
        FROM clients c
        JOIN ui_users u ON c.user_id = u.user_id
        WHERE u.username = ?
    """,
        (username,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# FILES
def add_file(client_id, filename, size, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO files (client_id, filename, size, upload_time, status)
        VALUES (?, ?, ?, datetime('now'), ?)
    """, (client_id, filename, size, status))
    
    file_id = cur.lastrowid
    conn.commit()
    conn.close()
    return file_id


def update_file_status(file_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE files
        SET status = ?
        WHERE file_id = ?
        """,
        (status, file_id),
    )
    conn.commit()
    conn.close()


def get_files_by_client(client_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM files
        WHERE client_id = ?
        """,
        (client_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_file(file_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE file_id = ?", (file_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_file_progress(file_id, progress):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE files
        SET status='UPLOADING', size=?
        WHERE file_id=?
    """,
        (progress, file_id),
    )
    conn.commit()
    conn.close()


def finish_file_upload(file_id, real_size):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE files
        SET status='UPLOADED', size=?, upload_time=datetime('now')
        WHERE file_id=?
    """,
        (real_size, file_id),
    )
    conn.commit()
    conn.close()


def delete_file(file_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM files WHERE file_id=?", (file_id,))
    conn.commit()
    conn.close()


# ACTIONS
def create_action(client_id, file_id, action_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO actions (client_id, file_id, action_type, status)
        VALUES (?, ?, ?, 'PENDING')
    """,
        (client_id, file_id, action_type),
    )
    conn.commit()
    conn.close()


def set_action_status(action_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE actions
        SET status = ?
        WHERE action_id = ?
    """,
        (status, action_id),
    )
    conn.commit()
    conn.close()


def mark_action_running(action_id):
    """Client has started handling the request."""
    set_action_status(action_id, "RUNNING")


def mark_action_done(action_id):
    """Client confirms upload or download is complete."""
    set_action_status(action_id, "DONE")


def mark_action_canceled(action_id):
    """Action aborted by UI or Client."""
    set_action_status(action_id, "CANCELED")


def get_action(action_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM actions WHERE action_id=?", (action_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_action(action_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM actions WHERE action_id=?", (action_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_action_by_file(file_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM actions WHERE file_id=?", (file_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_actions_by_client(client_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM actions
        WHERE client_id = ?
        AND status IN ('PENDING', 'RUNNING')
    """,
        (client_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cancel_upload_action(action_id, file_id):
    mark_action_canceled(action_id)
    update_file_status(file_id, "CANCELED")
