def test_master_dashboard_access_denied_for_student(client):
    """Đảm bảo tài khoản Sinh viên không thể truy cập trang Quản trị Master"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role'] = 'student'
        sess['force_password_change'] = False
        
    response = client.get('/master')
    assert response.status_code in [302, 403]

def test_master_dashboard_access_denied_for_admin(client):
    """Đảm bảo tài khoản Giảng viên (Admin) không thể truy cập trang Master"""
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['role'] = 'admin'
        sess['force_password_change'] = False
        
    response = client.get('/master/students')
    assert response.status_code in [302, 403]

def test_master_dashboard_grade_distribution_uses_real_counts(client, monkeypatch):
    """Biểu đồ phổ điểm lấy số đếm thật từ CSDL (trước đây là số liệu mẫu cố định [25, 40, 20, 10, 5])"""
    from app.controllers import master as master_module

    def fake_counts(*names):
        values = {'dist_gioi': 7, 'dist_kha': 11, 'dist_tb': 3, 'dist_yeu': 2, 'dist_kem': 1}
        return {name: values.get(name, 0) for name in names}

    monkeypatch.setattr(master_module, '_system_counts', fake_counts)
    with client.session_transaction() as sess:
        sess['user_id'], sess['username'], sess['role'] = 1, 'master@eduflaw.com', 'master'

    html = client.get('/master').get_data(as_text=True)

    assert 'data: [7, 11, 3, 2, 1],' in html
    assert '[25, 40, 20, 10, 5]' not in html
