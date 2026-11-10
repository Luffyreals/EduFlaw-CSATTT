import io
import re
from contextlib import contextmanager
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app.controllers import admin as admin_module
from app.controllers import auth as auth_module
from app.controllers import master as master_module
from app.models import profile_model, staff_model, user_model
from app.models.profile_model import StudentProfile
from app.models.staff_model import StaffProfile
from app.models.user_model import User
from app.services import student_import_service
from app.services.mvp_seed_service import MvpSeedService
from app.services.student_import_service import StudentImportService
from app.utils.temp_password import (
    LEGACY_DEFAULT_PASSWORD,
    TEMP_PASSWORD_ALPHABET,
    TEMP_PASSWORD_LENGTH,
    generate_temp_password,
    hash_temp_password,
)


class FakeCursor:
    """Cursor giả lập: ghi lại câu SQL đã chạy, trả kết quả fetchone theo thứ tự cho trước"""

    def __init__(self, fetchone_results=(), rowcount=1):
        self.queries = []
        self._fetchone_results = list(fetchone_results)
        self.rowcount = rowcount
        self.lastrowid = 0

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        self.lastrowid += 1

    def fetchone(self):
        return self._fetchone_results.pop(0) if self._fetchone_results else None

    def fetchall(self):
        return []

    def close(self):
        pass


def _patch_cursor(monkeypatch, module, cursor):
    @contextmanager
    def fake_get_db_cursor(*args, **kwargs):
        yield cursor

    monkeypatch.setattr(module, 'get_db_cursor', fake_get_db_cursor)


def _login_as(client, user_id, username, role):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['force_password_change'] = False


def _users_insert_or_update(cursor):
    return [(sql, params) for sql, params in cursor.queries if 'users' in sql and ('INSERT' in sql or 'UPDATE' in sql)]


# ---------- Sinh mật khẩu tạm ----------

def test_temp_password_is_random_and_strong():
    """Mật khẩu tạm phải ngẫu nhiên, đủ dài, có chữ hoa/thường/số và không bao giờ là mật khẩu mặc định cũ"""
    passwords = {generate_temp_password() for _ in range(300)}

    assert len(passwords) == 300
    for password in passwords:
        assert len(password) == TEMP_PASSWORD_LENGTH
        assert set(password) <= set(TEMP_PASSWORD_ALPHABET)
        assert re.search(r'[A-Z]', password) and re.search(r'[a-z]', password) and re.search(r'\d', password)
        assert password != LEGACY_DEFAULT_PASSWORD


def test_temp_password_hash_is_salted_and_verifiable():
    password = generate_temp_password()
    first, second = hash_temp_password(password), hash_temp_password(password)

    assert first != second
    assert User.verify_password(first, password)
    assert not User.verify_password(first, LEGACY_DEFAULT_PASSWORD)


def test_no_fixed_default_password_left_in_app_code():
    """Không còn chỗ nào trong mã ứng dụng cấp mật khẩu cố định 123456 (chỉ còn hằng số dùng để chặn DB cũ)"""
    app_dir = Path(__file__).resolve().parent.parent / 'app'
    offenders = [
        str(path) for path in app_dir.rglob('*.py')
        if "'123456'" in path.read_text(encoding='utf-8') and path.name != 'temp_password.py'
    ]
    assert offenders == []


# ---------- Model: tạo/reset tài khoản ----------

def test_reset_student_password_issues_unique_temp_password(monkeypatch):
    cursor = FakeCursor()
    _patch_cursor(monkeypatch, user_model, cursor)

    first = User.reset_student_password('b24dccn001@eduflaw.com')
    sql, params = cursor.queries[-1]
    second = User.reset_student_password('b24dccn001@eduflaw.com')

    assert first and second and first != second
    assert 'must_change_password = TRUE' in sql and 'personal_email = NULL' in sql
    assert User.verify_password(params[0], first)
    assert params[1] == 'b24dccn001@eduflaw.com'


def test_reset_student_password_returns_none_when_account_missing(monkeypatch):
    _patch_cursor(monkeypatch, user_model, FakeCursor(rowcount=0))
    assert User.reset_student_password('khong.ton.tai@eduflaw.com') is None


def test_reset_admin_password_issues_temp_password(monkeypatch):
    cursor = FakeCursor(fetchone_results=[('gv.001@eduflaw.com',)])
    _patch_cursor(monkeypatch, staff_model, cursor)

    username, temp_password = StaffProfile.reset_admin_password(7)
    sql, params = _users_insert_or_update(cursor)[-1]

    assert username == 'gv.001@eduflaw.com'
    assert 'must_change_password = TRUE' in sql
    assert User.verify_password(params[0], temp_password)
    assert temp_password != LEGACY_DEFAULT_PASSWORD


