import importlib
from contextlib import contextmanager
from datetime import timedelta

import config
from app import create_app
from app.controllers import master as master_module
from app.models import grade_model
from app.models.grade_model import Grade


def _login_as(client, user_id, username, role):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['force_password_change'] = False


class RecordingCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((' '.join(sql.split()), params))

    def fetchone(self):
        return {'total': 120}

    def fetchall(self):
        return [{'id': 1}]


def test_search_audit_logs_paginates_on_server(monkeypatch):
    """Nhật ký sửa điểm: COUNT + LIMIT/OFFSET, từ khóa được escape, lọc đầu điểm hợp lệ"""
    cursor = RecordingCursor()

    @contextmanager
    def fake_get_db_cursor(dictionary=False, commit=False):
        yield cursor

    monkeypatch.setattr(grade_model, 'get_db_cursor', fake_get_db_cursor)

    rows, total, page = Grade.search_audit_logs('50%_x', 'Thi lần 1', page=2, per_page=25)
    assert (rows, total, page) == ([{'id': 1}], 120, 2)

    count_sql, count_params = cursor.executed[0]
    select_sql, select_params = cursor.executed[1]
    assert count_sql.startswith('SELECT COUNT(*)')
    assert count_params == ('%50\\%\\_x%',) * 8 + ('Thi lần 1',)
    assert select_sql.endswith('ORDER BY a.id DESC LIMIT %s OFFSET %s')
    assert select_params[-2:] == (25, 25)


def test_search_audit_logs_counts_without_joins_when_not_searching(monkeypatch):
    cursor = RecordingCursor()

    @contextmanager
    def fake_get_db_cursor(dictionary=False, commit=False):
        yield cursor

    monkeypatch.setattr(grade_model, 'get_db_cursor', fake_get_db_cursor)
    Grade.search_audit_logs('', 'trường lạ', page=1, per_page=25)

    count_sql, count_params = cursor.executed[0]
    assert count_sql == 'SELECT COUNT(*) as total FROM grade_audit_logs a'
    assert count_params == ()


def test_audit_log_page_uses_server_filters_and_pagination(client, monkeypatch):
    """Trang nhật ký chỉ nhận bộ lọc hợp lệ và render phân trang thay cho lọc bằng JS"""
    captured = {}

    def fake_search(keyword, field_name, page, per_page):
        captured.update(keyword=keyword, field_name=field_name, page=page, per_page=per_page)
        return [], 0, 1

    monkeypatch.setattr(master_module.Grade, 'search_audit_logs', fake_search)
    _login_as(client, 3, 'master@eduflaw.com', 'master')

    response = client.get('/master/audit_logs?q=B24&field=Thi+l%E1%BA%A7n+1&per_page=9999&page=3')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert captured == {'keyword': 'B24', 'field_name': 'Thi lần 1', 'page': 3, 'per_page': 25}
    assert 'searchLogs' not in html
    assert 'Không có lượt sửa điểm nào khớp với bộ lọc.' in html

    client.get('/master/audit_logs?field=%3Cscript%3E')
    assert captured['field_name'] is None


def test_error_pages_are_vietnamese_and_api_errors_are_json():
    """404/405/CSRF hiển thị trang tiếng Việt; endpoint /api/ trả JSON để JavaScript đọc được thông báo"""
    client = create_app({'SECRET_KEY': 'test-only', 'TESTING': True}).test_client()

    not_found = client.get('/khong-ton-tai')
    assert not_found.status_code == 404
    assert 'Không tìm thấy trang' in not_found.get_data(as_text=True)

    method = client.get('/logout')
    assert method.status_code == 405
    assert 'Thao tác không được hỗ trợ' in method.get_data(as_text=True)

    csrf_html = client.post('/logout')
    assert csrf_html.status_code == 400
    assert 'Phiên làm việc đã hết hạn' in csrf_html.get_data(as_text=True)

    csrf_json = client.post('/auth/api/send-otp', json={'account': 'x', 'personal_email': 'a@gmail.com'})
    assert csrf_json.status_code == 400
    assert csrf_json.get_json()['success'] is False
    assert 'tải lại trang' in csrf_json.get_json()['message']


def test_session_timeout_defaults_to_30_minutes_and_is_configurable(monkeypatch):
    """Phiên hết hạn sau 30 phút không thao tác (5 phút cũ làm mất dữ liệu form), chỉnh được qua môi trường"""
    try:
        monkeypatch.delenv('SESSION_TIMEOUT_MINUTES', raising=False)
        monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
        assert importlib.reload(config).Config.PERMANENT_SESSION_LIFETIME == timedelta(minutes=30)

        monkeypatch.setenv('SESSION_TIMEOUT_MINUTES', '15')
        assert importlib.reload(config).Config.PERMANENT_SESSION_LIFETIME == timedelta(minutes=15)
    finally:
        monkeypatch.undo()
        importlib.reload(config)
