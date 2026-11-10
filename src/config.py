import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = Path(BASE_DIR).parent
load_dotenv(REPO_ROOT / '.env')
load_dotenv(Path(BASE_DIR) / '.env')


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Hết hạn sau bấy nhiêu phút KHÔNG thao tác (mỗi request gia hạn lại). 5 phút quá ngắn:
    # giảng viên/master điền form lâu sẽ bị đăng xuất khi gửi và mất dữ liệu vừa nhập.
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=max(1, int(os.getenv('SESSION_TIMEOUT_MINUTES', '30') or 30)))
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE')
    WTF_CSRF_TIME_LIMIT = 3600

    # Số reverse proxy tin cậy đứng trước app (0 = không dùng X-Forwarded-*)
    TRUST_PROXY = int(os.getenv('TRUST_PROXY', '0') or 0)

    MYSQL_HOST = os.getenv('MYSQL_HOST')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT') or 4000)
    MYSQL_USER = os.getenv('MYSQL_USER')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
    MYSQL_DB = os.getenv('MYSQL_DB')

    # TLS tới CSDL. CSDL ở xa (TiDB Cloud) cần kênh được mã hóa VÀ xác thực chứng chỉ, nếu không kẻ đứng giữa
    # (MITM) có thể giả mạo máy chủ DB. Trỏ MYSQL_SSL_CA tới file CA (PEM) để bật TLS có xác thực danh tính.
    # MYSQL_SSL_VERIFY=false chỉ tắt kiểm tra hostname (vẫn xác thực CA). MYSQL_SSL_DISABLED=true chỉ dùng cho
    # CSDL local không có TLS (vd MySQL trên localhost khi phát triển).
    MYSQL_SSL_CA = os.getenv('MYSQL_SSL_CA')
    MYSQL_SSL_VERIFY = _env_bool('MYSQL_SSL_VERIFY', True)
    MYSQL_SSL_DISABLED = _env_bool('MYSQL_SSL_DISABLED', False)

    # Khóa mã hóa trường PII nhạy cảm (CCCD) ở tầng ứng dụng. Nên đặt khóa riêng, tách khỏi SECRET_KEY;
    # nếu để trống sẽ dẫn xuất tạm từ SECRET_KEY (xem app/utils/field_crypto.py). ĐỔI khóa này đồng nghĩa
    # phải mã hóa lại dữ liệu cũ, nên giữ cố định ở production.
    FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SECRET_KEY = 'test-only-secret-key'

config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}