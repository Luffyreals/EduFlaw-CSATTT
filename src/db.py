import time
import mysql.connector
from mysql.connector import pooling
from mysql.connector.errors import PoolError
from config import Config
from threading import Lock

POOL_SIZE = 10
# Pool của mysql-connector báo lỗi ngay khi hết kết nối; chờ tối đa bấy nhiêu giây trước khi bỏ cuộc
POOL_WAIT_SECONDS = 5


def _default_ca_bundle():
    """Đường dẫn bộ CA công khai của certifi (nếu đã cài), dùng làm CA mặc định cho TLS tới CSDL; '' nếu không có."""
    try:
        import certifi
        return certifi.where()
    except Exception:
        return ''


class SafePooledConnection:
    """
    Bọc kết nối lấy từ pool. Pool tắt pool_reset_session (với TiDB, mỗi lần reset phiên tốn ~375 ms),
    nên trước khi trả kết nối về pool phải rollback transaction còn dở; nếu không, request sau có thể
    commit nhầm thay đổi dở dang hoặc đọc snapshot cũ (REPEATABLE READ).
    """

    def __init__(self, connection):
        self._connection = connection

    def close(self):
        try:
            if self._connection.in_transaction:
                self._connection.rollback()
        except mysql.connector.Error:
            pass
        finally:
            self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


class LazyConnectionPool:
    def __init__(self):
        self._pool = None
        self._lock = Lock()

    def get_connection(self):
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    self._pool = self._create_pool()

        deadline = time.monotonic() + POOL_WAIT_SECONDS
        while True:
            try:
                return SafePooledConnection(self._pool.get_connection())
            except PoolError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    @staticmethod
    def _build_settings():
        settings = {
            'host': Config.MYSQL_HOST,
            'port': Config.MYSQL_PORT,
            'user': Config.MYSQL_USER,
            'password': Config.MYSQL_PASSWORD,
            'database': Config.MYSQL_DB
        }
        environment_names = {
            'host': 'MYSQL_HOST',
            'port': 'MYSQL_PORT',
            'user': 'MYSQL_USER',
            'password': 'MYSQL_PASSWORD',
            'database': 'MYSQL_DB'
        }
        missing = [environment_names[name] for name, value in settings.items() if value in (None, '')]
        if missing:
            names = ', '.join(missing)
            raise RuntimeError(f'Missing database configuration: {names}')

        # Cấu hình TLS: với CSDL ở xa phải bật kênh mã hóa CÓ xác thực chứng chỉ để chống MITM.
        ssl_ca = (Config.MYSQL_SSL_CA or '').strip()
        if Config.MYSQL_SSL_DISABLED:
            # Tắt hẳn TLS: chỉ cho CSDL local không bật TLS; không dùng ở môi trường qua mạng
            settings['ssl_disabled'] = True
        elif not ssl_ca and not Config.MYSQL_SSL_VERIFY:
            # TLS bật (mặc định của driver) nhưng KHÔNG xác thực chứng chỉ: dành cho CSDL nội bộ dùng chứng chỉ
            # tự ký (vd MySQL trong Docker). Đường truyền vẫn được mã hóa, đủ cho caching_sha2_password của MySQL 8.
            settings['ssl_verify_cert'] = False
            settings['ssl_verify_identity'] = False
        else:
            if not ssl_ca:
                # Không cấu hình CA: tự dùng bộ CA công khai của certifi (nếu đã cài) để kết nối vẫn được
                # xác thực chứng chỉ mà không phải khai báo đường dẫn CA theo từng máy. TiDB Cloud dùng CA công khai.
                ssl_ca = _default_ca_bundle()
            if ssl_ca:
                # Có CA -> xác thực chứng chỉ máy chủ; mặc định xác thực cả danh tính (hostname)
                settings['ssl_ca'] = ssl_ca
                settings['ssl_verify_cert'] = True
                settings['ssl_verify_identity'] = Config.MYSQL_SSL_VERIFY
            # Vẫn không có CA (không cài certifi): giữ mặc định driver (có thể không xác thực chứng chỉ);
            # create_app cảnh báo ở production để nhắc cấu hình MYSQL_SSL_CA.
        return settings

    @classmethod
    def _create_pool(cls):
        return pooling.MySQLConnectionPool(
            pool_name='eduflaw_pool',
            pool_size=POOL_SIZE,
            pool_reset_session=False,
            **cls._build_settings()
        )


db_pool = LazyConnectionPool()