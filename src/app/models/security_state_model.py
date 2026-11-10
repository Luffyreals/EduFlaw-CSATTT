import time

from app.utils.db_helper import get_db_cursor

# Trạng thái chống dò mật khẩu/OTP lưu trong CSDL (không phải RAM) để đúng khi chạy nhiều worker
# và không mất khi khởi động lại. Thời gian là epoch giây dạng số thực.
LOGIN_ATTEMPT_RETENTION_SECONDS = 86400


class SecurityState:
    # ---- Khóa đăng nhập ----

    @staticmethod
    def lockout_until(key):
        """Thời điểm khóa kết thúc (0 nếu chưa bị khóa)"""
        with get_db_cursor() as cursor:
            cursor.execute("SELECT lockout_until FROM login_attempts WHERE throttle_key = %s", (key[:255],))
            row = cursor.fetchone()
        return float(row[0]) if row else 0.0

    @staticmethod
    def register_failure(key, max_attempts, lockout_seconds):
        """Ghi nhận một lần sai; trả về True nếu khóa tạm thời vừa được kích hoạt"""
        key = key[:255]
        now = time.time()
        with get_db_cursor(commit=True) as cursor:
            # Tăng bằng một câu lệnh nguyên tử để nhiều worker không ghi đè số lần của nhau
            cursor.execute(
                "INSERT INTO login_attempts (throttle_key, attempts, lockout_until, updated_at) "
                "VALUES (%s, 1, 0, %s) "
                "ON DUPLICATE KEY UPDATE attempts = attempts + 1, updated_at = VALUES(updated_at)",
                (key, now)
            )
            cursor.execute("SELECT attempts FROM login_attempts WHERE throttle_key = %s", (key,))
            row = cursor.fetchone()
            if row and int(row[0]) >= max_attempts:
                cursor.execute(
                    "UPDATE login_attempts SET attempts = 0, lockout_until = %s WHERE throttle_key = %s",
                    (now + lockout_seconds, key)
                )
                return True
        return False

    @staticmethod
    def clear_failures(*keys):
        keys = [key[:255] for key in keys]
        if not keys:
            return
        placeholders = ', '.join(['%s'] * len(keys))
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(f"DELETE FROM login_attempts WHERE throttle_key IN ({placeholders})", tuple(keys))

    @staticmethod
    def purge_login_attempts():
        cutoff = time.time() - LOGIN_ATTEMPT_RETENTION_SECONDS
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM login_attempts WHERE updated_at < %s AND lockout_until < %s", (cutoff, time.time()))

    # ---- OTP ----

    @staticmethod
    def create_otp(otp_id, username, personal_email, otp_hash, expires_at):
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO otp_requests (otp_id, username, personal_email, otp_hash, expires_at, attempts) "
                "VALUES (%s, %s, %s, %s, %s, 0)",
                (otp_id, username, personal_email, otp_hash, expires_at)
            )

    @staticmethod
    def get_otp(otp_id):
        if not otp_id:
            return None
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT username, personal_email, otp_hash, expires_at, attempts FROM otp_requests WHERE otp_id = %s",
                (otp_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def increment_otp_attempts(otp_id):
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("UPDATE otp_requests SET attempts = attempts + 1 WHERE otp_id = %s", (otp_id,))

    @staticmethod
    def delete_otp(otp_id):
        if not otp_id:
            return
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM otp_requests WHERE otp_id = %s", (otp_id,))

    @staticmethod
    def record_send(username, sent_at):
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("INSERT INTO otp_send_log (username, sent_at) VALUES (%s, %s)", (username, sent_at))

    @staticmethod
    def recent_sends(username, since):
        """Các thời điểm đã gửi OTP cho tài khoản kể từ `since`, tăng dần"""
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT sent_at FROM otp_send_log WHERE username = %s AND sent_at >= %s ORDER BY sent_at",
                (username, since)
            )
            return [float(row[0]) for row in cursor.fetchall()]

    @staticmethod
    def purge_otp(now, send_window):
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM otp_requests WHERE expires_at < %s", (now,))
            cursor.execute("DELETE FROM otp_send_log WHERE sent_at < %s", (now - send_window,))