def test_reset_admin_password_ignores_non_admin_accounts(monkeypatch):
    cursor = FakeCursor(fetchone_results=[None])
    _patch_cursor(monkeypatch, staff_model, cursor)

    assert StaffProfile.reset_admin_password(1) is None
    assert _users_insert_or_update(cursor) == []


def test_create_admin_account_uses_temp_password(monkeypatch):
    cursor = FakeCursor(fetchone_results=[None])
    _patch_cursor(monkeypatch, staff_model, cursor)

    success, message, temp_password = StaffProfile.create_admin_account('gv.moi@eduflaw.com', 'Nguyễn Văn A')
    sql, params = _users_insert_or_update(cursor)[0]

    assert success is True and 'thành công' in message
    assert 'must_change_password' in sql and 'TRUE' in sql
    assert User.verify_password(params[1], temp_password)


def test_add_student_profile_uses_temp_password(monkeypatch):
    cursor = FakeCursor()
    _patch_cursor(monkeypatch, profile_model, cursor)

    username, temp_password = StudentProfile.add_student_profile({
        'student_code': 'B24DCCN999', 'full_name': 'Trần Thị B', 'dob': '2006-01-01',
        'gender': 'Nữ', 'major': 'Công nghệ thông tin', 'cohort': 'D24', 'class_name': 'D24CQCN01'
    })
    sql, params = _users_insert_or_update(cursor)[0]

    assert username == 'b24dccn999@eduflaw.com'
    assert 'must_change_password' in sql and 'TRUE' in sql
    assert User.verify_password(params[1], temp_password)


# ---------- Onboarding ----------

def test_complete_onboarding_rejects_reusing_temp_password(monkeypatch):
    temp_password = generate_temp_password() + 'xyz'
    cursor = FakeCursor(fetchone_results=[{'password': hash_temp_password(temp_password)}])
    _patch_cursor(monkeypatch, user_model, cursor)

    success, message = User.complete_onboarding(1, 'sv.that@gmail.com', temp_password)

    assert success is False
    assert 'mật khẩu tạm thời' in message
    assert _users_insert_or_update(cursor) == []


def test_complete_onboarding_clears_must_change_flag(monkeypatch):
    cursor = FakeCursor(fetchone_results=[{'password': hash_temp_password(generate_temp_password())}])
    _patch_cursor(monkeypatch, user_model, cursor)

    success, _ = User.complete_onboarding(1, 'sv.that@gmail.com', 'MatKhauMoi@2026')
    sql, params = _users_insert_or_update(cursor)[0]

    assert success is True
    assert 'must_change_password = FALSE' in sql
    assert User.verify_password(params[0], 'MatKhauMoi@2026')


# ---------- Đăng nhập ----------

@pytest.fixture
def no_profile_db(monkeypatch):
    @contextmanager
    def unavailable_cursor(*args, **kwargs):
        raise RuntimeError('Không dùng CSDL thật trong test')
        yield

    monkeypatch.setattr(auth_module, 'get_db_cursor', unavailable_cursor)


def _patch_login_user(monkeypatch, user):
    monkeypatch.setattr(auth_module.User, 'get_user_by_username', lambda username: user if username == user.username else None)


def test_login_with_temp_password_forces_onboarding(client, monkeypatch, no_profile_db):
    """Tài khoản có must_change_password phải onboarding dù đã có Gmail (ví dụ sau khi được cấp lại mật khẩu)"""
    temp_password = generate_temp_password()
    user = User(5, 'b24dccn005@eduflaw.com', hash_temp_password(temp_password), 'student',
                personal_email='sv.cu@gmail.com', must_change_password=True)
    _patch_login_user(monkeypatch, user)

    response = client.post('/login', data={'username': user.username, 'password': temp_password})

    assert response.status_code == 302
    assert '/onboarding' in response.headers['Location']
    with client.session_transaction() as sess:
        assert sess['force_password_change'] is True


def test_login_after_onboarding_skips_gate(client, monkeypatch, no_profile_db):
    user = User(6, 'b24dccn006@eduflaw.com', hash_temp_password('MatKhauMoi@2026'), 'student',
                personal_email='sv.that@gmail.com', must_change_password=False)
    _patch_login_user(monkeypatch, user)

    response = client.post('/login', data={'username': user.username, 'password': 'MatKhauMoi@2026'})

    assert response.status_code == 302
    assert '/onboarding' not in response.headers['Location']
    with client.session_transaction() as sess:
        assert sess['force_password_change'] is False


