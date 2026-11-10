import hashlib
import hmac
import mysql.connector
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.db_helper import get_db_cursor
from app.utils.password_policy import validate_password_strength
from app.utils.temp_password import LEGACY_DEFAULT_PASSWORD, issue_temp_password

# Hash giả (tính một lần lúc import) để so khớp khi tài khoản không tồn tại/đã khóa, giữ thời gian phản hồi
# của đăng nhập đồng đều với tài khoản thật đã băm mật khẩu — xem User.verify_login_password.
_DUMMY_PASSWORD_HASH = generate_password_hash('eduflaw-timing-equalizer-decoy')


class User:
    def __init__(self, id, username, password, role, is_active=True, personal_email=None, must_change_password=False):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.is_active = bool(is_active)
        self.personal_email = personal_email
        self.must_change_password = bool(must_change_password)

    @staticmethod
    def verify_password(stored_password, candidate_password):
        if not isinstance(stored_password, str) or not isinstance(candidate_password, str):
            return False
        if stored_password.startswith(('scrypt:', 'pbkdf2:')):
            return check_password_hash(stored_password, candidate_password)
        return hmac.compare_digest(stored_password, candidate_password)

    @classmethod
    def verify_login_password(cls, user, candidate_password):
        """Xác minh mật khẩu đăng nhập với thời gian phản hồi đồng đều.

        Khi tài khoản không tồn tại hoặc đã bị khóa, vẫn thực hiện một phép so khớp với hash giả rồi trả về False,
        để thời gian phản hồi không tiết lộ tài khoản có tồn tại hay không (chống dò tài khoản bằng thời gian — A07).
        """
        if user and user.is_active:
            return cls.verify_password(user.password, candidate_password)
        cls.verify_password(_DUMMY_PASSWORD_HASH, candidate_password if isinstance(candidate_password, str) else '')
        return False

    @staticmethod
    def is_password_hashed(password):
        return isinstance(password, str) and password.startswith(('scrypt:', 'pbkdf2:'))

    @classmethod
    def uses_legacy_default_password(cls, password):
        """Mật khẩu mặc định dùng chung của phiên bản cũ: đoán được nên không còn được chấp nhận để đăng nhập"""
        return cls.verify_password(password, LEGACY_DEFAULT_PASSWORD)

    def needs_onboarding(self):
        """Đang dùng mật khẩu tạm do nhà trường cấp, hoặc sinh viên/giảng viên chưa liên kết Gmail cá nhân"""
        return self.must_change_password or (self.role in ('student', 'admin') and not self.personal_email)

    @staticmethod
    def password_fingerprint(password_hash):
        """Dấu vân tay của mật khẩu đang dùng, lưu trong session (cookie chỉ ký, không mã hóa nên không lưu hash thật).

        Đổi mật khẩu, quên mật khẩu hay được cấp mật khẩu tạm mới đều làm dấu vân tay đổi,
        nên mọi phiên đăng nhập cũ trên các máy khác mất hiệu lực ở request kế tiếp.
        """
        key = (current_app.config.get('SECRET_KEY') or '').encode()
        return hmac.new(key, (password_hash or '').encode(), hashlib.sha256).hexdigest()[:32]

    @classmethod
    def current_password_fingerprint(cls, user_id):
        """Dấu vân tay mật khẩu hiện tại trong CSDL: dùng để giữ phiên của chính người vừa đổi mật khẩu"""
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                return cls.password_fingerprint(user['password']) if user else ''
        except Exception:
            return ''

    @classmethod
    def is_account_active(cls, user_id, role, password_fp=None):
        """Kiểm tra tài khoản trong session vẫn tồn tại, chưa bị khóa, đúng vai trò và (nếu truyền password_fp)
        mật khẩu chưa bị đổi kể từ lúc đăng nhập. Lỗi CSDL => từ chối."""
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT is_active, role, password FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not (user and user['is_active'] and user['role'] == role):
                    return False
                if password_fp is None:
                    return True
                return hmac.compare_digest(password_fp, cls.password_fingerprint(user['password']))
        except Exception:
            return False

    @classmethod
    def upgrade_legacy_password(cls, user_id, password):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE users SET password = %s WHERE id = %s AND password = %s",
                    (generate_password_hash(password), user_id, password)
                )
                return cursor.rowcount > 0
        except Exception:
            return False

    @classmethod
    def get_user_by_username(cls, username):
        user_data = None
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT id, username, password, role, is_active, personal_email, must_change_password FROM users WHERE username = %s",
                    (username,)
                )
                user_data = cursor.fetchone()
        except Exception:
            try:
                with get_db_cursor(dictionary=True) as cursor:
                    cursor.execute(
                        "SELECT id, username, password, role, is_active FROM users WHERE username = %s",
                        (username,)
                    )
                    user_data = cursor.fetchone()
            except Exception:
                pass

        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                password=user_data['password'],
                role=user_data['role'],
                is_active=user_data['is_active'],
                personal_email=user_data.get('personal_email'),
                must_change_password=user_data.get('must_change_password')
            )
        return None

    @classmethod
    def get_all_students(cls):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, username FROM users WHERE role = 'student'")
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def complete_onboarding(cls, user_id, personal_email, new_password):
        strong, strength_message = validate_password_strength(new_password)
        if not strong:
            return False, strength_message

        try:
            with get_db_cursor(dictionary=True, commit=True) as cursor:
                cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return False, "Lỗi: Không tìm thấy tài khoản người dùng."
                if cls.verify_password(user['password'], new_password):
                    return False, "Mật khẩu mới không được trùng với mật khẩu tạm thời được cấp."

                hashed_password = generate_password_hash(new_password)
                cursor.execute(
                    "UPDATE users SET password = %s, personal_email = %s, must_change_password = FALSE WHERE id = %s",
                    (hashed_password, personal_email.strip().lower(), user_id)
                )
            return True, "Kích hoạt tài khoản và đổi mật khẩu mới thành công!"
        except mysql.connector.IntegrityError:
            # Ràng buộc UNIQUE uq_users_personal_email: Gmail đã thuộc về tài khoản khác
            return False, "Địa chỉ Gmail này đã được liên kết với một tài khoản khác trong hệ thống."
        except Exception:
            return False, "Lỗi hệ thống máy chủ cơ sở dữ liệu."

    @classmethod
    def change_password(cls, user_id, current_password, new_password):
        strong, strength_message = validate_password_strength(new_password)
        if not strong:
            return False, strength_message

        try:
            with get_db_cursor(dictionary=True, commit=True) as cursor:
                cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()

                if not user:
                    return False, "Lỗi: Không tìm thấy tài khoản người dùng."

                if not cls.verify_password(user['password'], current_password):
                    return False, "Mật khẩu hiện tại không chính xác!"

                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))

            return True, "Đổi mật khẩu bảo mật thành công! Vui lòng dùng mật khẩu mới cho lần đăng nhập sau."
        except Exception:
            return False, "Lỗi hệ thống máy chủ cơ sở dữ liệu."

    @classmethod
    def reset_student_password(cls, username):
        """Cấp mật khẩu tạm ngẫu nhiên mới; trả về mật khẩu tạm (chỉ để hiển thị một lần) hoặc None nếu thất bại"""
        temp_password, password_hash = issue_temp_password()
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE users SET password = %s, personal_email = NULL, must_change_password = TRUE "
                    "WHERE username = %s AND role = 'student'",
                    (password_hash, username)
                )
                return temp_password if cursor.rowcount > 0 else None
        except Exception:
            return None