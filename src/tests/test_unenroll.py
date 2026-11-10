"""Hủy ghi danh sinh viên khỏi lớp tín chỉ: chỉ gỡ dòng chưa có điểm, đúng lớp, qua route của Master có CSRF."""
from contextlib import contextmanager
from decimal import Decimal

from app import create_app
from app.models import grade_model
from app.models.grade_model import Grade

EMPTY_SCORES = {column: None for column in Grade.SCORE_COLUMNS}


class UnenrollCursor:
    def __init__(self, row):
        self.row = row
        self.executed = []
        self.rowcount = -1

    def execute(self, sql, params=()):
        sql = ' '.join(sql.split())
        self.executed.append((sql, params))
        if sql.startswith('DELETE'):
            self.rowcount = 1

    def fetchone(self):
        return self.row

    def deletes(self):
        return [(sql, params) for sql, params in self.executed if sql.startswith('DELETE')]


def _patch_cursor(monkeypatch, row):
    cursor = UnenrollCursor(row)

    @contextmanager
    def fake_get_db_cursor(dictionary=False, commit=False):
        yield cursor

    monkeypatch.setattr(grade_model, 'get_db_cursor', fake_get_db_cursor)
    return cursor


def _grade_row(credit_class_id=5, has_audit_logs=0, **scores):
    return {'credit_class_id': credit_class_id, **EMPTY_SCORES, **scores, 'has_audit_logs': has_audit_logs}


def test_unenroll_deletes_row_without_scores(monkeypatch):
    """Dòng chưa có đầu điểm nào được xóa, khóa dòng khi đọc và chỉ xóa đúng grade của đúng lớp"""
    cursor = _patch_cursor(monkeypatch, _grade_row())

    success, message = Grade.unenroll_student('5', '42')

    assert success is True
    assert 'Đã hủy ghi danh' in message
    select_sql, select_params = cursor.executed[0]
    assert select_sql.endswith('FOR UPDATE')
    assert select_params == (42,)
    assert cursor.deletes() == [('DELETE FROM grades WHERE id = %s AND credit_class_id = %s', (42, 5))]


def test_unenroll_rejects_row_with_any_score(monkeypatch):
    """Đã có bất kỳ đầu điểm nào (kể cả 0 hoặc chỉ thi lại) thì từ chối, không xóa"""
    for column, value in (('score_cc', Decimal('0.0')), ('score_thi_2', Decimal('5.0')), ('score', Decimal('7.5'))):
        cursor = _patch_cursor(monkeypatch, _grade_row(**{column: value}))

        success, message = Grade.unenroll_student(5, 42)

        assert success is False
        assert 'đã có điểm' in message
        assert cursor.deletes() == []


def test_unenroll_rejects_row_with_audit_logs(monkeypatch):
    """Điểm đã bị xóa về trống nhưng còn nhật ký sửa điểm: không xóa (xóa grades sẽ xóa dây chuyền nhật ký)"""
    cursor = _patch_cursor(monkeypatch, _grade_row(has_audit_logs=1))

    success, message = Grade.unenroll_student(5, 42)

    assert success is False
    assert 'nhật ký sửa điểm' in message
    assert cursor.deletes() == []


def test_unenroll_rejects_grade_from_another_class(monkeypatch):
    """grade_id thuộc lớp khác (hoặc không tồn tại) thì từ chối, không xóa"""
    for row in (_grade_row(credit_class_id=6), None):
        cursor = _patch_cursor(monkeypatch, row)

        success, message = Grade.unenroll_student(5, 42)

        assert success is False
        assert 'Không tìm thấy sinh viên này trong lớp tín chỉ' in message
        assert cursor.deletes() == []


def test_unenroll_rejects_non_numeric_ids_without_querying(monkeypatch):
    cursor = _patch_cursor(monkeypatch, _grade_row())

    success, _ = Grade.unenroll_student('5', '42 OR 1=1')

    assert success is False
    assert cursor.executed == []


def _login_as(client, role):
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = f'{role}@eduflaw.com'
        sess['role'] = role
        sess['force_password_change'] = False


def test_unenroll_route_calls_model_and_returns_to_class_page(client, monkeypatch):
    calls = []
    monkeypatch.setattr(Grade, 'unenroll_student',
                        classmethod(lambda cls, class_id, grade_id: calls.append((class_id, grade_id)) or (True, 'Đã hủy ghi danh sinh viên khỏi lớp tín chỉ.')))
    _login_as(client, 'master')

    response = client.post('/master/grades/unenroll', data={'credit_class_id': '5', 'grade_id': '42'},
                           headers={'Referer': 'http://localhost/master/grades?credit_class_id=5'})

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/master/grades?credit_class_id=5')
    assert calls == [('5', '42')]
    with client.session_transaction() as sess:
        assert ('success', 'Đã hủy ghi danh sinh viên khỏi lớp tín chỉ.') in sess['_flashes']


def test_unenroll_route_requires_master_role(client, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('Không phải master thì không được gọi hủy ghi danh')

    monkeypatch.setattr(Grade, 'unenroll_student', classmethod(fail))

    assert client.post('/master/grades/unenroll', data={'credit_class_id': '5', 'grade_id': '42'}).status_code == 302
    for role in ('admin', 'student'):
        _login_as(client, role)
        response = client.post('/master/grades/unenroll', data={'credit_class_id': '5', 'grade_id': '42'})
        assert response.status_code == 302
        assert '/master/' not in response.headers['Location']


def test_unenroll_route_requires_csrf_token(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('Thiếu CSRF token thì không được gọi hủy ghi danh')

    monkeypatch.setattr(Grade, 'unenroll_student', classmethod(fail))
    client = create_app({'SECRET_KEY': 'test-only', 'TESTING': True}).test_client()
    _login_as(client, 'master')

    response = client.post('/master/grades/unenroll', data={'credit_class_id': '5', 'grade_id': '42'})

    assert response.status_code == 400


def test_class_page_shows_unenroll_button_only_for_rows_without_scores(client, monkeypatch):
    """Nút hủy ghi danh chỉ có ở dòng chưa có điểm; dữ liệu sinh viên truyền qua data-*, không chèn vào JavaScript"""
    credit_class = {'id': 5, 'class_code': 'CN301-01', 'subject_name': 'Môn 5', 'credits': 3, 'semester': 1, 'year': 2026}
    no_scores = {'grade_id': 41, 'username': 'a@eduflaw.com', 'full_name': "O'Brien <b>", 'student_code': 'B24DCCN041',
                 'class_name': 'D24CN', **EMPTY_SCORES, **Grade.convert_score(None)}
    with_scores = {**no_scores, 'grade_id': 42, 'student_code': 'B24DCCN042', 'full_name': 'Có điểm',
                   'score_cc': Decimal('8.0'), 'score': Decimal('8.0'), **Grade.convert_score(8.0)}
    monkeypatch.setattr(Grade, 'get_credit_class', staticmethod(lambda cid: credit_class))
    monkeypatch.setattr(Grade, 'get_students_in_credit_class', staticmethod(lambda cid: [no_scores, with_scores]))
    _login_as(client, 'master')

    html = client.get('/master/grades?credit_class_id=5').get_data(as_text=True)

    assert html.count('onclick="confirmUnenroll(this.dataset)"') == 1
    assert 'data-class-id="5" data-grade-id="41"' in html
    assert 'data-grade-id="42"' not in html
    assert 'data-full-name="O&#39;Brien &lt;b&gt;"' in html
    assert "titleText: 'Hủy ghi danh sinh viên?'" in html
