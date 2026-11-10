def test_student_dashboard_requires_login(client):
    """Truy cập dashboard sinh viên khi chưa đăng nhập phải bị chuyển hướng"""
    response = client.get('/student')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_student_profile_requires_login(client):
    """Truy cập trang hồ sơ cá nhân khi chưa đăng nhập phải bị chuyển hướng"""
    response = client.get('/student/profile')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_dashboard_gpa_chart_uses_real_term_gpa(client, monkeypatch):
    """Biểu đồ xu hướng vẽ GPA tích lũy thật theo học kỳ (trước đây là số liệu mẫu cố định cho mọi sinh viên)"""
    from app.controllers import student as student_module
    from app.models.grade_model import Grade

    def grade(year, semester, score, credits=3):
        row = {'year': year, 'semester': semester, 'score': score, 'credits': credits}
        row.update(Grade.convert_score(score))
        return row

    grades = [grade(2025, 1, 6.0), grade(2025, 2, 9.0), grade(2025, 2, None)]
    monkeypatch.setattr(student_module.Grade, 'get_all_grades_by_student', lambda user_id: grades)
    monkeypatch.setattr(student_module.Grade, 'get_student_schedule', lambda user_id: [])
    monkeypatch.setattr(student_module.StudentProfile, 'get_student_profile', lambda username: {'class_name': 'D25CQAT01'})
    monkeypatch.setattr(student_module.Announcement, 'get_announcements_for_student', lambda class_name: [])
    with client.session_transaction() as sess:
        sess['user_id'], sess['username'], sess['role'] = 1, 'b25dcat001@eduflaw.com', 'student'

    html = client.get('/student').get_data(as_text=True)

    expected = [
        {'label': 'HK1 2025-2026', 'gpa': Grade.calculate_gpa(grades[:1])['gpa_4']},
        {'label': 'HK2 2025-2026', 'gpa': Grade.calculate_gpa(grades)['gpa_4']},
    ]
    import json
    trend = json.loads(html.split('const trend = ', 1)[1].split(';', 1)[0])
    assert trend == expected
    assert '2.8, 3.0, 2.9' not in html