@pytest.mark.parametrize('stored_password', [LEGACY_DEFAULT_PASSWORD, hash_temp_password(LEGACY_DEFAULT_PASSWORD)])
def test_legacy_default_password_cannot_activate_account(client, monkeypatch, no_profile_db, stored_password):
    """Tài khoản chưa kích hoạt trên DB cũ còn mật khẩu 123456: không ai đăng nhập vào để gắn Gmail được"""
    user = User(7, 'b24dccn007@eduflaw.com', stored_password, 'student', personal_email=None)
    _patch_login_user(monkeypatch, user)

    response = client.post('/login', data={'username': user.username, 'password': LEGACY_DEFAULT_PASSWORD})

    assert response.status_code == 200
    assert auth_module.LEGACY_PASSWORD_DISABLED_MESSAGE in response.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


# ---------- Route: hiển thị mật khẩu tạm một lần ----------

def _assert_shown_once(response, temp_password, client):
    assert response.status_code == 200
    assert temp_password in response.get_data(as_text=True)
    assert response.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as sess:
        # Mật khẩu tạm không được nằm trong cookie session (flash)
        assert temp_password not in repr(dict(sess))


def test_master_reset_student_password_shows_temp_password_once(client, monkeypatch):
    _login_as(client, 1, 'master@eduflaw.com', 'master')
    monkeypatch.setattr(master_module.User, 'reset_student_password', classmethod(lambda cls, username: 'TamThoi7Kx9P'))

    response = client.post('/master/students/reset_password', data={'username': 'b24dccn001@eduflaw.com'})

    _assert_shown_once(response, 'TamThoi7Kx9P', client)
    assert 'b24dccn001@eduflaw.com' in response.get_data(as_text=True)


def test_advisor_reset_student_password_shows_temp_password_once(client, monkeypatch):
    _login_as(client, 2, 'gv.001@eduflaw.com', 'admin')
    monkeypatch.setattr(admin_module.StudentProfile, 'is_student_assigned_to_advisor', lambda *args: True)
    monkeypatch.setattr(admin_module.User, 'reset_student_password', classmethod(lambda cls, username: 'TamThoi8Mn3Q'))

    response = client.post('/admin/students/reset_password', data={'username': 'b24dccn001@eduflaw.com'})

    _assert_shown_once(response, 'TamThoi8Mn3Q', client)


def test_advisor_cannot_reset_unassigned_student(client, monkeypatch):
    _login_as(client, 2, 'gv.001@eduflaw.com', 'admin')
    monkeypatch.setattr(admin_module.StudentProfile, 'is_student_assigned_to_advisor', lambda *args: False)
    called = []
    monkeypatch.setattr(admin_module.User, 'reset_student_password', classmethod(lambda cls, username: called.append(username)))

    response = client.post('/admin/students/reset_password', data={'username': 'b24dccn001@eduflaw.com'})

    assert response.status_code == 403
    assert called == []


def test_master_reset_admin_password_shows_temp_password_once(client, monkeypatch):
    _login_as(client, 1, 'master@eduflaw.com', 'master')
    monkeypatch.setattr(master_module.StaffProfile, 'reset_admin_password',
                        classmethod(lambda cls, user_id: ('gv.001@eduflaw.com', 'TamThoi9Pq4R')))

    response = client.post('/master/admins/reset_password', data={'user_id': '7'})

    _assert_shown_once(response, 'TamThoi9Pq4R', client)


def test_master_add_admin_ignores_client_supplied_password(client, monkeypatch):
    """Master không còn tự đặt mật khẩu khởi tạo (trước đây mặc định 123456): hệ thống tự sinh"""
    _login_as(client, 1, 'master@eduflaw.com', 'master')
    calls = []

    def fake_create(cls, *args):
        calls.append(args)
        return True, 'Cấp tài khoản cho giảng viên Nguyễn Văn A thành công.', 'TamThoi2Ab5C'

    monkeypatch.setattr(master_module.StaffProfile, 'create_admin_account', classmethod(fake_create))

    response = client.post('/master/admins/add', data={
        'email': 'gv.moi@eduflaw.com', 'full_name': 'Nguyễn Văn A', 'password': LEGACY_DEFAULT_PASSWORD
    })

    assert calls == [('gv.moi@eduflaw.com', 'Nguyễn Văn A')]
    _assert_shown_once(response, 'TamThoi2Ab5C', client)


