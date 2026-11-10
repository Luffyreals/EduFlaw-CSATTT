def test_unauthorized_access_to_admin(client):
    """Kiểm tra việc truy cập trái phép vào hệ thống Admin khi chưa đăng nhập"""
    response = client.get('/admin')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_student_cannot_access_admin(client):
    """Kiểm tra phân quyền: Sinh viên không thể vào trang của Giảng viên/Admin"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role'] = 'student'
        sess['force_password_change'] = False
        
    response = client.get('/admin')
    # Chấp nhận hệ thống trả về 403 hoặc chuyển hướng 302
    assert response.status_code in [302, 403]