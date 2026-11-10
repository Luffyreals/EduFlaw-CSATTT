import mysql.connector
import pytest
from flask import Flask
from mysql.connector.errors import PoolError

import db
from app.controllers import master as master_module
from app.utils import db_helper
from app.utils.db_helper import get_db_cursor, release_request_connection


class FakeCursor:
    def __init__(self, connection, row=None):
        self.connection = connection
        self.row = row
        self.closed = False

    def execute(self, sql, params=()):
        self.connection.executed.append(sql)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, row=None):
        self.in_transaction = False
        self.executed = []
        self.events = []
        self.row = row
        self.cursor_kwargs = None

    def cursor(self, **kwargs):
        self.cursor_kwargs = kwargs
        self.in_transaction = True
        return FakeCursor(self, self.row)

    def commit(self):
        self.events.append('commit')
        self.in_transaction = False

    def rollback(self):
        self.events.append('rollback')
        self.in_transaction = False

    def close(self):
        self.events.append('close')


class CountingPool:
    def __init__(self, row=None):
        self.row = row
        self.connections = []

    def get_connection(self):
        connection = FakeConnection(self.row)
        self.connections.append(connection)
        return connection


def test_safe_connection_rolls_back_open_transaction_before_returning_to_pool():
    """Pool không reset phiên nên transaction dở phải được rollback trước khi kết nối quay lại pool"""
    raw = FakeConnection()
    raw.in_transaction = True
    db.SafePooledConnection(raw).close()
    assert raw.events == ['rollback', 'close']

    idle = FakeConnection()
    db.SafePooledConnection(idle).close()
    assert idle.events == ['close']


def test_safe_connection_closes_even_if_rollback_fails():
    """Kết nối hỏng (rollback lỗi) vẫn phải được trả về pool"""
    raw = FakeConnection()
    raw.in_transaction = True

    def broken_rollback():
        raise mysql.connector.OperationalError('Lost connection')

    raw.rollback = broken_rollback
    db.SafePooledConnection(raw).close()
    assert raw.events == ['close']


def test_pool_waits_for_a_free_connection(monkeypatch):
    """Pool hết kết nối thì chờ thay vì báo lỗi ngay"""
    attempts = []

    class BusyThenFreePool:
        def get_connection(self):
            attempts.append(1)
            if len(attempts) < 3:
                raise PoolError('Failed getting connection; pool exhausted')
            return FakeConnection()

    pool = db.LazyConnectionPool()
    pool._pool = BusyThenFreePool()
    monkeypatch.setattr(db.time, 'sleep', lambda seconds: None)

    assert isinstance(pool.get_connection(), db.SafePooledConnection)
    assert len(attempts) == 3


def test_request_reuses_one_connection_and_releases_it_on_teardown(monkeypatch):
    """Mọi get_db_cursor trong một request dùng chung một kết nối, trả về pool khi request kết thúc"""
    pool = CountingPool()
    monkeypatch.setattr(db_helper, 'db_pool', pool)
    app = Flask(__name__)
    app.teardown_appcontext(release_request_connection)

    with app.app_context():
        for _ in range(3):
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute('SELECT 1')
        assert len(pool.connections) == 1
        assert pool.connections[0].events == []
        assert pool.connections[0].cursor_kwargs == {'dictionary': True, 'buffered': True}

    assert pool.connections[0].events == ['close']


def test_outside_app_context_each_cursor_borrows_and_returns(monkeypatch):
    """Script ngoài Flask (seed, init_db) mượn và trả kết nối cho từng lần dùng"""
    pool = CountingPool()
    monkeypatch.setattr(db_helper, 'db_pool', pool)

    for _ in range(2):
        with get_db_cursor() as cursor:
            cursor.execute('SELECT 1')

    assert len(pool.connections) == 2
    assert all(connection.events == ['close'] for connection in pool.connections)


def test_commit_block_rolls_back_on_any_exception(monkeypatch):
    """Lỗi không phải lỗi CSDL trong khối commit=True cũng phải rollback, vì kết nối còn được dùng tiếp trong request"""
    pool = CountingPool()
    monkeypatch.setattr(db_helper, 'db_pool', pool)
    app = Flask(__name__)

    with app.app_context():
        with pytest.raises(KeyError):
            with get_db_cursor(commit=True) as cursor:
                cursor.execute('UPDATE users SET is_active = 0')
                raise KeyError('dữ liệu thiếu')
        assert pool.connections[0].events == ['rollback']

        with get_db_cursor(commit=True) as cursor:
            cursor.execute('UPDATE users SET is_active = 1')
        assert pool.connections[0].events == ['rollback', 'commit']


