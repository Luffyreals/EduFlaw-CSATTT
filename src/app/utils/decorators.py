# app/utils/decorators.py
from functools import wraps
from flask import session, redirect, abort
from app.models.user_model import User

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/login')
            
            user_role = session.get('role')
            if user_role not in allowed_roles:
                # Tự động điều hướng về đúng dashboard của role đó nếu truy cập sai
                dashboard_map = {
                    'master': '/master',
                    'admin': '/admin',
                    'student': '/student'
                }
                return redirect(dashboard_map.get(user_role, '/login'))

            # Tài khoản bị khóa/xóa, hoặc mật khẩu đã đổi/cấp lại sau khi đăng nhập thì session cũ phải mất hiệu lực ngay.
            # Session không có pw_fp (đăng nhập trước khi có cơ chế này) cũng bị hủy: '' không khớp dấu vân tay nào.
            if not User.is_account_active(session.get('user_id'), user_role, session.get('pw_fp', '')):
                session.clear()
                return redirect('/login')

            return f(*args, **kwargs)
        return decorated_function
    return decorator