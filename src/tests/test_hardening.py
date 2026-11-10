import json

from flask import flash, render_template_string

from app import create_app
from app.controllers import admin as admin_module
from app.controllers import auth as auth_module
from app.controllers import master as master_module
from app.models.user_model import User
from app.services.token_service import OtpService


def _login_as(client, user_id, username, role):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['force_password_change'] = False


def test_flash_messages_are_json_encoded_in_script(app):
    """Thông báo flash phải được mã hoá JSON khi chèn vào <script>, không chỉ escape kiểu HTML"""
    message = "Lỗi ngành abc\\'\n</script><img src=x onerror=alert(1)>"
    template = '{% import "layouts/ui_macros.html" as ui %}{{ ui.render_topbar_scripts() }}'

    with app.test_request_context('/'):
        flash(message, 'error')
        html = render_template_string(template)

    assert f'showSystemToast("error" === \'error\' ? \'error\' : \'success\', {json.dumps(message).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\'", "\\u0027")});' in html
    assert '</script><img' not in html
    assert 'titleText: message' in html


def test_create_app_sets_anti_clickjacking_headers():
    """Mọi phản hồi phải chặn bị nhúng iframe và chặn đoán MIME"""
    client = create_app({'SECRET_KEY': 'test-only', 'TESTING': True}).test_client()
    response = client.get('/login')

    assert response.headers['X-Frame-Options'] == 'DENY'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_master_major_page_does_not_reflect_query_into_js(client, monkeypatch):
    """Tham số major trên URL không được chèn vào chuỗi JS trong onclick/onsubmit (reflected XSS)"""
    monkeypatch.setattr(master_module.StudentProfile, 'get_classes_summary_by_major', lambda major: [])
    _login_as(client, 3, 'master@eduflaw.com', 'master')

    payload = "x');alert(1);//"
    html = client.get('/master/students', query_string={'major': payload}).get_data(as_text=True)

    assert "value=this.dataset.major" in html
    assert "' + this.dataset.major + '" in html
    assert "value='x&#39;);alert(1);//'" not in html
    assert 'data-major="x&#39;);alert(1);//"' in html


def test_admin_self_update_keeps_official_profile_fields(client, monkeypatch):
    """Giảng viên tự sửa hồ sơ chỉ đổi được liên lạc; họ tên/CCCD/ngày sinh/giới tính đã có được giữ nguyên"""
    saved = {}
    monkeypatch.setattr(admin_module.StaffProfile, 'get_admin_profile', classmethod(lambda cls, user_id: {
        'full_name': 'ThS. Nguyễn Văn B', 'id_card': '001185000001',
        'date_of_birth': '1985-05-05', 'gender': 'Nam', 'phone_number': '0900000000', 'address': 'Cũ'
    }))

    def fake_update(cls, user_id, full_name, id_card, phone_number, dob, gender, address):
        saved.update(full_name=full_name, id_card=id_card, phone_number=phone_number,
                     dob=dob, gender=gender, address=address)
        return True

    monkeypatch.setattr(admin_module.StaffProfile, 'update_admin_profile_by_master', classmethod(fake_update))
    _login_as(client, 2, 'gv.001@eduflaw.com', 'admin')

    client.post('/admin/profile/update_info', data={
        'full_name': 'Tên Giả', 'id_card': '999', 'dob': '2000-01-01', 'gender': 'Nữ',
        'phone_number': '0911111111', 'address': 'Mới'
    })

    assert saved == {
        'full_name': 'ThS. Nguyễn Văn B', 'id_card': '001185000001', 'phone_number': '0911111111',
        'dob': '1985-05-05', 'gender': 'Nam', 'address': 'Mới'
    }


def test_other_session_cannot_overwrite_pending_otp(app):
    """Người khác yêu cầu OTP cho cùng tài khoản không làm mất mã của chủ tài khoản"""
    victim_session, attacker_session = {}, {}
    victim_code = OtpService.create_session_otp(victim_session, 'b24dccn001@eduflaw.com', 'sv.that@gmail.com')
    OtpService.create_session_otp(attacker_session, 'b24dccn001@eduflaw.com', 'sv.that@gmail.com')

    is_valid, _ = OtpService.verify_session_otp(victim_session, 'b24dccn001@eduflaw.com', 'sv.that@gmail.com', victim_code)
    assert is_valid is True


def test_replaying_old_session_does_not_reset_otp_attempts(app):
    """Số lần nhập sai được đếm phía máy chủ: phát lại cookie session cũ không reset được"""
    session_data = {}
    OtpService.create_session_otp(session_data, 'b24dccn001@eduflaw.com', 'sv.that@gmail.com')
    replayed_snapshot = dict(session_data)

    for _ in range(OtpService.MAX_ATTEMPTS):
        OtpService.verify_session_otp(dict(replayed_snapshot), 'b24dccn001@eduflaw.com', 'sv.that@gmail.com', '000000')

    is_valid, message = OtpService.verify_session_otp(dict(replayed_snapshot), 'b24dccn001@eduflaw.com', 'sv.that@gmail.com', '000000')
    assert is_valid is False
    assert 'quá 5 lần' in message


def test_otp_sends_are_limited_per_account():
    """Mỗi tài khoản chỉ được gửi tối đa MAX_SENDS_PER_WINDOW mã trong một khoảng thời gian, dù đổi phiên"""
    for _ in range(OtpService.MAX_SENDS_PER_WINDOW):
        OtpService.create_session_otp({}, 'b24dccn001@eduflaw.com', 'sv.that@gmail.com')

    assert OtpService.resend_wait_seconds({}, 'b24dccn001@eduflaw.com') > 0
    assert OtpService.resend_wait_seconds({}, 'b24dccn002@eduflaw.com') == 0


def test_complete_onboarding_reports_duplicate_personal_email(monkeypatch):
    """Gmail đã thuộc tài khoản khác (vi phạm UNIQUE) phải báo lỗi rõ ràng"""
    import mysql.connector
    from contextlib import contextmanager
    from app.models import user_model

    @contextmanager
    def duplicate_cursor(*args, **kwargs):
        raise mysql.connector.IntegrityError(msg="Duplicate entry for key 'uq_users_personal_email'", errno=1062)
        yield

    monkeypatch.setattr(user_model, 'get_db_cursor', duplicate_cursor)
    success, message = User.complete_onboarding(1, 'sv.that@gmail.com', 'MatKhauMoi@2026')

    assert success is False
    assert 'đã được liên kết với một tài khoản khác' in message


def test_credentials_workbook_neutralizes_formulas():
    """Họ tên/email từ file import không được thành công thức trong file Excel mật khẩu tạm (Excel injection)"""
    from openpyxl import load_workbook
    from app.utils.temp_password import build_credentials_workbook

    output = build_credentials_workbook([{
        'username': '=cmd@evil.example', 'full_name': '=HYPERLINK("http://evil.example","Bấm")',
        'role': 'student', 'password': 'AbcDef234567'
    }])
    sheet = load_workbook(output).active

    assert [cell.data_type for cell in sheet[2]] == ['s', 's', 's', 's']
    assert sheet['A2'].value == "'=cmd@evil.example"
    assert sheet['B2'].value.startswith("'=HYPERLINK")
    assert sheet['D2'].value == 'AbcDef234567'
