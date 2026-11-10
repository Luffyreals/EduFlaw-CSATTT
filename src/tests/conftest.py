import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from app.controllers.auth import auth_bp
from app.controllers.admin import admin_bp
from app.controllers.master import master_bp
from app.controllers.student import student_bp
from app.controllers import auth as auth_module
from app.models.user_model import User
from app.services import token_service
from tests.fake_security_state import FakeSecurityState
from app.utils.db_helper import release_request_connection

@pytest.fixture(autouse=True)
def isolate_from_database(monkeypatch):
    """Test không kết nối CSDL thật: coi mọi tài khoản trong session là đang hoạt động, dùng kho trạng thái chống dò (khóa đăng nhập, OTP) trong bộ nhớ, riêng cho từng test"""
    monkeypatch.setattr(User, 'is_account_active', classmethod(lambda cls, user_id, role, password_fp=None: True))
    fake_state = FakeSecurityState()
    monkeypatch.setattr(auth_module, 'SecurityState', fake_state)
    monkeypatch.setattr(token_service, 'SecurityState', fake_state)
    return fake_state

@pytest.fixture
def app():
    """Khởi tạo Flask app giả lập cho môi trường test"""
    app = Flask(__name__, template_folder='../app/templates')
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key-123'
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Mock hàm csrf_token() để các file HTML không bị lỗi
    app.jinja_env.globals['csrf_token'] = lambda: 'dummy-csrf-token'
    
    # Đăng ký các route để test
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(student_bp)

    # Giống create_app: trả kết nối CSDL dùng chung của request về pool khi kết thúc
    app.teardown_appcontext(release_request_connection)

    return app

@pytest.fixture
def client(app):
    """Tạo test client để giả lập các request HTTP"""
    return app.test_client()