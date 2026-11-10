from app.utils.db_helper import get_db_cursor
from app.utils.field_crypto import decrypt_in_rows, encrypt_field
from app.utils.pagination import escape_like, clamp_page
from app.utils.temp_password import issue_temp_password


def _clean(value):
    """Bỏ khoảng trắng hai đầu; chuỗi rỗng thành NULL (cột DATE ở strict mode từ chối '' và ô trống không bị lưu thành '')"""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


class StaffProfile:
    @classmethod
    def get_admin_profile(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT full_name, id_card, phone_number, date_of_birth, gender, address FROM admin_profiles WHERE user_id = %s",
                    (user_id,)
                )
                return decrypt_in_rows(cursor.fetchone(), 'id_card')
        except Exception:
            return None

    @classmethod
    def get_master_profile(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT full_name, id_card, phone_number, date_of_birth, gender, address FROM master_profiles WHERE user_id = %s",
                    (user_id,)
                )
                return decrypt_in_rows(cursor.fetchone(), 'id_card')
        except Exception:
            return None

    @classmethod
    def update_master_profile(cls, user_id, full_name, phone_number, dob, gender, address, id_card=None):
        full_name, phone_number, dob, gender, address, id_card = map(_clean, (full_name, phone_number, dob, gender, address, id_card))
        if not full_name:
            return False
        id_card = encrypt_field(id_card)  # CCCD lưu dạng mã hóa
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT id FROM master_profiles WHERE user_id = %s", (user_id,))
                exists = cursor.fetchone()

                if exists:
                    sql = """
                        UPDATE master_profiles 
                        SET full_name = %s, id_card = %s, phone_number = %s, date_of_birth = %s, gender = %s, address = %s 
                        WHERE user_id = %s
                    """
                    cursor.execute(sql, (full_name, id_card, phone_number, dob, gender, address, user_id))
                else:
                    sql = """
                        INSERT INTO master_profiles (user_id, full_name, id_card, phone_number, date_of_birth, gender, address) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (user_id, full_name, id_card, phone_number, dob, gender, address))

                return True
        except Exception:
            return False

    @classmethod
    def search_admins(cls, keyword='', status=None, page=1, per_page=20):
        """
        Tìm và phân trang giảng viên phía máy chủ. keyword khớp họ tên, email hoặc số điện thoại;
        status là 1 (đang hoạt động), 0 (đã khóa) hoặc None (tất cả).
        Trả về (danh sách giảng viên của trang, tổng số khớp, số trang thực tế sau khi giới hạn).
        """
        conditions = ["u.role = 'admin'"]
        params = []
        if keyword:
            pattern = f"%{escape_like(keyword)}%"
            conditions.append("(a.full_name LIKE %s OR u.username LIKE %s OR a.phone_number LIKE %s)")
            params.extend([pattern] * 3)
        if status in (0, 1):
            conditions.append("u.is_active = %s")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions)
        from_clause = " FROM users u LEFT JOIN admin_profiles a ON u.id = a.user_id"

        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT COUNT(*) as total" + from_clause + where, tuple(params))
                total = cursor.fetchone()['total']
                page = clamp_page(page, per_page, total)

                cursor.execute(
                    """
                    SELECT u.id as user_id, u.username as email, u.is_active, a.full_name,
                           a.id_card, a.phone_number, a.date_of_birth, a.gender, a.address
                    """ + from_clause + where + " ORDER BY u.id ASC LIMIT %s OFFSET %s",
                    tuple(params) + (per_page, (page - 1) * per_page)
                )
                results = cursor.fetchall()
                for result in results:
                    if result.get('date_of_birth') and hasattr(result['date_of_birth'], 'strftime'):
                        result['date_of_birth'] = result['date_of_birth'].strftime('%Y-%m-%d')
                decrypt_in_rows(results, 'id_card')
                return results, total, page
        except Exception:
            return [], 0, 1

    @classmethod
    def get_admin_options(cls):
        """Danh sách rút gọn (email, họ tên) các giảng viên đang hoạt động cho dropdown phân công"""
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT u.username as email, a.full_name
                    FROM users u
                    LEFT JOIN admin_profiles a ON u.id = a.user_id
                    WHERE u.role = 'admin' AND u.is_active = TRUE
                    ORDER BY a.full_name ASC, u.username ASC
                    """
                )
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def update_admin_profile_by_self(cls, user_id, full_name, id_card, phone_number, dob, gender, address):
        """
        Giảng viên tự cập nhật hồ sơ: chỉ đổi được liên lạc (SĐT, địa chỉ). Họ tên, CCCD, ngày sinh, giới tính
        do Master quản lý, giảng viên chỉ được điền khi đang trống.
        Trả về họ tên được lưu, hoặc None nếu lưu thất bại.
        """
        current = cls.get_admin_profile(user_id) or {}
        official = {
            'full_name': current.get('full_name') or full_name,
            'id_card': current.get('id_card') or id_card,
            'date_of_birth': current.get('date_of_birth') or dob or None,
            'gender': current.get('gender') or gender
        }
        saved = cls.update_admin_profile_by_master(
            user_id, official['full_name'], official['id_card'], phone_number,
            official['date_of_birth'], official['gender'], address
        )
        return official['full_name'] if saved else None

    @classmethod
    def update_admin_profile_by_master(cls, user_id, full_name, id_card, phone_number, dob, gender, address):
        full_name, id_card, phone_number, dob, gender, address = map(_clean, (full_name, id_card, phone_number, dob, gender, address))
        if not full_name:
            return False
        id_card = encrypt_field(id_card)  # CCCD lưu dạng mã hóa
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT id FROM admin_profiles WHERE user_id = %s", (user_id,))
                exists = cursor.fetchone()

                if exists:
                    sql = "UPDATE admin_profiles SET full_name = %s, id_card = %s, phone_number = %s, date_of_birth = %s, gender = %s, address = %s WHERE user_id = %s"
                    cursor.execute(sql, (full_name, id_card, phone_number, dob, gender, address, user_id))
                else:
                    sql = "INSERT INTO admin_profiles (user_id, full_name, id_card, phone_number, date_of_birth, gender, address) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    cursor.execute(sql, (user_id, full_name, id_card, phone_number, dob, gender, address))

                return True
        except Exception:
            return False

    @classmethod
    def create_admin_account(cls, email, full_name):
        """Tạo tài khoản giảng viên với mật khẩu tạm ngẫu nhiên; trả về (thành công, thông báo, mật khẩu tạm hoặc None)"""
        temp_password, password_hash = issue_temp_password()
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (email,))
                if cursor.fetchone():
                    return False, "Email này đã tồn tại trong hệ thống.", None

                cursor.execute(
                    "INSERT INTO users (username, password, role, must_change_password) VALUES (%s, %s, 'admin', TRUE)",
                    (email, password_hash)
                )
                user_id = cursor.lastrowid
                cursor.execute("INSERT INTO admin_profiles (user_id, full_name) VALUES (%s, %s)", (user_id, full_name))
                return True, f"Cấp tài khoản cho giảng viên {full_name} thành công.", temp_password
        except Exception:
            return False, "Lỗi cơ sở dữ liệu.", None

    @classmethod
    def toggle_admin_status(cls, user_id, new_status):
        try:
            with get_db_cursor(commit=True) as cursor:
                # Chỉ áp dụng cho tài khoản Giảng viên, không cho khóa nhầm tài khoản Master/Sinh viên
                cursor.execute("SELECT username FROM users WHERE id = %s AND role = 'admin'", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return False

                cursor.execute("UPDATE users SET is_active = %s WHERE id = %s AND role = 'admin'", (new_status, user_id))

                if new_status == 0:
                    cursor.execute("UPDATE credit_classes SET lecturer_id = NULL WHERE lecturer_id = %s", (user_id,))
                    cursor.execute("UPDATE student_profiles SET advisor_name = NULL, advisor_email = NULL WHERE advisor_email = %s", (user[0],))

                return True
        except Exception:
            return False

    @classmethod
    def reset_admin_password(cls, user_id):
        """Cấp mật khẩu tạm ngẫu nhiên mới cho giảng viên; trả về (username, mật khẩu tạm) hoặc None nếu thất bại"""
        temp_password, password_hash = issue_temp_password()
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT username FROM users WHERE id = %s AND role = 'admin'", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return None

                cursor.execute(
                    "UPDATE users SET password = %s, personal_email = NULL, must_change_password = TRUE "
                    "WHERE id = %s AND role = 'admin'",
                    (password_hash, user_id)
                )
                return (user[0], temp_password) if cursor.rowcount > 0 else None
        except Exception:
            return None
