import math
from decimal import Decimal, ROUND_HALF_UP
from app.utils.db_helper import get_db_cursor
from app.utils.pagination import escape_like, clamp_page

class Grade:
    @staticmethod
    def is_valid_score(value):
        if value is None:
            return True
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(numeric_value) and 0 <= numeric_value <= 10

    @staticmethod
    def validate_weights(weights):
        defaults = {'cc': 10, 'bttl': 0, 'tbkt': 20, 'tgk': 0, 'tnth': 0, 'thi': 70}
        try:
            values = [float(weights.get(key, default)) for key, default in defaults.items()]
        except (TypeError, ValueError):
            return False
        return (
            all(math.isfinite(value) and 0 <= value <= 100 for value in values)
            and math.isclose(sum(values), 100, abs_tol=0.01)
        )

    @staticmethod
    def convert_score(score):
        grade_scale = (
            (9.0, 4.0, 'A+', '#16a34a'),
            (8.5, 3.7, 'A', '#22c55e'),
            (8.0, 3.5, 'B+', '#3b82f6'),
            (7.0, 3.0, 'B', '#3b82f6'),
            (6.5, 2.5, 'C+', '#f59e0b'),
            (5.5, 2.0, 'C', '#f59e0b'),
            (5.0, 1.5, 'D+', '#64748b'),
            (4.0, 1.0, 'D', '#64748b')
        )
        if score is None:
            return {'score_4': None, 'letter': '--', 'color': '#cbd5e1'}
        for threshold, points, letter, color in grade_scale:
            if score >= threshold:
                return {'score_4': points, 'letter': letter, 'color': color}
        return {'score_4': 0.0, 'letter': 'F', 'color': '#ef4444'}

    @classmethod
    def get_credit_classes_by_lecturer(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT c.id, c.class_code, c.subject_name, c.credits, c.semester, c.year,
                           c.weight_cc, c.weight_bttl, c.weight_tbkt, c.weight_tgk, c.weight_tnth, c.weight_thi,
                           c.day_of_week, c.shift, c.room,
                           COUNT(g.id) as enrolled_students
                    FROM credit_classes c
                    LEFT JOIN grades g ON c.id = g.credit_class_id
                    WHERE c.lecturer_id = %s
                    GROUP BY c.id
                    ORDER BY c.year DESC, c.semester DESC
                """
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def get_students_in_credit_class(cls, credit_class_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT g.id as grade_id, u.username, p.full_name, p.student_code, p.class_name, 
                           g.score_cc, g.score_bttl, g.score_tbkt, g.score_tgk, g.score_tnth, g.score_thi, g.score_thi_2,
                           g.score
                    FROM grades g
                    JOIN users u ON g.student_id = u.id
                    JOIN student_profiles p ON u.id = p.user_id
                    WHERE g.credit_class_id = %s
                    ORDER BY p.student_code ASC
                """
                cursor.execute(sql, (credit_class_id,))
                results = cursor.fetchall()
                
                for row in results:
                    row.update(cls.convert_score(row['score']))
                        
                return results
        except Exception:
            return []

    @classmethod
    def update_detailed_grade(cls, grade_id, credit_class_id, data, user_id=None, reason=None):
        return cls.update_detailed_grades(credit_class_id, {str(grade_id): data}, user_id=user_id, reason=reason)

    @classmethod
    def save_single_score(cls, grade_id, credit_class_id, field, value, user_id=None, reason=None):
        """Auto-save một ô điểm: gộp với giá trị mới nhất trong CSDL (dòng bị khóa trong transaction), để hai ô
        lưu gần như cùng lúc không đè mất nhau. Trả về các đầu điểm sau khi lưu, hoặc None nếu thất bại."""
        saved = {}
        ok = cls.update_detailed_grades(
            credit_class_id, {str(grade_id): {field: value}},
            user_id=user_id, reason=reason, partial=True, saved=saved
        )
        return saved.get(str(grade_id)) if ok else None
    
    SCORE_COLUMNS = ('score_cc', 'score_bttl', 'score_tbkt', 'score_tgk', 'score_tnth', 'score_thi', 'score_thi_2', 'score')
    AUDIT_FIELD_NAMES = {
        'score_cc': 'Chuyên cần',
        'score_bttl': 'Bài tập lớn',
        'score_tbkt': 'Trung bình kiểm tra',
        'score_tgk': 'Giữa kỳ',
        'score_tnth': 'Thực hành',
        'score_thi': 'Thi lần 1',
        'score_thi_2': 'Thi lần 2',
        'score': 'Tổng kết hệ 10'
    }

    @staticmethod
    def _score_changed(old_value, new_value):
        if old_value is not None and new_value is not None:
            return abs(float(new_value) - float(old_value)) > 0.01
        return old_value != new_value

    @classmethod
    def update_detailed_grades(cls, credit_class_id, grades_data, user_id=None, reason=None,
                               partial=False, saved=None, **kwargs):
        """
        Lưu điểm của nhiều sinh viên trong một lớp tín chỉ: chỉ cập nhật dòng có thay đổi, bằng một câu UPDATE,
        và ghi nhật ký từng đầu điểm thay đổi bằng một câu INSERT nhiều dòng.

        Các dòng điểm bị khóa (FOR UPDATE) đến hết transaction. partial=True: mỗi dict chỉ chứa các đầu điểm cần đổi,
        phần còn lại lấy từ CSDL. saved (dict): nhận các đầu điểm sau khi lưu của từng dòng.
        """
        if partial and any(set(data) - set(cls.SCORE_COLUMNS[:-1]) for data in grades_data.values()):
            return False
        if not grades_data or any(
            not str(grade_id).isdecimal()
            or not all(cls.is_valid_score(value) for value in data.values())
            for grade_id, data in grades_data.items()
        ):
            return False

        try:
            with get_db_cursor(dictionary=True, commit=True) as cursor:
                cursor.execute("""
                    SELECT weight_cc, weight_bttl, weight_tbkt, weight_tgk, weight_tnth, weight_thi 
                    FROM credit_classes WHERE id = %s
                """, (credit_class_id,))
                weights = cursor.fetchone()
                if not weights or not cls.validate_weights({
                    'cc': weights['weight_cc'], 'bttl': weights['weight_bttl'],
                    'tbkt': weights['weight_tbkt'], 'tgk': weights['weight_tgk'],
                    'tnth': weights['weight_tnth'], 'thi': weights['weight_thi']
                }):
                    return False

                grade_ids = list(grades_data)
                placeholders = ', '.join(['%s'] * len(grade_ids))
                
                cursor.execute(
                    f"SELECT id, score_cc, score_bttl, score_tbkt, score_tgk, score_tnth, score_thi, score_thi_2, score FROM grades WHERE credit_class_id = %s AND id IN ({placeholders}) FOR UPDATE",
                    (credit_class_id, *grade_ids)
                )
                old_grades = {str(row['id']): row for row in cursor.fetchall()}
                
                if set(old_grades.keys()) != {str(grade_id) for grade_id in grade_ids}:
                    return False
                    
                changed_rows = []
                audit_rows = []
                for grade_id, data in grades_data.items():
                    old_data = old_grades[str(grade_id)]
                    if partial:
                        data = {
                            column: data[column] if column in data
                            else (None if old_data.get(column) is None else float(old_data[column]))
                            for column in cls.SCORE_COLUMNS if column != 'score'
                        }
                    new_values = {column: data.get(column) for column in cls.SCORE_COLUMNS if column != 'score'}
                    new_values['score'] = cls.calculate_final_score(data, weights)
                    if saved is not None:
                        saved[str(grade_id)] = new_values

                    changed_columns = [
                        column for column in cls.SCORE_COLUMNS
                        if cls._score_changed(old_data.get(column), new_values[column])
                    ]
                    if not changed_columns:
                        continue

                    changed_rows.append((int(grade_id), new_values))
                    if user_id:
                        for column in changed_columns:
                            old_val, new_val = old_data.get(column), new_values[column]
                            audit_rows.append((
                                int(grade_id), cls.AUDIT_FIELD_NAMES[column],
                                None if old_val is None else float(old_val),
                                None if new_val is None else float(new_val),
                                user_id, reason
                            ))

                if changed_rows:
                    # Một câu UPDATE cho cả lớp (CASE theo id) thay vì mỗi sinh viên một câu:
                    # với CSDL ở xa, mỗi câu lệnh tốn một vòng mạng
                    set_clauses = []
                    params = []
                    for column in cls.SCORE_COLUMNS:
                        set_clauses.append(
                            f"{column} = CASE id " + " ".join(["WHEN %s THEN %s"] * len(changed_rows)) + " END"
                        )
                        for grade_id, new_values in changed_rows:
                            params.extend((grade_id, new_values[column]))
                    id_placeholders = ', '.join(['%s'] * len(changed_rows))
                    cursor.execute(
                        f"UPDATE grades SET {', '.join(set_clauses)} WHERE credit_class_id = %s AND id IN ({id_placeholders})",
                        (*params, credit_class_id, *(grade_id for grade_id, _ in changed_rows))
                    )

                if audit_rows:
                    cls.log_grade_changes(cursor, audit_rows)

                return True
        except Exception:
            return False

    @staticmethod
    def _decimal(value):
        # Đi qua str() để 6.5 là đúng 6.5 (float nhị phân 6.5*0.7 = 4.55 lại thành 4.5499999...)
        return Decimal(str(value))

    @classmethod
    def _round_half_up(cls, value, places):
        """Làm tròn kiểu thông thường (5 thì lên), không phải round() của Python (số thực + làm tròn chẵn)"""
        return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))

    @classmethod
    def calculate_final_score(cls, data, weights):
        exam_scores = [data.get('score_thi'), data.get('score_thi_2')]
        exam_scores = [cls._decimal(score) for score in exam_scores if score is not None]
        if not exam_scores:
            return None

        component_keys = ('cc', 'bttl', 'tbkt', 'tgk', 'tnth')
        total = sum(
            cls._decimal(data.get(f'score_{key}') or 0) * cls._decimal(weights[f'weight_{key}'])
            for key in component_keys
        )
        total += max(exam_scores) * cls._decimal(weights['weight_thi'])
        return cls._round_half_up(total / 100, 1)

    @classmethod
    def get_all_grades_by_student(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT g.*, c.class_code 
                    FROM grades g
                    LEFT JOIN credit_classes c ON g.credit_class_id = c.id
                    WHERE g.student_id = %s
                    ORDER BY g.year ASC, g.semester ASC
                """
                cursor.execute(sql, (user_id,))
                results = cursor.fetchall()

                for row in results:
                    row.update(cls.convert_score(row['score']))
                return results
        except Exception:
            return []

    @classmethod
    def calculate_gpa(cls, grades_list):
        total_credits = 0
        total_score_points = 0
        total_gpa4_points = 0
        total_passed_credits = 0

        for grade in grades_list:
            score = grade.get('score')
            credits = grade.get('credits', 3)
            if score is not None:
                total_credits += credits
                total_score_points += (score * credits)
                grade_points = grade.get('score_4')
                if grade_points is None:
                    grade_points = cls.convert_score(score)['score_4']
                total_gpa4_points += (grade_points * credits)
                if score >= 4.0:
                    total_passed_credits += credits

        if total_credits > 0:
            gpa_10 = cls._round_half_up(cls._decimal(total_score_points) / total_credits, 2)
            gpa_4 = cls._round_half_up(cls._decimal(total_gpa4_points) / total_credits, 2)
        else:
            gpa_10 = gpa_4 = 0

        return {
            'gpa_10': gpa_10,
            'gpa_4': gpa_4,
            'total_credits': total_credits,
            'total_passed_credits': total_passed_credits
        }

    CREDIT_CLASS_SELECT = """
        SELECT c.*, a.full_name as lecturer_name, u.username as lecturer_email
        FROM credit_classes c
        LEFT JOIN users u ON c.lecturer_id = u.id
        LEFT JOIN admin_profiles a ON u.id = a.user_id
    """

    @classmethod
    def get_credit_class(cls, credit_class_id):
        """Lấy một lớp tín chỉ kèm tên/email giảng viên, hoặc None nếu không tồn tại"""
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(cls.CREDIT_CLASS_SELECT + " WHERE c.id = %s", (credit_class_id,))
                return cursor.fetchone()
        except Exception:
            return None

    @classmethod
    def search_credit_classes(cls, keyword='', prefixes=(), semester=None, year=None, page=1, per_page=25):
        """
        Tìm và phân trang lớp tín chỉ phía máy chủ.
        keyword khớp mã lớp, tên môn, tên hoặc email giảng viên; prefixes lọc theo đầu mã lớp.
        Trả về (danh sách lớp của trang, tổng số lớp khớp, số trang thực tế sau khi giới hạn).
        """
        conditions = []
        params = []
        if keyword:
            pattern = f"%{escape_like(keyword)}%"
            conditions.append("(c.class_code LIKE %s OR c.subject_name LIKE %s OR a.full_name LIKE %s OR u.username LIKE %s)")
            params.extend([pattern] * 4)
        if prefixes:
            conditions.append("(" + " OR ".join(["c.class_code LIKE %s"] * len(prefixes)) + ")")
            params.extend(f"{escape_like(prefix)}%" for prefix in prefixes)
        if semester:
            conditions.append("c.semester = %s")
            params.append(semester)
        if year:
            conditions.append("c.year = %s")
            params.append(year)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) as total
                    FROM credit_classes c
                    LEFT JOIN users u ON c.lecturer_id = u.id
                    LEFT JOIN admin_profiles a ON u.id = a.user_id
                    """ + where,
                    tuple(params)
                )
                total = cursor.fetchone()['total']
                page = clamp_page(page, per_page, total)

                cursor.execute(
                    cls.CREDIT_CLASS_SELECT + where
                    + " ORDER BY c.year DESC, c.semester DESC, c.subject_name ASC, c.id ASC LIMIT %s OFFSET %s",
                    tuple(params) + (per_page, (page - 1) * per_page)
                )
                return cursor.fetchall(), total, page
        except Exception:
            return [], 0, 1

    @classmethod
    def assign_lecturer(cls, credit_class_id, lecturer_id):
        try:
            with get_db_cursor(commit=True) as cursor:
                # rowcount = 0 cả khi lớp đã có đúng giảng viên này, nên kiểm tra lớp tồn tại riêng
                cursor.execute("SELECT id FROM credit_classes WHERE id = %s", (credit_class_id,))
                if not cursor.fetchone():
                    return False
                cursor.execute("UPDATE credit_classes SET lecturer_id = %s WHERE id = %s", (lecturer_id, credit_class_id))
                return True
        except Exception:
            return False

    @classmethod
    def enroll_students(cls, credit_class_id, student_identifiers):
        identifiers = list(dict.fromkeys(
            str(identifier).strip() for identifier in student_identifiers if str(identifier).strip()
        ))
        if not identifiers:
            return False, 'Hãy nhập ít nhất một email hoặc mã sinh viên.'
        if len(identifiers) > 500:
            return False, 'Mỗi lần chỉ được ghi danh tối đa 500 sinh viên.'

        try:
            with get_db_cursor(dictionary=True, commit=True) as cursor:
                cursor.execute(
                    "SELECT subject_name, credits, semester, year FROM credit_classes WHERE id = %s",
                    (credit_class_id,)
                )
                credit_class = cursor.fetchone()
                if not credit_class:
                    return False, 'Không tìm thấy lớp tín chỉ.'

                placeholders = ', '.join(['%s'] * len(identifiers))
                cursor.execute(
                    f"""
                    SELECT u.id, u.username, p.student_code
                    FROM users u
                    JOIN student_profiles p ON p.user_id = u.id
                    WHERE u.role = 'student'
                      AND (u.username IN ({placeholders}) OR p.student_code IN ({placeholders}))
                    """,
                    tuple(identifiers + identifiers)
                )
                rows = cursor.fetchall()
                resolved_ids = set()
                matched_identifiers = set()
                for row in rows:
                    if row['username'] in identifiers:
                        resolved_ids.add(row['id'])
                        matched_identifiers.add(row['username'])
                    if row['student_code'] in identifiers:
                        resolved_ids.add(row['id'])
                        matched_identifiers.add(row['student_code'])

                unknown = [identifier for identifier in identifiers if identifier not in matched_identifiers]
                if unknown:
                    return False, f"Không tìm thấy sinh viên: {', '.join(unknown[:10])}. Chưa ghi danh ai."

                student_ids = sorted(resolved_ids)
                placeholders = ', '.join(['%s'] * len(student_ids))
                cursor.execute(
                    f"SELECT student_id FROM grades WHERE credit_class_id = %s AND student_id IN ({placeholders})",
                    (credit_class_id, *student_ids)
                )
                already_enrolled = {row['student_id'] for row in cursor.fetchall()}
                new_student_ids = [student_id for student_id in student_ids if student_id not in already_enrolled]

                if new_student_ids:
                    cursor.executemany(
                        """
                        INSERT INTO grades
                        (student_id, credit_class_id, subject, credits, semester, year)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE id = id
                        """,
                        [(
                            student_id, credit_class_id, credit_class['subject_name'],
                            credit_class['credits'], credit_class['semester'], credit_class['year']
                        ) for student_id in new_student_ids]
                    )

                return True, f'Đã ghi danh {len(new_student_ids)} sinh viên; {len(already_enrolled)} đã có trong lớp.'
        except Exception:
            return False, 'Không thể ghi danh sinh viên vào lớp tín chỉ.'

    @classmethod
    def unenroll_student(cls, credit_class_id, grade_id):
        """
        Gỡ một sinh viên ghi danh nhầm khỏi lớp tín chỉ (xóa dòng grades).
        Chỉ gỡ được khi dòng chưa có đầu điểm nào và chưa có nhật ký sửa điểm: xóa grades sẽ xóa dây chuyền
        grade_audit_logs (ON DELETE CASCADE), nên dòng đã từng nhập điểm phải giữ lại.
        """
        try:
            credit_class_id, grade_id = int(credit_class_id), int(grade_id)
        except (TypeError, ValueError):
            return False, 'Không tìm thấy sinh viên này trong lớp tín chỉ.'

        try:
            with get_db_cursor(dictionary=True, commit=True) as cursor:
                # FOR UPDATE: khóa dòng để không ai nhập điểm xen vào giữa lúc kiểm tra và lúc xóa
                cursor.execute(
                    f"""
                    SELECT g.credit_class_id, {', '.join('g.' + column for column in cls.SCORE_COLUMNS)},
                           EXISTS (SELECT 1 FROM grade_audit_logs a WHERE a.grade_id = g.id) AS has_audit_logs
                    FROM grades g
                    WHERE g.id = %s
                    FOR UPDATE
                    """,
                    (grade_id,)
                )
                row = cursor.fetchone()
                if not row or row['credit_class_id'] != credit_class_id:
                    return False, 'Không tìm thấy sinh viên này trong lớp tín chỉ.'
                if any(row[column] is not None for column in cls.SCORE_COLUMNS):
                    return False, 'Không thể hủy ghi danh: sinh viên đã có điểm trong lớp này.'
                if row['has_audit_logs']:
                    return False, 'Không thể hủy ghi danh: dòng điểm này đã có nhật ký sửa điểm, cần giữ lại để đối chiếu.'

                cursor.execute(
                    "DELETE FROM grades WHERE id = %s AND credit_class_id = %s",
                    (grade_id, credit_class_id)
                )
                if cursor.rowcount != 1:
                    return False, 'Không tìm thấy sinh viên này trong lớp tín chỉ.'
                return True, 'Đã hủy ghi danh sinh viên khỏi lớp tín chỉ.'
        except Exception:
            return False, 'Không thể hủy ghi danh sinh viên khỏi lớp tín chỉ.'

    @classmethod
    def create_credit_class(cls, class_code, subject_name, credits, semester, year, weights, schedule=None):
        if not cls.validate_weights(weights):
            return False, 'Tổng hệ số điểm phải bằng 100%; mỗi hệ số nằm trong khoảng 0–100%.'
        schedule = schedule or {}
        
        try:
            with get_db_cursor(commit=True) as cursor:
                sql = """
                    INSERT INTO credit_classes 
                    (class_code, subject_name, credits, semester, year, 
                     weight_cc, weight_bttl, weight_tbkt, weight_tgk, weight_tnth, weight_thi,
                     day_of_week, shift, room)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                val = (class_code, subject_name, credits, semester, year,
                       weights.get('cc', 10), weights.get('bttl', 0), weights.get('tbkt', 20), 
                       weights.get('tgk', 0), weights.get('tnth', 0), weights.get('thi', 70),
                       schedule.get('day_of_week'), schedule.get('shift'), schedule.get('room'))
                cursor.execute(sql, val)
                return True, "Khởi tạo Lớp tín chỉ thành công!"
        except Exception:
            # Chi tiết lỗi đã được get_db_cursor ghi log; không hiển thị thông tin CSDL cho người dùng
            return False, "Không thể lưu lớp tín chỉ. Mã lớp có thể đã tồn tại hoặc dữ liệu không hợp lệ."

    @classmethod
    def update_credit_class(cls, class_id, class_code, subject_name, credits, semester, year, weights, schedule=None, user_id=None):
        if not cls.validate_weights(weights):
            return False, 'Lỗi hệ số điểm.'
        schedule = schedule or {}
        
        new_weights = {
            'weight_cc': weights.get('cc', 10), 'weight_bttl': weights.get('bttl', 0),
            'weight_tbkt': weights.get('tbkt', 20), 'weight_tgk': weights.get('tgk', 0),
            'weight_tnth': weights.get('tnth', 0), 'weight_thi': weights.get('thi', 70)
        }
        try:
            with get_db_cursor(dictionary=True, commit=True) as cursor:
                sql = """
                    UPDATE credit_classes 
                    SET class_code=%s, subject_name=%s, credits=%s, semester=%s, year=%s,
                        weight_cc=%s, weight_bttl=%s, weight_tbkt=%s, weight_tgk=%s, weight_tnth=%s, weight_thi=%s,
                        day_of_week=%s, shift=%s, room=%s
                    WHERE id=%s
                """
                val = (class_code, subject_name, credits, semester, year,
                       new_weights['weight_cc'], new_weights['weight_bttl'], new_weights['weight_tbkt'],
                       new_weights['weight_tgk'], new_weights['weight_tnth'], new_weights['weight_thi'],
                       schedule.get('day_of_week'), schedule.get('shift'), schedule.get('room'), class_id)
                cursor.execute(sql, val)

                # grades giữ bản sao tên môn/số tín chỉ/học kỳ chép lúc ghi danh (bảng điểm và GPA đọc từ đây): đồng bộ lại
                cursor.execute(
                    "UPDATE grades SET subject = %s, credits = %s, semester = %s, year = %s WHERE credit_class_id = %s",
                    (subject_name, credits, semester, year, class_id)
                )

                # Trọng số có thể vừa đổi: tính lại điểm tổng kết đã lưu (một câu UPDATE cho cả lớp) và ghi nhật ký
                cursor.execute(
                    "SELECT id, score, score_cc, score_bttl, score_tbkt, score_tgk, score_tnth, score_thi, score_thi_2 "
                    "FROM grades WHERE credit_class_id = %s FOR UPDATE",
                    (class_id,)
                )
                changes = []
                for row in cursor.fetchall():
                    new_score = cls.calculate_final_score(row, new_weights)
                    if cls._score_changed(row['score'], new_score):
                        changes.append((row['id'], None if row['score'] is None else float(row['score']), new_score))
                if changes:
                    cases = ' '.join(['WHEN %s THEN %s'] * len(changes))
                    cursor.execute(
                        f"UPDATE grades SET score = CASE id {cases} END "
                        f"WHERE credit_class_id = %s AND id IN ({', '.join(['%s'] * len(changes))})",
                        (*[value for grade_id, _, new in changes for value in (grade_id, new)], class_id,
                         *[grade_id for grade_id, _, _ in changes])
                    )
                    if user_id:
                        cls.log_grade_changes(cursor, [
                            (grade_id, cls.AUDIT_FIELD_NAMES['score'], old, new, user_id,
                             'Master đổi trọng số điểm của lớp tín chỉ')
                            for grade_id, old, new in changes
                        ])
                message = "Cập nhật thành công!"
                if changes:
                    message += f" Đã tính lại điểm tổng kết của {len(changes)} sinh viên theo trọng số mới."
                return True, message
        except Exception:
            # Chi tiết lỗi đã được get_db_cursor ghi log; không hiển thị thông tin CSDL cho người dùng
            return False, "Không thể lưu lớp tín chỉ. Mã lớp có thể đã tồn tại hoặc dữ liệu không hợp lệ."

    @classmethod
    def get_student_schedule(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT c.class_code, c.subject_name, c.day_of_week, c.shift, c.room, a.full_name as lecturer_name, c.semester, c.year
                    FROM grades g
                    JOIN credit_classes c ON g.credit_class_id = c.id
                    LEFT JOIN users u ON c.lecturer_id = u.id
                    LEFT JOIN admin_profiles a ON u.id = a.user_id
                    WHERE g.student_id = %s AND c.day_of_week IS NOT NULL
                    ORDER BY c.year DESC, c.semester DESC, c.day_of_week ASC, c.shift ASC
                """
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def get_lecturer_schedule(cls, lecturer_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT class_code, subject_name, day_of_week, shift, room, credits, class_code
                    FROM credit_classes
                    WHERE lecturer_id = %s AND day_of_week IS NOT NULL
                    ORDER BY year DESC, semester DESC, day_of_week ASC, shift ASC
                """
                cursor.execute(sql, (lecturer_id,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def delete_credit_class(cls, class_id):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("SELECT COUNT(*) FROM grades WHERE credit_class_id = %s", (class_id,))
                if cursor.fetchone()[0] > 0:
                    return False, "⛔ Không thể xóa! Lớp này đang có dữ liệu điểm của sinh viên."
                    
                cursor.execute("DELETE FROM credit_classes WHERE id = %s", (class_id,))
                return True, "Đã xóa Lớp học phần thành công."
        except Exception:
            return False, "Lỗi hệ thống khi xóa dữ liệu."

    @classmethod
    def get_lecturer_dashboard_stats(cls, lecturer_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = "SELECT COUNT(id) as total_classes, SUM(credits) as total_credits FROM credit_classes WHERE lecturer_id = %s"
                cursor.execute(sql, (lecturer_id,))
                result = cursor.fetchone()
                return {
                    'total_classes': result['total_classes'] or 0,
                    'total_credits': result['total_credits'] or 0
                }
        except Exception:
            return {'total_classes': 0, 'total_credits': 0}

    @classmethod
    def log_grade_changes(cls, cursor, rows):
        """
        Ghi nhiều dòng nhật ký sửa điểm; mỗi dòng là (grade_id, field_name, old_score, new_score, modified_by, reason).
        executemany của mysql-connector gộp thành một câu INSERT nhiều giá trị; modified_at dùng mặc định CURRENT_TIMESTAMP.
        """
        cursor.executemany(
            """
            INSERT INTO grade_audit_logs (grade_id, field_name, old_score, new_score, modified_by, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            rows
        )

    AUDIT_LOG_FROM = """
        FROM grade_audit_logs a
        LEFT JOIN users u ON a.modified_by = u.id
        LEFT JOIN admin_profiles ap ON u.id = ap.user_id
        LEFT JOIN master_profiles mp ON u.id = mp.user_id
        LEFT JOIN grades g ON a.grade_id = g.id
        LEFT JOIN users su ON g.student_id = su.id
        LEFT JOIN student_profiles p ON su.id = p.user_id
        LEFT JOIN credit_classes c ON g.credit_class_id = c.id
    """

    @classmethod
    def search_audit_logs(cls, keyword='', field_name=None, page=1, per_page=25):
        """
        Tìm và phân trang nhật ký sửa điểm phía máy chủ, mới nhất trước.
        keyword khớp mã/tên sinh viên, mã lớp, tên môn, email/tên người sửa hoặc lý do;
        field_name lọc theo đầu điểm (giá trị trong AUDIT_FIELD_NAMES).
        Trả về (danh sách dòng của trang, tổng số dòng khớp, số trang thực tế sau khi giới hạn).
        """
        conditions = []
        params = []
        if keyword:
            pattern = f"%{escape_like(keyword)}%"
            conditions.append(
                "(p.student_code LIKE %s OR p.full_name LIKE %s OR c.class_code LIKE %s OR c.subject_name LIKE %s"
                " OR u.username LIKE %s OR ap.full_name LIKE %s OR mp.full_name LIKE %s OR a.reason LIKE %s)"
            )
            params.extend([pattern] * 8)
        if field_name in cls.AUDIT_FIELD_NAMES.values():
            conditions.append("a.field_name = %s")
            params.append(field_name)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        try:
            with get_db_cursor(dictionary=True) as cursor:
                # Không lọc theo từ khóa thì không cần JOIN để đếm
                count_from = cls.AUDIT_LOG_FROM if keyword else " FROM grade_audit_logs a "
                cursor.execute("SELECT COUNT(*) as total" + count_from + where, tuple(params))
                total = cursor.fetchone()['total']
                page = clamp_page(page, per_page, total)

                cursor.execute(
                    """
                    SELECT a.*,
                           u.username as modifier_email,
                           ap.full_name as modifier_name,
                           mp.full_name as master_modifier_name,
                           p.student_code,
                           p.full_name as student_name,
                           c.class_code,
                           c.subject_name
                    """ + cls.AUDIT_LOG_FROM + where + " ORDER BY a.id DESC LIMIT %s OFFSET %s",
                    tuple(params) + (per_page, (page - 1) * per_page)
                )
                return cursor.fetchall(), total, page
        except Exception:
            return [], 0, 1


    @classmethod
    def get_credit_classes_by_student(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT c.id, c.class_code, c.subject_name, c.credits, c.semester, c.year,
                           c.day_of_week, c.shift, c.room,
                           c.weight_cc, c.weight_bttl, c.weight_tbkt, c.weight_tgk, c.weight_tnth, c.weight_thi,
                           a.full_name as lecturer_name, u.username as lecturer_email,
                           (SELECT COUNT(*) FROM grades g2 WHERE g2.credit_class_id = c.id) as enrolled_students
                    FROM grades g
                    JOIN credit_classes c ON g.credit_class_id = c.id
                    LEFT JOIN users u ON c.lecturer_id = u.id
                    LEFT JOIN admin_profiles a ON u.id = a.user_id
                    WHERE g.student_id = %s
                    ORDER BY c.year DESC, c.semester DESC, c.subject_name ASC
                """
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def get_roster_in_credit_class(cls, credit_class_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT u.username, p.full_name, p.student_code, p.class_name, p.gender
                    FROM grades g
                    JOIN users u ON g.student_id = u.id
                    JOIN student_profiles p ON u.id = p.user_id
                    WHERE g.credit_class_id = %s
                    ORDER BY p.student_code ASC
                """
                cursor.execute(sql, (credit_class_id,))
                return cursor.fetchall()
        except Exception:
            return []