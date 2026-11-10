from contextlib import contextmanager

from app.models import security_state_model
from app.models.security_state_model import SecurityState


class ScriptedCursor:
    """Cursor giả: ghi lại câu lệnh và trả về kết quả đã định sẵn cho các câu SELECT"""

    def __init__(self, rows):
        self.rows = list(rows)
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((' '.join(sql.split()), params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return self.rows.pop(0) if self.rows else []


def _use_cursor(monkeypatch, cursor):
    commits = []

    @contextmanager
    def fake_get_db_cursor(dictionary=False, commit=False):
        yield cursor
        commits.append(commit)

    monkeypatch.setattr(security_state_model, 'get_db_cursor', fake_get_db_cursor)
    return commits


def test_register_failure_increments_atomically_without_lock(monkeypatch):
    cursor = ScriptedCursor([(2,)])
    commits = _use_cursor(monkeypatch, cursor)

    assert SecurityState.register_failure('user:a', 5, 60) is False
    assert 'ON DUPLICATE KEY UPDATE attempts = attempts + 1' in cursor.executed[0][0]
    assert len(cursor.executed) == 2
    assert commits == [True]


def test_register_failure_locks_at_threshold(monkeypatch):
    cursor = ScriptedCursor([(5,)])
    _use_cursor(monkeypatch, cursor)

    assert SecurityState.register_failure('user:a', 5, 60) is True
    sql, params = cursor.executed[-1]
    assert sql.startswith('UPDATE login_attempts SET attempts = 0, lockout_until')
    assert params[1] == 'user:a'


def test_lockout_until_defaults_to_zero(monkeypatch):
    _use_cursor(monkeypatch, ScriptedCursor([]))
    assert SecurityState.lockout_until('ip:1.2.3.4') == 0.0


def test_lockout_until_reads_stored_value(monkeypatch):
    _use_cursor(monkeypatch, ScriptedCursor([(1234.5,)]))
    assert SecurityState.lockout_until('ip:1.2.3.4') == 1234.5


def test_keys_are_truncated_to_column_length(monkeypatch):
    cursor = ScriptedCursor([(1,)])
    _use_cursor(monkeypatch, cursor)
    SecurityState.register_failure('x' * 400, 5, 60)
    assert len(cursor.executed[0][1][0]) == 255


def test_recent_sends_returns_floats(monkeypatch):
    _use_cursor(monkeypatch, ScriptedCursor([[(10,), (20,)]]))
    assert SecurityState.recent_sends('a@eduflaw.com', 0) == [10.0, 20.0]


def test_missing_otp_id_skips_database(monkeypatch):
    cursor = ScriptedCursor([])
    _use_cursor(monkeypatch, cursor)
    assert SecurityState.get_otp(None) is None
    SecurityState.delete_otp(None)
    assert cursor.executed == []


# ---- Cấu hình production ----

import pytest

from app import create_app


def _production_config(**overrides):
    config = {'SECRET_KEY': 'k', 'ENV': 'production', 'TESTING': False, 'SESSION_COOKIE_SECURE': True,
              'MYSQL_HOST': 'h', 'MYSQL_USER': 'u', 'MYSQL_PASSWORD': 'p', 'MYSQL_DB': 'd'}
    config.update(overrides)
    return config


def test_production_requires_database_settings():
    with pytest.raises(RuntimeError, match='MYSQL_HOST'):
        create_app(_production_config(MYSQL_HOST=None))


def test_production_requires_secure_cookie():
    with pytest.raises(RuntimeError, match='SESSION_COOKIE_SECURE'):
        create_app(_production_config(SESSION_COOKIE_SECURE=False))


def test_production_sends_hsts_and_health_check():
    client = create_app(_production_config()).test_client()
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}
    assert 'max-age' in response.headers['Strict-Transport-Security']


def test_trust_proxy_uses_forwarded_client_ip():
    app = create_app({'SECRET_KEY': 'k', 'TESTING': True, 'TRUST_PROXY': 1})

    @app.route('/ip')
    def ip():
        from flask import request
        return request.remote_addr

    response = app.test_client().get('/ip', headers={'X-Forwarded-For': '203.0.113.9'})
    assert response.get_data(as_text=True) == '203.0.113.9'


def test_forwarded_header_ignored_without_trust_proxy():
    app = create_app({'SECRET_KEY': 'k', 'TESTING': True, 'TRUST_PROXY': 0})

    @app.route('/ip')
    def ip():
        from flask import request
        return request.remote_addr

    response = app.test_client().get('/ip', headers={'X-Forwarded-For': '203.0.113.9'})
    assert response.get_data(as_text=True) != '203.0.113.9'


def test_create_app_makes_console_output_unicode_safe(monkeypatch):
    """print() tiếng Việt/emoji trên console cp1252 không được làm hỏng request"""
    import io
    import sys

    stream = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
    monkeypatch.setattr(sys, 'stdout', stream)
    create_app({'SECRET_KEY': 'k', 'TESTING': True})
    print('✅ Đã gửi OTP')
    stream.flush()


def test_authenticated_pages_are_not_cached():
    app = create_app({'SECRET_KEY': 'k', 'TESTING': True})
    client = app.test_client()
    assert 'no-store' not in client.get('/login').headers.get('Cache-Control', '')
    with client.session_transaction() as flask_session:
        flask_session['user_id'] = 1
    assert client.get('/healthz').headers['Cache-Control'] == 'no-store'
