"""Test hồi quy cho các lỗi phát hiện khi kiểm thử end-to-end trên giao diện thật."""
from decimal import Decimal

from app.controllers import auth as auth_module
from app.controllers import master as master_module
from app.models.grade_model import Grade

WEIGHTS = {'weight_cc': Decimal('10.00'), 'weight_bttl': Decimal('0.00'), 'weight_tbkt': Decimal('20.00'),
           'weight_tgk': Decimal('0.00'), 'weight_tnth': Decimal('0.00'), 'weight_thi': Decimal('70.00')}


def _login_as(client, user_id, username, role, force_password_change=False):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['force_password_change'] = force_password_change


def _scores(cc, tbkt, thi):
    return {'score_cc': cc, 'score_bttl': None, 'score_tbkt': tbkt, 'score_tgk': None,
            'score_tnth': None, 'score_thi': thi, 'score_thi_2': None}


def test_final_score_rounds_half_up():
    """0.5 + 1.0 + 6.5*0.7 = 6.05 phải làm tròn thành 6.1 (round() của Python trên số thực cho ra 6.0)"""
    assert Grade.calculate_final_score(_scores(5, 5, 6.5), WEIGHTS) == 6.1
    assert Grade.calculate_final_score(_scores(Decimal('5.0'), Decimal('5.0'), Decimal('6.5')), WEIGHTS) == 6.1
    # 10*0.1 + 7.5*0.2 + 8.5*0.7 = 8.45 -> 8.5
    assert Grade.calculate_final_score(_scores(10, 7.5, 8.5), WEIGHTS) == 8.5


def test_gpa_rounds_half_up():
    """GPA làm tròn 2 chữ số theo kiểu 5 thì lên"""
    grades = [{'score': 8.0, 'credits': 3, 'score_4': 3.5}, {'score': 7.0, 'credits': 5, 'score_4': 3.0}]
    # GPA hệ 4 = (3.5*3 + 3.0*5) / 8 = 3.1875 -> 3.19; hệ 10 = 59/8 = 7.375 -> 7.38
    assert Grade.calculate_gpa(grades)['gpa_4'] == 3.19
    assert Grade.calculate_gpa(grades)['gpa_10'] == 7.38


def test_onboarding_stays_on_password_step_after_otp_verified(client, monkeypatch):
    """Sau khi đã xác thực OTP, lỗi ở bước đặt mật khẩu không được đẩy người dùng về bước 1"""
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: None)
    monkeypatch.setattr(auth_module.StudentProfile, 'get_student_profile', lambda username: {'full_name': 'Nguyễn Văn A'})
    _login_as(client, 1, 'b24dccn001@eduflaw.com', 'student', force_password_change=True)

    html = client.get('/onboarding').get_data(as_text=True)
    assert 'const verifiedPersonalEmail = null;' in html

    with client.session_transaction() as sess:
        sess['onboarding_otp_verified'] = True
        sess['verified_personal_email'] = 'sv.that@gmail.com'
    html = client.get('/onboarding').get_data(as_text=True)
    assert 'const verifiedPersonalEmail = "sv.that@gmail.com";' in html
    assert 'goToStep(3);' in html


def test_master_student_detail_has_reset_password_button(client, monkeypatch):
    """Master phải có nút cấp lại mật khẩu sinh viên (trước đây route có nhưng giao diện không có)"""
    profile = {'user_id': 7, 'username': 'b24dccn001@eduflaw.com', 'student_code': 'B24DCCN001',
               'full_name': "O'Neil <b>Test</b>", 'class_name': 'D24CQCN01', 'major': 'Công nghệ thông tin',
               'cohort': 'D24', 'date_of_birth': '2006-01-01'}
    monkeypatch.setattr(master_module.StudentProfile, 'get_student_profile', lambda username: profile)
    monkeypatch.setattr(master_module.Grade, 'get_all_grades_by_student', lambda user_id: [])
    _login_as(client, 3, 'master@eduflaw.com', 'master')

    html = client.get('/master/student/detail?username=b24dccn001%40eduflaw.com').get_data(as_text=True)
    assert 'action="/master/students/reset_password"' in html
    # Tên sinh viên chỉ nằm trong data-*, không chèn vào chuỗi JS của onsubmit
    assert 'data-student="O&#39;Neil &lt;b&gt;Test&lt;/b&gt; - B24DCCN001"' in html
    assert "this.dataset.student" in html


def test_flash_toast_script_is_not_cut_by_comment(app):
    """Có thông báo flash thì khối script hiện toast phải còn nguyên: trước đây comment JS chứa thẻ đóng script
    làm trình duyệt kết thúc script giữa chừng, in mã ra trang và làm hỏng mọi nút dùng SweetAlert"""
    from flask import flash, render_template_string

    with app.test_request_context('/'):
        flash('Đã cập nhật hồ sơ </script><b>x</b>', 'success')
        html = render_template_string('{% import "layouts/ui_macros.html" as ui %}{{ ui.render_topbar_scripts() }}')

    inline_script = html.split('sweetalert2.all.min.js', 1)[1]
    body = inline_script.split('<script>', 1)[1]
    assert 'showSystemToast("success"' in body.split('</script>', 1)[0]
    # Nội dung flash được tojson escape, không tự đóng được thẻ script
    assert '</script><b>' not in html


def test_shared_css_sets_mobile_viewport(app):
    """Trang sau đăng nhập phải có thẻ viewport, nếu không điện thoại hiển thị bản 980px thu nhỏ"""
    from flask import render_template_string

    with app.test_request_context('/'):
        html = render_template_string('{% import "layouts/ui_macros.html" as ui %}{{ ui.render_common_css() }}')

    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert '@media (max-width: 768px)' in html