def test_master_add_student_shows_temp_password_once(client, monkeypatch):
    _login_as(client, 1, 'master@eduflaw.com', 'master')
    monkeypatch.setattr(master_module.StudentProfile, 'get_major_name_by_code', lambda code: 'Công nghệ thông tin')
    monkeypatch.setattr(master_module.StudentProfile, 'add_student_profile',
                        lambda data: (f"{data['student_code'].lower()}@eduflaw.com", 'TamThoi3Cd6E'))

    response = client.post('/master/students/add', data={
        'student_code': 'B24DCCN999', 'full_name': 'Trần Thị B', 'dob': '2006-01-01', 'gender': 'Nữ'
    })

    _assert_shown_once(response, 'TamThoi3Cd6E', client)
    assert 'b24dccn999@eduflaw.com' in response.get_data(as_text=True)


# ---------- Import Excel và seed ----------

class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class FakeImportCursor(FakeCursor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batches = []

    def executemany(self, sql, rows):
        # Ghi lại từng dòng như một lần execute để các assert theo dòng vẫn dùng được
        self.batches.append((sql, list(rows)))
        for params in rows:
            self.queries.append((sql, params))

    def fetchall(self):
        sql, params = self.queries[-1]
        if 'FROM majors' in sql:
            return [('Công nghệ thông tin',)]
        if 'SELECT id, username FROM users' in sql:
            return [(index + 1, username) for index, username in enumerate(params)]
        return []


def test_import_rows_issues_distinct_temp_password_per_student(monkeypatch):
    cursor = FakeImportCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(student_import_service.db_pool, 'get_connection', lambda: connection)
    rows = [
        {'Email': f'b24dccn{i:03d}@eduflaw.com', 'MaSV': f'B24DCCN{i:03d}', 'HoTen': f'Sinh viên {i}',
         'Lop': 'D24CQCN01', 'Nganh': 'Công nghệ thông tin'}
        for i in range(1, 4)
    ]

    count, errors, credentials = StudentImportService.import_rows(rows)
    user_inserts = [params for sql, params in cursor.queries if 'INSERT INTO users' in sql]

    assert (count, errors) == (3, [])
    assert connection.committed
    assert len({item['password'] for item in credentials}) == 3
    assert all('must_change_password' in sql for sql, _ in cursor.queries if 'INSERT INTO users' in sql)
    for item, params in zip(credentials, user_inserts):
        assert params[0] == item['username']
        assert User.verify_password(params[1], item['password'])

    # Chèn theo lô: một executemany cho users và một cho student_profiles, hồ sơ gắn đúng user_id đọc lại
    assert [sql.split('(')[0].split()[-1] for sql, _ in cursor.batches] == ['users', 'student_profiles']
    profile_rows = cursor.batches[1][1]
    assert [row[0] for row in profile_rows] == [1, 2, 3]
    assert [row[1] for row in profile_rows] == ['B24DCCN001', 'B24DCCN002', 'B24DCCN003']


def test_master_import_returns_credentials_workbook(client, monkeypatch):
    _login_as(client, 1, 'master@eduflaw.com', 'master')
    credentials = [{'username': 'b24dccn001@eduflaw.com', 'full_name': 'Sinh viên 1', 'role': 'student', 'password': 'TamThoi4Fg7H'}]
    monkeypatch.setattr(master_module.StudentImportService, 'import_rows', classmethod(lambda cls, rows: (1, [], credentials)))

    workbook = Workbook()
    workbook.active.append(['Email', 'MaSV', 'HoTen', 'Lop', 'Nganh'])
    workbook.active.append(['b24dccn001@eduflaw.com', 'B24DCCN001', 'Sinh viên 1', 'D24CQCN01', 'Công nghệ thông tin'])
    upload = io.BytesIO()
    workbook.save(upload)
    upload.seek(0)

    response = client.post('/master/students/import', data={'excel_file': (upload, 'ds.xlsx')},
                           content_type='multipart/form-data')

    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']
    assert response.headers['Cache-Control'] == 'no-store'
    sheet = load_workbook(io.BytesIO(response.data)).active
    assert [cell.value for cell in sheet[2]] == ['b24dccn001@eduflaw.com', 'Sinh viên 1', 'student', 'TamThoi4Fg7H']


def test_seed_writes_credentials_file(tmp_path):
    path = tmp_path / 'instance' / 'mat_khau_tam.xlsx'
    MvpSeedService._write_credentials_file(str(path), [
        {'username': 'gv.001@eduflaw.com', 'full_name': 'ThS. A', 'role': 'admin', 'password': 'TamThoi5Jk8L'}
    ])

    sheet = load_workbook(path).active
    assert [cell.value for cell in sheet[1]] == ['Tài khoản', 'Họ tên', 'Vai trò', 'Mật khẩu tạm']
    assert sheet['D2'].value == 'TamThoi5Jk8L'
