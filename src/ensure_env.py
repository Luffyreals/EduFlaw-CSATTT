"""
Chuẩn bị file .env cho người mới: tạo .env từ .env.example (nếu chưa có) và TỰ SINH các khóa bí mật còn trống
(SECRET_KEY, FIELD_ENCRYPTION_KEY, MASTER_PASSWORD) để không phải tự điền tay.

Chạy lại nhiều lần an toàn: chỉ điền các giá trị đang trống, không ghi đè giá trị đã có; không in giá trị bí mật.
Được setup.ps1 / setup.sh gọi; cũng chạy trực tiếp được: python ensure_env.py
"""
import re
import secrets
import sys
from pathlib import Path


def _make_console_safe():
    """Console Windows (cp1252) không in được tiếng Việt: tránh UnicodeEncodeError làm hỏng script."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            try:
                stream.reconfigure(errors='replace')
            except (AttributeError, ValueError):
                pass

# Các khóa tự sinh nếu đang trống: (tên biến, hàm sinh giá trị)
_GENERATORS = {
    'SECRET_KEY': lambda: secrets.token_hex(32),
    'FIELD_ENCRYPTION_KEY': lambda: secrets.token_hex(32),
    'MASTER_PASSWORD': lambda: secrets.token_urlsafe(12),  # >= 12 ký tự cho seed tài khoản Master
}


def _current_value(text, name):
    match = re.search(rf'(?m)^\s*{re.escape(name)}\s*=(.*)$', text)
    return match.group(1).strip() if match else None


def _set_value(text, name, value):
    if re.search(rf'(?m)^\s*{re.escape(name)}\s*=.*$', text):
        return re.sub(rf'(?m)^\s*{re.escape(name)}\s*=.*$', f'{name}={value}', text, count=1)
    return text.rstrip('\n') + f'\n{name}={value}\n'


def ensure_env(env_path='.env', example_path='.env.example'):
    """Đảm bảo .env tồn tại và các khóa bí mật đã có. Trả về danh sách tên khóa vừa sinh."""
    path = Path(env_path)
    created = False
    if not path.exists():
        example = Path(example_path)
        if not example.exists():
            raise FileNotFoundError(f'Không tìm thấy {example_path} để tạo {env_path}.')
        path.write_text(example.read_text(encoding='utf-8-sig'), encoding='utf-8')
        created = True

    text = path.read_text(encoding='utf-8-sig')
    generated = []
    for name, generate in _GENERATORS.items():
        if not _current_value(text, name):
            text = _set_value(text, name, generate())
            generated.append(name)
    if generated:
        path.write_text(text, encoding='utf-8')
    return created, generated


def main():
    _make_console_safe()
    created, generated = ensure_env()
    if created:
        print('Đã tạo .env từ .env.example.')
    else:
        print('.env đã có, giữ nguyên.')
    if generated:
        # Chỉ in TÊN khóa đã sinh, không in giá trị
        print('Đã tự sinh khóa (không in giá trị): ' + ', '.join(generated))
    else:
        print('Các khóa bí mật đã có sẵn.')


if __name__ == '__main__':
    main()
