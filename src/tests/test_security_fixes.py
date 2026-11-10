import logging

from flask import Flask

from app import create_app
from app.controllers import auth as auth_module
from app.controllers import admin as admin_module
from app.controllers import student as student_module
from app.models.user_model import User
from app.services import token_service
from app.services.token_service import OtpService
from app.services.grade_export_service import GradeExportService
from app.utils.password_policy import validate_password_strength


def _fake_user(personal_email='sv.that@gmail.com'):
    return User(id=7, username='master@eduflaw.com', password='scrypt:hash',
                role='master', is_active=True, personal_email=personal_email)


def test_forgot_password_does_not_leak_reset_link(client, monkeypatch):
    """Form khôi phục kiểu cũ không được trả link reset mật khẩu về trình duyệt"""
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: _fake_user())

    response = client.post('/forgot-password', data={'email': 'master@eduflaw.com'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'/reset-password/' not in response.data


def test_send_otp_api_never_returns_otp(client, monkeypatch):
    """API gửi OTP không được trả mã OTP trong response, kể cả ở chế độ mô phỏng"""
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: _fake_user())
    monkeypatch.setattr(OtpService, 'send_otp_email', classmethod(lambda cls, *args: (True, True)))

    response = client.post('/auth/api/send-otp', json={
        'account': 'master@eduflaw.com',
        'personal_email': 'sv.that@gmail.com'
    })
    payload = response.get_json()
    assert payload['success'] is True
    assert 'dev_otp' not in payload


def test_send_otp_email_fails_when_smtp_errors(monkeypatch):
    """Lỗi SMTP phải trả về thất bại thay vì chuyển sang chế độ mô phỏng"""
    monkeypatch.setenv('SMTP_EMAIL', 'eduflaw.bot@gmail.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'realapppassword1')

    def broken_smtp(*args, **kwargs):
        raise OSError('SMTP down')

    monkeypatch.setattr(token_service.smtplib, 'SMTP', broken_smtp)

    with Flask(__name__).app_context():
        assert OtpService.send_otp_email('sv.that@gmail.com', 'b24dccn001@eduflaw.com', '123456') == (False, False)


def test_send_otp_email_dev_mode_disabled_outside_debug(monkeypatch):
    """Chưa cấu hình SMTP và không chạy debug/test thì không được giả lập gửi OTP thành công"""
    monkeypatch.delenv('SMTP_EMAIL', raising=False)
    monkeypatch.delenv('SMTP_PASSWORD', raising=False)

    production_app = Flask(__name__)
    production_app.config.update(DEBUG=False, TESTING=False)
    with production_app.app_context():
        assert OtpService.send_otp_email('sv.that@gmail.com', 'b24dccn001@eduflaw.com', '123456') == (False, False)


def test_admin_student_list_does_not_inline_profile_data_in_onclick(client, monkeypatch):
    """Dữ liệu hồ sơ do sinh viên nhập không được chèn trực tiếp vào chuỗi JS trong onclick"""
    payload = "');alert(1);//"
    profile = {
        'avatar_url': None, 'full_name': 'Nguyen Van A', 'student_code': 'B24DCCN001',
        'username': 'b24dccn001@eduflaw.com', 'gender': 'Nam', 'date_of_birth': '2006-01-01',
        'phone_number': payload, 'class_role': 'Thành viên', 'status': 'Đang học',
        'nationality': 'Việt Nam', 'ethnicity': 'Kinh', 'religion': 'Không',
        'id_card': '001', 'hometown': 'Hà Nội', 'current_address': payload
    }
    monkeypatch.setattr(admin_module.StudentProfile, 'is_class_assigned_to_advisor', lambda *args: True)
    monkeypatch.setattr(admin_module.StudentProfile, 'get_profiles_by_class', lambda *args: ([profile], 1))

    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['username'] = 'gv.001@eduflaw.com'
        sess['role'] = 'admin'
        sess['force_password_change'] = False

    response = client.get('/admin/students?class_name=D24CQCN01')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'onclick="openModalFromCard(this)"' in html
    assert 'data-address="&#39;);alert(1);//"' in html
    assert 'openModal(\'' not in html


def test_login_verify_runs_hash_even_for_unknown_account(monkeypatch):
    """Chống dò tài khoản bằng thời gian: đường đăng nhập vẫn so khớp hash khi tài khoản không tồn tại/đã khóa"""
    calls = []
    monkeypatch.setattr(User, 'verify_password',
                        staticmethod(lambda stored, candidate: calls.append(stored) or False))

    # Tài khoản không tồn tại -> vẫn thực hiện một phép so khớp (với hash giả) rồi trả về False
    assert User.verify_login_password(None, 'bất kỳ') is False
    # Tài khoản bị khóa -> cũng không được bỏ qua phép so khớp
    locked = User(id=1, username='sv@eduflaw.com', password='scrypt:real', role='student', is_active=False)
    assert User.verify_login_password(locked, 'bất kỳ') is False
    # Tài khoản đang hoạt động -> so khớp với chính hash của tài khoản đó
    active = User(id=2, username='gv@eduflaw.com', password='scrypt:real', role='admin', is_active=True)
    assert User.verify_login_password(active, 'bất kỳ') is False

    assert len(calls) == 3
    assert calls[2] == 'scrypt:real'          # tài khoản thật: so khớp đúng hash của nó
    assert calls[0] not in ('', 'scrypt:real')  # tài khoản giả: so khớp với hash giả, không rỗng


def test_csp_restricts_script_and_object_sources():
    """CSP phải giới hạn nguồn script/object (phòng thủ chiều sâu cho XSS), không chỉ frame-ancestors"""
    client = create_app({'SECRET_KEY': 'test-only', 'TESTING': True}).test_client()
    csp = client.get('/login').headers['Content-Security-Policy']

    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "'unsafe-eval'" not in csp


def test_password_policy_rejects_weak_passwords():
    """Chính sách mật khẩu offline: chặn mật khẩu ngắn, phổ biến hoặc quá đơn giản; chấp nhận mật khẩu mạnh"""
    assert validate_password_strength('short')[0] is False            # quá ngắn
    assert validate_password_strength('password1234')[0] is False     # phổ biến
    assert validate_password_strength('aaaaaaaaaaaa')[0] is False     # lặp ký tự
    assert validate_password_strength('121212121212')[0] is False     # chỉ 2 ký tự
    assert validate_password_strength('MatKhauMoi@2026')[0] is True   # mạnh


def test_complete_onboarding_rejects_common_password(monkeypatch):
    """complete_onboarding từ chối mật khẩu phổ biến trước khi chạm CSDL"""
    # Không monkeypatch CSDL: nếu kiểm tra độ mạnh không chặn sớm, test sẽ lỗi vì thử kết nối DB
    ok, message = User.complete_onboarding(1, 'sv@gmail.com', 'password1234')
    assert ok is False
    assert 'phổ biến' in message


def test_login_failure_is_logged_as_security_event(client, monkeypatch, caplog):
    """Đăng nhập sai phải ghi một sự kiện an ninh (phục vụ giám sát), không ghi mật khẩu"""
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: None)

    with caplog.at_level(logging.INFO):
        client.post('/login', data={'username': 'ke.tancong@eduflaw.com', 'password': 'sai-mat-khau'})

    security_lines = [record.message for record in caplog.records if '[SECURITY]' in record.message]
    assert any('event=login_failed' in line for line in security_lines)
    assert all('sai-mat-khau' not in line for line in security_lines)


def test_grade_export_neutralizes_formula_names():
    """Xuất bảng điểm phải vô hiệu hóa công thức (kể cả mở đầu bằng tab/CR) để tránh CSV/Excel injection"""
    credit_class = {'class_code': 'AT301-01', 'subject_name': '=HYPERLINK("http://evil")',
                    'credits': 3}
    students = [{
        'student_code': 'B24DCAT001', 'full_name': '=cmd|calc', 'username': 'b24dcat001@eduflaw.com',
        'class_name': '\t=1+1', 'score_cc': 8, 'score_bttl': None, 'score_tbkt': 7, 'score_tgk': None,
        'score_tnth': None, 'score_thi': 9, 'score_thi_2': None, 'score': 8.5, 'score_4': 3.7, 'letter': 'A'
    }]

    import openpyxl
    output, _ = GradeExportService.create_workbook(credit_class, students)
    sheet = openpyxl.load_workbook(output).active
    values = [cell.value for row in sheet.iter_rows() for cell in row if isinstance(cell.value, str)]

    # Không còn ô văn bản nào thực sự bắt đầu bằng ký tự công thức
    assert all(not value.lstrip().startswith(('=', '+', '-', '@')) for value in values)
    assert "'=cmd|calc" in values
    assert "'=HYPERLINK(\"http://evil\")" in values


def test_student_cannot_open_foreign_credit_class(client, monkeypatch):
    """Sinh viên xem lớp tín chỉ không thuộc mình phải bị chặn 403 (không phải lỗi 500)"""
    monkeypatch.setattr(student_module.Grade, 'get_credit_classes_by_student', lambda user_id: [])

    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'b24dccn001@eduflaw.com'
        sess['role'] = 'student'
        sess['force_password_change'] = False

    response = client.get('/student/credit-classes?credit_class_id=5')
    assert response.status_code == 403
