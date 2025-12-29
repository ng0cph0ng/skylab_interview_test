import bcrypt


def verify_password(plain: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu bằng bcrypt."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except:
        return False
