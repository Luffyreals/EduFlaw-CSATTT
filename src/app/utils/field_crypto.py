# app/utils/field_crypto.py
"""
Mã hóa cấp trường cho PII nhạy cảm (CCCD) ở tầng ứng dụng.

Dữ liệu được mã hóa AES-256-GCM (có xác thực toàn vẹn) trước khi lưu vào CSDL, nên một bản dump CSDL hay
người có quyền đọc CSDL cũng không thấy được CCCD dạng rõ (khóa không nằm trong CSDL). Đây là phòng thủ bổ
sung cho mã hóa at-rest (TDE) của hạ tầng, vốn không bảo vệ trước truy vấn CSDL thông thường.

Khóa lấy từ FIELD_ENCRYPTION_KEY (khuyến nghị đặt riêng); nếu trống thì dẫn xuất tạm từ SECRET_KEY.
Giải mã khoan dung với dữ liệu cũ dạng rõ (giá trị không có tiền tố coi như plaintext, trả về nguyên văn),
giống cách nâng cấp dần mật khẩu cũ — nên có thể bật mã hóa mà không cần migration bắt buộc ngay.
"""
import base64
import logging
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app, has_app_context

from config import Config

ENCRYPTION_PREFIX = 'enc:v1:'
_NONCE_BYTES = 12
_HKDF_INFO = b'eduflaw-field-encryption-v1'
_key_cache = {}
_logger = logging.getLogger(__name__)


def _key_material():
    """Nguồn khóa: FIELD_ENCRYPTION_KEY nếu có, ngược lại SECRET_KEY. Đọc từ app config khi trong app context."""
    if has_app_context():
        cfg = current_app.config
        material = cfg.get('FIELD_ENCRYPTION_KEY') or cfg.get('SECRET_KEY')
    else:
        material = Config.FIELD_ENCRYPTION_KEY or Config.SECRET_KEY
    if not material:
        raise RuntimeError('Thiếu FIELD_ENCRYPTION_KEY/SECRET_KEY để mã hóa trường PII.')
    return material


def _aes():
    material = _key_material()
    cached = _key_cache.get(material)
    if cached is None:
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(material.encode('utf-8'))
        cached = _key_cache[material] = AESGCM(key)
    return cached


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(ENCRYPTION_PREFIX)


def encrypt_field(value):
    """Mã hóa một giá trị để lưu CSDL. None/'' giữ nguyên; giá trị đã mã hóa không mã hóa lại (tránh mã hóa 2 lần)."""
    if value is None:
        return None
    text = str(value)
    if text == '' or is_encrypted(text):
        return text
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = _aes().encrypt(nonce, text.encode('utf-8'), None)
    return ENCRYPTION_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode('ascii')


def decrypt_field(value):
    """Giải mã giá trị đọc từ CSDL. Dữ liệu cũ dạng rõ (không tiền tố) trả về nguyên văn. Lỗi giải mã: ghi log, trả nguyên văn."""
    if not is_encrypted(value):
        return value
    try:
        raw = base64.urlsafe_b64decode(value[len(ENCRYPTION_PREFIX):].encode('ascii'))
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return _aes().decrypt(nonce, ciphertext, None).decode('utf-8')
    except Exception:
        # Thường do sai khóa (đổi FIELD_ENCRYPTION_KEY) hoặc dữ liệu hỏng: không làm sập request
        _logger.error('Không giải mã được trường PII (kiểm tra FIELD_ENCRYPTION_KEY).')
        return value


def decrypt_in_rows(rows, *fields):
    """Giải mã các cột `fields` trong một dict hoặc danh sách dict (kết quả truy vấn), sửa tại chỗ và trả về chính nó."""
    if rows is None:
        return rows
    records = rows if isinstance(rows, list) else [rows]
    for record in records:
        if isinstance(record, dict):
            for field in fields:
                if field in record:
                    record[field] = decrypt_field(record[field])
    return rows
