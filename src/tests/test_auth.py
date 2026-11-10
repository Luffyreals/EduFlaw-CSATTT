def test_login_page_renders(client):
    """Kiểm tra trang đăng nhập có hiển thị thành công không (HTTP 200)"""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'EduFlaw' in response.data

def test_logout_clears_session(client):
    """Kiểm tra tính năng đăng xuất xóa session và chuyển hướng"""
    # Gắn session giả lập
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'test@eduflaw.com'
        
    response = client.post('/logout')
    assert response.status_code == 302 # Phải chuyển hướng
    assert '/login' in response.headers['Location']
    
    # Đảm bảo session đã bị xóa sạch
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_onboarding_gate_redirect(client):
    """Kiểm tra chốt chặn bảo mật (Onboarding Gate) chuyển hướng đúng"""
    with client.session_transaction() as sess:
        sess['user_id'] = 99
        sess['role'] = 'student'
        sess['force_password_change'] = True # Ép yêu cầu đổi mật khẩu (Onboarding)
        
    # Thử truy cập dashboard sẽ bị đẩy về trang /onboarding
    response = client.get('/student')
    assert response.status_code == 302
    assert '/onboarding' in response.headers['Location']

def test_logout_rejects_get_requests(client):
    """Đăng xuất chỉ nhận POST (kèm CSRF token) để trang khác không thể đăng xuất người dùng bằng một đường link"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1

    response = client.get('/logout')
    assert response.status_code == 405
    with client.session_transaction() as sess:
        assert sess['user_id'] == 1
