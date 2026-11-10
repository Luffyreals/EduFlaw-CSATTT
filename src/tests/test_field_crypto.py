from contextlib import contextmanager

from flask import Flask

from app.models import staff_model
from app.models.staff_model import StaffProfile
from app.utils.field_crypto import (
    ENCRYPTION_PREFIX,
    decrypt_field,
    decrypt_in_rows,
    encrypt_field,
    is_encrypted,
)

CCCD = '012345678901'


def _ctx(field_key='field-key-abc'):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['FIELD_ENCRYPTION_KEY'] = field_key
    return app


class FakeCursor:
    def __init__(self, fetchone_results=()):
        self.queries = []
        self._fetchone_results = list(fetchone_results)

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        return self._fetchone_results.pop(0) if self._fetchone_results else None

    def fetchall(self):
        return []

    def close(self):
        pass


def _patch_cursor(monkeypatch, cursor):
    @contextmanager
    def fake_get_db_cursor(*args, **kwargs):
        yield cursor

    monkeypatch.setattr(staff_model, 'get_db_cursor', fake_get_db_cursor)


def test_encrypt_decrypt_roundtrip():
    with _ctx().app_context():
        token = encrypt_field(CCCD)
        assert token.startswith(ENCRYPTION_PREFIX)
        assert CCCD not in token            # không lộ CCCD dạng rõ
        assert decrypt_field(token) == CCCD


def test_decrypt_tolerates_legacy_plaintext():
    """Dữ liệu cũ dạng rõ (không tiền tố) trả về nguyên văn; None giữ None"""
    with _ctx().app_context():
        assert decrypt_field(CCCD) == CCCD
        assert decrypt_field(None) is None


def test_encrypt_is_idempotent_and_skips_empty():
    with _ctx().app_context():
        token = encrypt_field(CCCD)
        assert encrypt_field(token) == token    # không mã hóa 2 lần
        assert encrypt_field('') == ''
        assert encrypt_field(None) is None


def test_encrypt_uses_random_nonce():
    with _ctx().app_context():
        assert encrypt_field(CCCD) != encrypt_field(CCCD)


def test_wrong_key_cannot_recover_plaintext():
    """Sai khóa (đổi FIELD_ENCRYPTION_KEY) thì không giải mã ra CCCD gốc — không fail-open"""
    with _ctx('key-one-aaaa').app_context():
        token = encrypt_field(CCCD)
    with _ctx('key-two-bbbb').app_context():
        assert decrypt_field(token) != CCCD


def test_decrypt_in_rows_handles_list_and_dict():
    with _ctx().app_context():
        token = encrypt_field(CCCD)
        rows = [{'id_card': token, 'x': 1}, {'id_card': None}]
        decrypt_in_rows(rows, 'id_card')
        assert rows[0]['id_card'] == CCCD and rows[1]['id_card'] is None

        single = {'id_card': token}
        assert decrypt_in_rows(single, 'id_card')['id_card'] == CCCD


def test_update_admin_profile_stores_encrypted_id_card(monkeypatch):
    """Ghi hồ sơ giảng viên: CCCD phải được mã hóa trước khi vào câu UPDATE"""
    cursor = FakeCursor(fetchone_results=[{'id': 1}])  # admin_profiles đã tồn tại -> nhánh UPDATE
    _patch_cursor(monkeypatch, cursor)
    with _ctx().app_context():
        ok = StaffProfile.update_admin_profile_by_master(1, 'GV A', CCCD, '090', '2000-01-01', 'Nam', 'HN')

    assert ok is True
    update_sql, params = cursor.queries[-1]
    assert 'UPDATE admin_profiles' in update_sql
    stored_id_card = params[1]                       # thứ tự: full_name, id_card, ...
    assert is_encrypted(stored_id_card)
    assert CCCD not in stored_id_card


def test_get_admin_profile_decrypts_id_card(monkeypatch):
    """Đọc hồ sơ giảng viên: CCCD trả về cho controller/template phải là dạng rõ"""
    with _ctx().app_context():
        token = encrypt_field(CCCD)
    cursor = FakeCursor(fetchone_results=[{
        'full_name': 'A', 'id_card': token, 'phone_number': None,
        'date_of_birth': None, 'gender': None, 'address': None
    }])
    _patch_cursor(monkeypatch, cursor)
    with _ctx().app_context():
        profile = StaffProfile.get_admin_profile(1)

    assert profile['id_card'] == CCCD
