from app.utils.db_helper import get_db_cursor
from app.utils.field_crypto import decrypt_in_rows, encrypt_field
from app.utils.pagination import clamp_page, escape_like
from app.utils.temp_password import issue_temp_password

class StudentProfile:
    @classmethod
    def get_student_profile(cls, username):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT p.*, u.username, u.personal_email, u.is_active
                    FROM student_profiles p
                    JOIN users u ON p.user_id = u.id
                    WHERE u.username = %s
                """
                cursor.execute(sql, (username,))
                result = cursor.fetchone()
                if result and result.get('date_of_birth'):
                    if hasattr(result['date_of_birth'], 'strftime'):
                        result['date_of_birth'] = result['date_of_birth'].strftime('%Y-%m-%d')
                    else:
                        result['date_of_birth'] = str(result['date_of_birth']).split(' ')[0]
                return decrypt_in_rows(result, 'id_card')
        except Exception:
            return None

    @classmethod
    def get_overview_stats(cls):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT m.id as major_id, m.major_name as major, m.max_students_per_cohort as max_students, COUNT(p.id) as total_students
                    FROM majors m
                    LEFT JOIN student_profiles p ON m.major_name = p.major
                    GROUP BY m.id, m.major_name, m.max_students_per_cohort
                    ORDER BY m.major_name ASC
                """
                cursor.execute(sql)
                stats = cursor.fetchall()
                return stats, sum(item['total_students'] for item in stats)
        except Exception:
            return [], 0

    @classmethod
    def add_major(cls, major_name, major_code, max_students):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "INSERT INTO majors (major_name, major_code, max_students_per_cohort) VALUES (%s, %s, %s)",
                    (major_name, major_code, max_students)
                )
                return True
        except Exception:
            return False

    @classmethod
    def get_classes_summary_by_major(cls, major_name):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT cohort, class_name, COUNT(*) as student_count
                    FROM student_profiles
                    WHERE major = %s
                    GROUP BY cohort, class_name
                    ORDER BY cohort DESC, class_name ASC
                """
                cursor.execute(sql, (major_name,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def get_profiles_by_class(cls, class_name, page=1, per_page=50):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT COUNT(*) as total FROM student_profiles WHERE class_name = %s", (class_name,))
                total_records = cursor.fetchone()['total']
                
                offset = (page - 1) * per_page
                sql = """
                    SELECT p.*, u.username
                    FROM student_profiles p
                    JOIN users u ON p.user_id = u.id
                    WHERE p.class_name = %s
                    ORDER BY p.student_code ASC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (class_name, per_page, offset))
                results = cursor.fetchall()

                decrypt_in_rows(results, 'id_card')
                return results, total_records
        except Exception:
            return [], 0

    @classmethod
    def is_class_assigned_to_advisor(cls, class_name, advisor_email):
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM student_profiles WHERE class_name = %s AND advisor_email = %s LIMIT 1",
                    (class_name, advisor_email)
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    @classmethod
    def is_student_assigned_to_advisor(cls, username, advisor_email):
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1
                    FROM student_profiles p
                    JOIN users u ON p.user_id = u.id
                    WHERE u.username = %s AND p.advisor_email = %s
                    LIMIT 1
                    """,
                    (username, advisor_email)
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    @classmethod
    def update_student_profile(cls, username, update_data):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                
                if 'dob' in update_data:
                     dob_val = update_data.pop('dob')
                     if dob_val:
                         update_data['date_of_birth'] = dob_val

                valid_data = {k: v for k, v in update_data.items() if v is not None}
                if not user or not valid_data:
                    return False

                if 'id_card' in valid_data:
                    valid_data['id_card'] = encrypt_field(valid_data['id_card'])  # CCCD lưu dạng mã hóa

                set_clause = ", ".join([f"{k} = %s" for k in valid_data.keys()])
                values = list(valid_data.values()) + [user[0]]
                
                sql = f"UPDATE student_profiles SET {set_clause} WHERE user_id = %s"
                cursor.execute(sql, values)
                return True
        except Exception:
            return False

    @classmethod
    def update_student_contact(cls, user_id, phone_number, current_address):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE student_profiles SET phone_number = %s, current_address = %s WHERE user_id = %s",
                    (phone_number, current_address, user_id)
                )
                return True
        except Exception:
            return False

    @classmethod
    def delete_student_profile(cls, username):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if not user:
                    return False
                
                user_id = user[0]

                cursor.execute(
                    "DELETE FROM grade_audit_logs WHERE grade_id IN (SELECT id FROM grades WHERE student_id = %s)", 
                    (user_id,)
                )
                
                cursor.execute("DELETE FROM grades WHERE student_id = %s", (user_id,))
                
                cursor.execute("DELETE FROM student_profiles WHERE user_id = %s", (user_id,))
                
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                
                return True
        except Exception:
            return False

    @classmethod
    def add_student_profile(cls, data):
        """Tạo tài khoản sinh viên với mật khẩu tạm ngẫu nhiên; trả về (username, mật khẩu tạm) hoặc None nếu thất bại"""
        temp_password, password_hash = issue_temp_password()
        try:
            with get_db_cursor(commit=True) as cursor:
                username = f"{data['student_code'].lower()}@eduflaw.com"
                cursor.execute(
                    "INSERT INTO users (username, password, role, must_change_password) VALUES (%s, %s, 'student', TRUE)",
                    (username, password_hash)
                )
                user_id = cursor.lastrowid
                sql = """
                    INSERT INTO student_profiles
                    (user_id, student_code, full_name, date_of_birth, gender, major, cohort, class_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    user_id, data['student_code'], data['full_name'], data['dob'],
                    data['gender'], data['major'], data['cohort'], data['class_name']
                )
                cursor.execute(sql, values)
                return username, temp_password
        except Exception:
            return None

    @classmethod
    def delete_major(cls, major_name):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT COUNT(*) FROM student_profiles WHERE major = %s", (major_name,))
                if cursor.fetchone()[0] > 0:
                    return False, "Không thể xóa ngành đang có sinh viên. Hãy chuyển hoặc xóa sinh viên trước."
                    
                cursor.execute("DELETE FROM majors WHERE major_name = %s", (major_name,))
                return True, "Xóa ngành thành công."
        except Exception:
            return False, "Lỗi CSDL."

    @classmethod
    def get_major_name_by_code(cls, major_code):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT major_name FROM majors WHERE major_code = %s", (major_code,))
                result = cursor.fetchone()
                return result['major_name'] if result else None
        except Exception:
            return None

    @classmethod
    def update_major(cls, major_id, new_name, new_quota):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT major_name FROM majors WHERE id = %s", (major_id,))
                existing = cursor.fetchone()
                if not existing:
                    return False, 'Không tìm thấy ngành cần cập nhật.'

                old_name = existing[0]
                cursor.execute(
                    "UPDATE majors SET major_name = %s, max_students_per_cohort = %s WHERE id = %s",
                    (new_name, new_quota, major_id)
                )
                if old_name != new_name:
                    cursor.execute(
                        "UPDATE student_profiles SET major = %s WHERE major = %s",
                        (new_name, old_name)
                    )
                return True, f'Đã cập nhật ngành {new_name}.'
        except Exception:
            return False, 'Không thể cập nhật ngành. Hãy kiểm tra mã ngành có bị trùng không.'


    @classmethod
    def get_classes_by_advisor(cls, advisor_email):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT major, cohort, class_name, COUNT(*) as student_count
                    FROM student_profiles
                    WHERE advisor_email = %s
                    GROUP BY major, cohort, class_name
                    ORDER BY cohort DESC, class_name ASC
                """
                cursor.execute(sql, (advisor_email,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def assign_advisor_to_class(cls, class_name, advisor_email, advisor_name):
        try:
            with get_db_cursor(commit=True) as cursor:
                sql = """
                    UPDATE student_profiles
                    SET advisor_email = %s, advisor_name = %s
                    WHERE class_name = %s
                """
                cursor.execute("SELECT 1 FROM student_profiles WHERE class_name = %s LIMIT 1", (class_name,))
                if not cursor.fetchone():
                    return False
                cursor.execute(sql, (advisor_email, advisor_name, class_name))
                return True
        except Exception:
            return False

    @classmethod
    def search_global_students(cls, keyword, page=1, per_page=20):
        """Tìm sinh viên theo mã/họ tên/lớp; trả về (rows, total, page) với page đã đưa về khoảng hợp lệ"""
        try:
            with get_db_cursor(dictionary=True) as cursor:
                search_pattern = f"%{escape_like(keyword)}%"

                count_sql = """
                    SELECT COUNT(*) as total
                    FROM student_profiles p
                    WHERE p.student_code LIKE %s OR p.full_name LIKE %s OR p.class_name LIKE %s
                """
                cursor.execute(count_sql, (search_pattern, search_pattern, search_pattern))
                total_records = cursor.fetchone()['total']

                page = clamp_page(page, per_page, total_records)
                sql = """
                    SELECT p.*, u.username as email, u.is_active
                    FROM student_profiles p
                    JOIN users u ON p.user_id = u.id
                    WHERE p.student_code LIKE %s OR p.full_name LIKE %s OR p.class_name LIKE %s
                    ORDER BY p.class_name, p.student_code
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (search_pattern, search_pattern, search_pattern, per_page, (page - 1) * per_page))
                return decrypt_in_rows(cursor.fetchall(), 'id_card'), total_records, page
        except Exception:
            return [], 0, 1

    @classmethod
    def get_advisor_dashboard_stats(cls, advisor_email):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as total_students FROM student_profiles WHERE advisor_email = %s",
                    (advisor_email,)
                )
                result = cursor.fetchone()
                return result['total_students'] if result else 0
        except Exception:
            return 0