# app/utils/navigation.py
from urllib.parse import urlparse
from flask import request


def safe_referrer(default):
    """
    Trả về đường dẫn nội bộ từ header Referer để quay lại trang trước.
    Header Referer do client gửi lên nên chỉ chấp nhận URL cùng host; ngược lại dùng `default`
    để tránh lỗ hổng chuyển hướng mở (open redirect).
    """
    referrer = request.referrer
    if not referrer:
        return default

    parsed = urlparse(referrer)
    if parsed.scheme not in ('', 'http', 'https'):
        return default
    if parsed.netloc and parsed.netloc != request.host:
        return default

    path = parsed.path or '/'
    if not path.startswith('/') or path.startswith('//') or '\\' in path:
        return default

    return f"{path}?{parsed.query}" if parsed.query else path
