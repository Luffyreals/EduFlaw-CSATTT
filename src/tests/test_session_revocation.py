"""Đổi mật khẩu / được cấp lại mật khẩu thì mọi phiên đăng nhập cũ (cookie) phải mất hiệu lực"""
from contextlib import contextmanager

from werkzeug.security import generate_password_hash

from app.controllers import auth as auth_module
from app.models import user_model
from app.models.user_model import User

# conftest thay is_account_active bằng hàm luôn trả True: giữ bản thật để kiểm tra riêng
_real_is_account_active = User.is_account_active.__func__


class _RowCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return self.row


def _patch_user_row(monkeypatch, row):
    @contextmanager
    def fake_get_db_cursor(*args, **kwargs):
        yield _RowCursor(row)

    monkeypatch.setattr(user_model, 'get_db_cursor', fake_get_db_cursor)


def test_active_check_rejects_session_after_password_changed(app, monkeypatch):
    old_hash = generate_password_hash('MatKhauCu@2026')
    new_hash = generate_password_hash('MatKhauMoi@2026')
    _patch_user_row(monkeypatch, {'is_active': True, 'role': 'student', 'password': new_hash})

    with app.app_context():
        old_fp = User.password_fingerprint(old_hash)
        new_fp = User.password_fingerprint(new_hash)

        assert _real_is_account_active(User, 1, 'student', new_fp) is True
        assert _real_is_account_active(User, 1, 'student', old_fp) is False
        # Phiên tạo trước khi có cơ chế này không có pw_fp: bị hủy
        assert _real_is_account_active(User, 1, 'student', '') is False
        # Không truyền dấu vân tay thì chỉ kiểm tra trạng thái và vai trò
        assert _real_is_account_active(User, 1, 'student') is True


def test_active_check_still_rejects_locked_account(app, monkeypatch):
    password_hash = generate_password_hash('MatKhau@2026')
    _patch_user_row(monkeypatch, {'is_active': False, 'role': 'admin', 'password': password_hash})

    with app.app_context():
        assert _real_is_account_active(User, 2, 'admin', User.password_fingerprint(password_hash)) is False


def test_fingerprint_does_not_expose_password_hash(app):
    password_hash = generate_password_hash('MatKhau@2026')
    with app.app_context():
        fingerprint = User.password_fingerprint(password_hash)
    assert password_hash not in fingerprint
    assert len(fingerprint) == 32


def test_login_stores_password_fingerprint(client, monkeypatch):
    user = User(6, 'b24dccn006@eduflaw.com', generate_password_hash('MatKhauMoi@2026'), 'student',
                personal_email='sv.that@gmail.com')
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: user if username == user.username else None)

    @contextmanager
    def no_profile(*args, **kwargs):
        raise RuntimeError('Không dùng CSDL thật trong test')
        yield

    monkeypatch.setattr(auth_module, 'get_db_cursor', no_profile)

    client.post('/login', data={'username': user.username, 'password': 'MatKhauMoi@2026'})

    with client.application.app_context():
        expected = User.password_fingerprint(user.password)
    with client.session_transaction() as sess:
        assert sess['pw_fp'] == expected


def test_protected_route_checks_session_fingerprint(client, monkeypatch):
    seen = {}

    def fake_active(cls, user_id, role, password_fp=None):
        seen['password_fp'] = password_fp
        return False

    monkeypatch.setattr(User, 'is_account_active', classmethod(fake_active))
    with client.session_transaction() as sess:
        sess['user_id'] = 3
        sess['username'] = 'b24dccn003@eduflaw.com'
        sess['role'] = 'student'
        sess['pw_fp'] = 'dau-van-tay-cu'

    response = client.get('/student')

    assert seen['password_fp'] == 'dau-van-tay-cu'
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def _session(client, force_password_change):
    with client.session_transaction() as sess:
        sess['user_id'] = 4
        sess['username'] = 'gv.004@eduflaw.com'
        sess['role'] = 'admin'
        sess['pw_fp'] = 'dau-van-tay'
        sess['force_password_change'] = force_password_change


def test_activated_session_cannot_use_onboarding_to_change_password(client):
    """Phiên đã kích hoạt (máy bỏ quên đăng nhập) không được dùng onboarding để đổi mật khẩu/Gmail mà không cần mật khẩu"""
    _session(client, force_password_change=False)

    otp = client.post('/auth/api/onboarding/save-and-send-otp', json={'personal_email': 'ke.gian@gmail.com'})
    verify = client.post('/auth/api/onboarding/verify-otp', json={'personal_email': 'ke.gian@gmail.com', 'otp_code': '123456'})
    complete = client.post('/onboarding/complete', data={'new_password': 'MatKhauMoi@2026', 'confirm_password': 'MatKhauMoi@2026'})

    assert otp.status_code == 401 and verify.status_code == 401
    assert complete.status_code == 302 and '/login' in complete.headers['Location']
    assert '/admin' in client.get('/onboarding').headers['Location']


def test_revoked_session_cannot_use_onboarding(client, monkeypatch):
    """Phiên cũ sau khi mật khẩu đã được cấp lại (dấu vân tay không khớp) bị hủy, không chiếm được tài khoản"""
    monkeypatch.setattr(User, 'is_account_active', classmethod(lambda cls, user_id, role, password_fp=None: False))
    _session(client, force_password_change=True)

    response = client.post('/auth/api/onboarding/save-and-send-otp', json={'personal_email': 'ke.gian@gmail.com'})

    assert response.status_code == 401
    with client.session_transaction() as sess:
        assert 'user_id' not in sess