def test_system_counts_use_a_single_query(monkeypatch):
    """Thống kê của Master gộp nhiều COUNT vào một truy vấn"""
    pool = CountingPool(row={'total_students': 3000, 'total_admins': 259})
    monkeypatch.setattr(db_helper, 'db_pool', pool)

    with Flask(__name__).app_context():
        counts = master_module._system_counts('total_students', 'total_admins')

    assert counts == {'total_students': 3000, 'total_admins': 259}
    assert len(pool.connections[0].executed) == 1


def _set_db_config(monkeypatch, **overrides):
    base = {
        'MYSQL_HOST': 'db.example.com', 'MYSQL_PORT': 4000, 'MYSQL_USER': 'u',
        'MYSQL_PASSWORD': 'p', 'MYSQL_DB': 'eduflaw',
        'MYSQL_SSL_CA': None, 'MYSQL_SSL_VERIFY': True, 'MYSQL_SSL_DISABLED': False,
    }
    base.update(overrides)
    for name, value in base.items():
        monkeypatch.setattr(db.Config, name, value, raising=False)


def test_db_settings_enable_verified_tls_when_ca_configured(monkeypatch):
    """Có MYSQL_SSL_CA thì kết nối phải xác thực chứng chỉ và danh tính máy chủ (chống MITM)"""
    _set_db_config(monkeypatch, MYSQL_SSL_CA='/etc/ssl/tidb-ca.pem', MYSQL_SSL_VERIFY=True)
    settings = db.LazyConnectionPool._build_settings()

    assert settings['ssl_ca'] == '/etc/ssl/tidb-ca.pem'
    assert settings['ssl_verify_cert'] is True
    assert settings['ssl_verify_identity'] is True
    assert 'ssl_disabled' not in settings


def test_db_settings_can_relax_hostname_check(monkeypatch):
    """MYSQL_SSL_VERIFY=false chỉ tắt kiểm tra hostname, vẫn xác thực CA"""
    _set_db_config(monkeypatch, MYSQL_SSL_CA='/etc/ssl/ca.pem', MYSQL_SSL_VERIFY=False)
    settings = db.LazyConnectionPool._build_settings()

    assert settings['ssl_verify_cert'] is True
    assert settings['ssl_verify_identity'] is False


def test_db_settings_allow_disabling_tls_for_local(monkeypatch):
    """MYSQL_SSL_DISABLED=true (CSDL local) thì tắt TLS và không kèm tham số xác thực"""
    _set_db_config(monkeypatch, MYSQL_SSL_DISABLED=True, MYSQL_SSL_CA='/ignored.pem')
    settings = db.LazyConnectionPool._build_settings()

    assert settings['ssl_disabled'] is True
    assert 'ssl_ca' not in settings and 'ssl_verify_identity' not in settings


def test_db_settings_require_core_config(monkeypatch):
    """Thiếu cấu hình CSDL bắt buộc thì báo lỗi rõ ràng"""
    _set_db_config(monkeypatch, MYSQL_PASSWORD=None)
    with pytest.raises(RuntimeError, match='MYSQL_PASSWORD'):
        db.LazyConnectionPool._build_settings()


def test_db_settings_fall_back_to_certifi_when_no_ca(monkeypatch):
    """Không đặt MYSQL_SSL_CA và không tắt TLS -> tự dùng bộ CA certifi (xác thực chứng chỉ mặc định)"""
    import certifi
    _set_db_config(monkeypatch, MYSQL_SSL_CA=None, MYSQL_SSL_DISABLED=False, MYSQL_SSL_VERIFY=True)
    settings = db.LazyConnectionPool._build_settings()
    assert settings['ssl_ca'] == certifi.where()
    assert settings['ssl_verify_cert'] is True
    assert settings['ssl_verify_identity'] is True


def test_db_settings_unverified_tls_for_self_signed(monkeypatch):
    """Không CA + MYSQL_SSL_VERIFY=false -> TLS bật nhưng không xác thực chứng chỉ (MySQL nội bộ tự ký)"""
    _set_db_config(monkeypatch, MYSQL_SSL_CA=None, MYSQL_SSL_VERIFY=False, MYSQL_SSL_DISABLED=False)
    settings = db.LazyConnectionPool._build_settings()
    assert settings['ssl_verify_cert'] is False
    assert settings['ssl_verify_identity'] is False
    assert 'ssl_ca' not in settings          # không dùng certifi
    assert 'ssl_disabled' not in settings     # TLS vẫn bật
