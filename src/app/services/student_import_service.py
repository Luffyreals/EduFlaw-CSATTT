import re

import mysql.connector

from app.utils.temp_password import issue_temp_password
from db import db_pool


class StudentImportService:
    REQUIRED_FIELDS = ('Email', 'MaSV', 'HoTen', 'Lop', 'Nganh')
    MAX_ROWS = 5000
    BATCH_SIZE = 1000

    @classmethod
    def import_rows(cls, rows):
        """
        Trả về (số sinh viên đã import, danh sách lỗi, danh sách mật khẩu tạm).
        Mỗi sinh viên nhận một mật khẩu tạm ngẫu nhiên riêng, chỉ trả về một lần cho Master (file Excel).
        """
        if not rows:
            return 0, ['Tệp không có dữ liệu sinh viên.'], []
        if len(rows) > cls.MAX_ROWS:
            return 0, [f'Mỗi lần chỉ được import tối đa {cls.MAX_ROWS} sinh viên.'], []

        normalized_rows = []
        errors = []
        seen_emails = set()
        seen_student_codes = set()

        for row_number, row in enumerate(rows, start=2):
            email = str(row.get('Email', '')).strip().lower()
            student_code = str(row.get('MaSV', '')).strip().upper()
            full_name = str(row.get('HoTen', '')).strip()
            class_name = str(row.get('Lop', '')).strip()
            major = str(row.get('Nganh', '')).strip()

            missing_fields = [
                field for field, value in (
                    ('Email', email), ('MaSV', student_code), ('HoTen', full_name),
                    ('Lop', class_name), ('Nganh', major)
                ) if not value
            ]
            if missing_fields:
                errors.append(f'Dòng {row_number}: thiếu {", ".join(missing_fields)}.')
                continue

            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                errors.append(f'Dòng {row_number}: email không hợp lệ.')
                continue
            if not re.fullmatch(r'B\d{2}DC[A-Z0-9]{2}\d+', student_code):
                errors.append(f'Dòng {row_number}: mã sinh viên không đúng định dạng.')
                continue
            if email in seen_emails or student_code in seen_student_codes:
                errors.append(f'Dòng {row_number}: email hoặc mã sinh viên bị trùng trong tệp.')
                continue

            seen_emails.add(email)
            seen_student_codes.add(student_code)
            normalized_rows.append({
                'email': email,
                'student_code': student_code,
                'full_name': full_name,
                'class_name': class_name,
                'major': major,
                'cohort': f'D{student_code[1:3]}'
            })

        if errors:
            return 0, errors, []

        connection = cursor = None
        try:
            connection = db_pool.get_connection()
            cursor = connection.cursor()
            emails = [row['email'] for row in normalized_rows]
            student_codes = [row['student_code'] for row in normalized_rows]
            major_names = sorted({row['major'] for row in normalized_rows})

            cursor.execute(
                f"SELECT username FROM users WHERE username IN ({', '.join(['%s'] * len(emails))})",
                tuple(emails)
            )
            existing_emails = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                f"SELECT student_code FROM student_profiles WHERE student_code IN ({', '.join(['%s'] * len(student_codes))})",
                tuple(student_codes)
            )
            existing_codes = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                f"SELECT major_name FROM majors WHERE major_name IN ({', '.join(['%s'] * len(major_names))})",
                tuple(major_names)
            )
            known_majors = {row[0] for row in cursor.fetchall()}

            conflicts = []
            for row_number, row in enumerate(normalized_rows, start=2):
                if row['email'] in existing_emails:
                    conflicts.append(f'Dòng {row_number}: email đã tồn tại ({row["email"]}).')
                if row['student_code'] in existing_codes:
                    conflicts.append(f'Dòng {row_number}: mã sinh viên đã tồn tại ({row["student_code"]}).')
                if row['major'] not in known_majors:
                    conflicts.append(f'Dòng {row_number}: ngành không tồn tại ({row["major"]}).')
            if conflicts:
                return 0, conflicts, []

            credentials = []
            user_rows = []
            for row in normalized_rows:
                temp_password, password_hash = issue_temp_password()
                user_rows.append((row['email'], password_hash))
                credentials.append({
                    'username': row['email'],
                    'full_name': row['full_name'],
                    'role': 'student',
                    'password': temp_password
                })

            # Chèn theo lô (executemany gộp thành INSERT nhiều dòng) thay vì 2 câu lệnh mỗi sinh viên:
            # với CSDL ở xa, import 5000 sinh viên từng dòng một mất hàng chục phút
            user_ids = {}
            for start in range(0, len(normalized_rows), cls.BATCH_SIZE):
                batch_users = user_rows[start:start + cls.BATCH_SIZE]
                cursor.executemany(
                    "INSERT INTO users (username, password, role, must_change_password) VALUES (%s, %s, 'student', TRUE)",
                    batch_users
                )
                usernames = [username for username, _ in batch_users]
                # AUTO_INCREMENT (đặc biệt trên TiDB) không bảo đảm liên tiếp nên đọc lại id theo username
                cursor.execute(
                    f"SELECT id, username FROM users WHERE username IN ({', '.join(['%s'] * len(usernames))})",
                    tuple(usernames)
                )
                user_ids.update({username: user_id for user_id, username in cursor.fetchall()})

            profile_rows = [
                (
                    user_ids[row['email']], row['student_code'], row['full_name'], row['major'],
                    row['cohort'], row['class_name']
                )
                for row in normalized_rows
            ]
            for start in range(0, len(profile_rows), cls.BATCH_SIZE):
                cursor.executemany(
                    """
                    INSERT INTO student_profiles
                    (user_id, student_code, full_name, major, cohort, class_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    profile_rows[start:start + cls.BATCH_SIZE]
                )

            connection.commit()
            return len(normalized_rows), [], credentials
        except mysql.connector.Error as err:
            if connection: connection.rollback()
            print(f'Lỗi import sinh viên: {err}')
            return 0, ['Không thể lưu dữ liệu. Hãy kiểm tra cấu trúc cơ sở dữ liệu và thử lại.'], []
        finally:
            if cursor: cursor.close()
            if connection: connection.close()