import logging
import os
import sys

from flask import Flask, session, redirect, url_for, request
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
import config as config_module
from config import Config

csrf = CSRFProtect()


def _make_console_safe():
    """Console Windows (cp1252) không in được tiếng Việt/emoji: print() sẽ ném UnicodeEncodeError và làm hỏng request (vd. gửi OTP)"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass


def create_app(config_class=None):
    _make_console_safe()
    app = Flask(__name__)

    # 1. Luôn nạp cấu hình gốc từ class Config trong config.py
    app.config.from_object(Config)

    # 2. Xử lý linh hoạt tham số config_class (tránh lỗi khi run.py truyền 'development')
    if isinstance(config_class, dict):
        app.config.update(config_class)
    elif isinstance(config_class, str):
        env_key = config_class.strip().lower()
        # Kiểm tra nếu trong config.py có định nghĩa dict hoặc class theo tên môi trường
        config_map = getattr(config_module, 'config_dict', None)
        env_class = getattr(config_module, f"{env_key.capitalize()}Config", None)

        if isinstance(config_map, dict) and env_key in config_map:
            app.config.from_object(config_map[env_key])
        elif env_class is not None:
            app.config.from_object(env_class)

        if env_key == 'testing':
            app.config['TESTING'] = True
    elif config_class is not None and config_class is not Config:
        app.config.from_object(config_class)

    # Thiếu SECRET_KEY thì session, CSRF và OTP đều không an toàn: dừng ngay thay vì chạy với khóa rỗng
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('Thiếu SECRET_KEY: hãy đặt SECRET_KEY trong file .env.')

    is_production = app.config.get('ENV') == 'production' and not app.config.get('TESTING')
    if is_production:
        _validate_production_config(app)
        _configure_logging(app)

    # Sau reverse proxy/PaaS, remote_addr là IP của proxy: khóa đăng nhập theo IP sẽ khóa nhầm tất cả mọi người.
    # Chỉ tin X-Forwarded-* khi khai báo đúng số proxy đứng trước app (TRUST_PROXY), vì header này giả mạo được.
    trusted_proxies = int(app.config.get('TRUST_PROXY') or 0)
    if trusted_proxies > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxies, x_proto=trusted_proxies, x_host=trusted_proxies)

    csrf.init_app(app)

    # Mỗi request dùng chung một kết nối CSDL (xem app/utils/db_helper.py); trả về pool khi request kết thúc
    from app.utils.db_helper import release_request_connection
    app.teardown_appcontext(release_request_connection)

    from app.utils.error_pages import register_error_handlers
    register_error_handlers(app)

    # CSP phòng thủ chiều sâu: giới hạn nguồn tải tài nguyên để nếu lỡ có XSS/HTML injection thì cũng
    # không nạp được script từ host lạ. Giữ 'unsafe-inline' cho script/style vì giao diện dùng nhiều
    # <script> và onclick/style nội tuyến; không bật 'unsafe-eval'. Thư viện ngoài chỉ từ cdn.jsdelivr.net.
    content_security_policy = '; '.join((
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "img-src 'self' data: https:",
        "font-src 'self' data:",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "connect-src 'self'",
    ))

    @app.after_request
    def set_security_headers(response):
        if not is_production and not app.config.get('TESTING'):
            from app.utils.pentest_toolbar import inject_pentest_toolbar
            response = inject_pentest_toolbar(response)
        # Chống clickjacking: không cho trang khác nhúng EduFlaw vào iframe
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Content-Security-Policy', content_security_policy)
        # Không cho trình duyệt đoán sai kiểu nội dung (MIME sniffing)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        # Không gửi đường dẫn đầy đủ (có thể chứa tham số) sang trang web khác
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        if 'user_id' in session and request.endpoint != 'static':
            # Trang chứa dữ liệu cá nhân không được lưu trong cache trình duyệt/proxy (nút Back sau đăng xuất)
            response.headers.setdefault('Cache-Control', 'no-store')
        if is_production:
            # Buộc trình duyệt dùng HTTPS cho các lần truy cập sau
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    @app.route('/healthz')
    def healthz():
        # Kiểm tra tiến trình còn sống (không chạm CSDL để CSDL chập chờn không làm nền tảng khởi động lại app)
        return {'status': 'ok'}

    @app.route('/demo')
    def demo_lab():
        from flask import send_file
        demo_path = os.path.abspath(os.path.join(app.root_path, '..', '..', 'demo', 'index.html'))
        if os.path.exists(demo_path):
            return send_file(demo_path)
        return "Demo lab file not found", 404

    # 3. Đăng ký các Blueprints
    from app.controllers.auth import auth_bp
    from app.controllers.student import student_bp
    from app.controllers.admin import admin_bp
    from app.controllers.master import master_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(master_bp)

    pentest_enabled = not is_production
    if pentest_enabled:
        from app.controllers.pentest import pentest_bp
        app.register_blueprint(pentest_bp)

    @app.context_processor
    def inject_dev_flags():
        return {'pentest_enabled': pentest_enabled and not app.config.get('TESTING')}

    @app.route('/')
    def index():
        if 'user_id' in session:
            if session.get('force_password_change'):
                return redirect(url_for('auth.onboarding'))
            role = session.get('role')
            if role == 'master':
                return redirect('/master')
            elif role == 'admin':
                return redirect('/admin')
            elif role == 'student':
                return redirect('/student')
        return redirect('/login')

    @app.before_request
    def check_onboarding_and_security():
        if 'user_id' not in session:
            return None

        # Các endpoint được phép truy cập trong quá trình kích hoạt tài khoản lần đầu
        onboarding_allowed = {
            'auth.onboarding',
            'auth.api_onboarding_save_and_send_otp',
            'auth.api_onboarding_verify_otp',
            'auth.onboarding_complete',
            'auth.logout',
            'auth.login',
            'static'
        }

        if request.endpoint in onboarding_allowed or (pentest_enabled and request.blueprint == 'pentest'):
            return None

        # Nếu tài khoản đang dùng mật khẩu tạm do nhà trường cấp (users.must_change_password) -> Bắt buộc vào /onboarding
        if session.get('force_password_change'):
            return redirect(url_for('auth.onboarding'))

    return app


def _validate_production_config(app):
    """Dừng sớm khi chạy production mà thiếu cấu hình bắt buộc, thay vì lỗi ở request đầu tiên"""
    missing = [name for name in ('MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DB') if not app.config.get(name)]
    if missing:
        raise RuntimeError(f"Thiếu cấu hình CSDL cho môi trường production: {', '.join(missing)}.")
    if not app.config.get('SESSION_COOKIE_SECURE'):
        raise RuntimeError('Production phải bật cookie Secure (SESSION_COOKIE_SECURE=true) và chạy sau HTTPS.')
    if not (os.getenv('SMTP_EMAIL') and os.getenv('SMTP_PASSWORD')):
        app.logger.warning('Chưa cấu hình SMTP_EMAIL/SMTP_PASSWORD: OTP sẽ không gửi được.')
    # CSDL ở xa mà không xác thực chứng chỉ TLS thì dễ bị tấn công xen giữa (MITM). Nếu không đặt MYSQL_SSL_CA,
    # app tự dùng bộ CA của certifi (xem db.py); chỉ cảnh báo khi cả hai đều không có.
    if not app.config.get('MYSQL_SSL_CA') and not app.config.get('MYSQL_SSL_DISABLED'):
        from db import _default_ca_bundle
        if not _default_ca_bundle():
            app.logger.warning('Kết nối CSDL có thể không xác thực chứng chỉ (rủi ro MITM): chưa đặt MYSQL_SSL_CA '
                               'và cũng chưa cài certifi. Hãy đặt MYSQL_SSL_CA hoặc cài certifi ở môi trường production.')


def _configure_logging(app):
    """Ghi log ra stdout để nền tảng triển khai (Docker/PaaS) thu thập"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)
