from contextlib import contextmanager

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from app import create_app
from app.controllers import auth as auth_module
from app.models.user_model import User
from app.services.token_service import OtpService
from app.utils.navigation import safe_referrer


@contextmanager
def _no_database(*args, **kwargs):
    raise RuntimeError('Không có CSDL trong môi trường test')
    yield


def _login_as(client, user_id, username, role, force_password_change=False):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['force_password_change'] = force_password_change


def test_onboarding_does_not_overwrite_official_student_data(client, monkeypatch):
    """Sinh viên onboarding chỉ được cập nhật liên lạc, không được ghi đè họ tên/ngày sinh/CCCD đã có"""
    saved = {}
    monkeypatch.setattr(auth_module, 'get_db_cursor', _no_database)
    monkeypatch.setattr(auth_module.StudentProfile, 'get_student_profile', lambda username: {
        'full_name': 'Nguyễn Văn A', 'date_of_birth': '2006-01-15', 'gender': 'Nam',
        'id_card': '001206000001', 'hometown': 'Hà Nội'
    })
    monkeypatch.setattr(auth_module.StudentProfile, 'update_student_profile',
                        lambda username, payload: saved.update(payload) or True)
    monkeypatch.setattr(OtpService, 'send_otp_email', classmethod(lambda cls, *args: (True, False)))
    _login_as(client, 1, 'b24dccn001@eduflaw.com', 'student', force_password_change=True)

    response = client.post('/auth/api/onboarding/save-and-send-otp', json={
        'full_name': 'Tên Giả Mạo', 'dob': '1990-01-01', 'gender': 'Nữ', 'id_card': '999999999999',
        'phone_number': '0912345678', 'hometown': 'Nơi khác', 'address': 'Số 1 Trần Phú',
        'personal_email': 'sv.that@gmail.com'
    })

    assert response.get_json()['success'] is True
    assert saved == {'phone_number': '0912345678', 'current_address': 'Số 1 Trần Phú'}
    with client.session_transaction() as sess:
        assert sess['display_name'] == 'Nguyễn Văn A'


def test_send_otp_same_response_for_unknown_account(client, monkeypatch):
    """Tài khoản không tồn tại hay Gmail không khớp đều nhận cùng một phản hồi (chống dò tài khoản)"""
    known_user = User(id=7, username='b24dccn001@eduflaw.com', password='x', role='student',
                      is_active=True, personal_email='sv.that@gmail.com')
    monkeypatch.setattr(auth_module.User, 'get_user_by_username',
                        lambda username: known_user if username == known_user.username else None)
    monkeypatch.setattr(OtpService, 'send_otp_email', classmethod(lambda cls, *args: (True, False)))

    unknown = client.post('/auth/api/send-otp', json={'account': 'khong.ton.tai@eduflaw.com', 'personal_email': 'a@gmail.com'})
    wrong_email = client.post('/auth/api/send-otp', json={'account': known_user.username, 'personal_email': 'sai@gmail.com'})
    correct = client.post('/auth/api/send-otp', json={'account': known_user.username, 'personal_email': 'sv.that@gmail.com'})

    assert unknown.status_code == wrong_email.status_code == correct.status_code == 200
    assert unknown.get_json() == wrong_email.get_json() == correct.get_json()


def test_send_otp_enforces_resend_cooldown(client, monkeypatch):
    """Không cho gửi OTP liên tục để reset số lần thử và dò mã"""
    known_user = User(id=7, username='b24dccn001@eduflaw.com', password='x', role='student',
                      is_active=True, personal_email='sv.that@gmail.com')
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: known_user)
    monkeypatch.setattr(OtpService, 'send_otp_email', classmethod(lambda cls, *args: (True, False)))
    payload = {'account': known_user.username, 'personal_email': 'sv.that@gmail.com'}

    assert client.post('/auth/api/send-otp', json=payload).status_code == 200
    assert client.post('/auth/api/send-otp', json=payload).status_code == 429


def test_login_lockout_applies_per_account_across_ips(client, monkeypatch):
    """Sai mật khẩu 5 lần thì tài khoản bị khóa tạm thời, kể cả khi đổi sang IP khác"""
    user = User(id=7, username='b24dccn001@eduflaw.com', password=generate_password_hash('MatKhauDung@2026'),
                role='student', is_active=True, personal_email='sv.that@gmail.com')
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: user)

    for index in range(5):
        client.post('/login', data={'username': user.username, 'password': 'sai'},
                    environ_base={'REMOTE_ADDR': f'10.0.0.{index}'})

    response = client.post('/login', data={'username': user.username, 'password': 'MatKhauDung@2026'},
                           environ_base={'REMOTE_ADDR': '10.0.0.99'})
    assert response.status_code == 429


def test_locked_account_session_is_revoked(client, monkeypatch):
    """Tài khoản bị khóa sau khi đăng nhập thì session cũ bị hủy ở request tiếp theo"""
    monkeypatch.setattr(User, 'is_account_active', classmethod(lambda cls, user_id, role, password_fp=None: False))
    _login_as(client, 2, 'gv.001@eduflaw.com', 'admin')

    response = client.get('/admin')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


@pytest.mark.parametrize('referrer, expected', [
    (None, '/fallback'),
    ('https://evil.example/phish', '/fallback'),
    ('//evil.example/phish', '/fallback'),
    ('javascript:alert(1)', '/fallback'),
    ('http://localhost/master/students?major=CN', '/master/students?major=CN'),
])
def test_safe_referrer_only_allows_same_host(referrer, expected):
    """Chuyển hướng về trang trước chỉ chấp nhận URL nội bộ (chống open redirect)"""
    headers = {'Referer': referrer} if referrer else {}
    with Flask(__name__).test_request_context('/', headers=headers, base_url='http://localhost'):
        assert safe_referrer('/fallback') == expected


def test_master_toggle_status_rejects_invalid_input(client):
    """Dữ liệu trạng thái không hợp lệ phải báo lỗi thay vì gây lỗi 500"""
    _login_as(client, 3, 'master@eduflaw.com', 'master')

    response = client.post('/master/admins/toggle_status', data={'user_id': '5'})
    assert response.status_code == 302
    assert '/master/admins' in response.headers['Location']


def test_create_app_requires_secret_key():
    """Không cho khởi động ứng dụng khi thiếu SECRET_KEY"""
    with pytest.raises(RuntimeError):
        create_app({'SECRET_KEY': None})
