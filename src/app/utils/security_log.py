# app/utils/security_log.py
from flask import current_app, has_request_context, request


def _clean(value):
    """Loại ký tự xuống dòng để kẻ tấn công không chèn được dòng log giả (log injection); cắt ngắn để log gọn"""
    return str(value).replace('\r', ' ').replace('\n', ' ')[:200]


def log_security_event(event, **fields):
    """
    Ghi một dòng log sự kiện an ninh (đăng nhập sai, kích hoạt khóa, cấp lại/đổi mật khẩu, khóa tài khoản...).

    Chỉ ghi định danh tài khoản, IP và loại sự kiện — TUYỆT ĐỐI không ghi mật khẩu, mã OTP hay dữ liệu nhạy cảm.
    Lỗi ghi log không được làm hỏng request, nên nuốt mọi ngoại lệ.
    """
    try:
        ip = request.remote_addr if has_request_context() else '-'
        detail = ' '.join(f'{key}={_clean(value)}' for key, value in fields.items() if value not in (None, ''))
        message = f'[SECURITY] event={_clean(event)} ip={ip}' + (f' {detail}' if detail else '')
        current_app.logger.info(message)
    except Exception:
        pass
