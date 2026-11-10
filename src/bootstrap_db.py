"""
Tự chuẩn bị CSDL cho người mới, giảm số bước thủ công:
- CSDL chưa có bảng  -> tạo bảng từ schema.sql rồi seed dữ liệu mẫu (gồm tài khoản Master để đăng nhập).
- CSDL có bảng nhưng chưa có người dùng -> seed dữ liệu mẫu.
- CSDL đã có người dùng -> KHÔNG đụng gì (an toàn với CSDL dùng chung của nhóm).

Mã thoát: 0 = CSDL đã sẵn sàng; 3 = chưa kết nối được CSDL (hãy khởi động CSDL, vd: docker compose up -d).
Chạy: python bootstrap_db.py   (thường do setup.ps1 / setup.sh gọi)
"""
import sys


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


def _users_count():
    """Số tài khoản hiện có. Ném ngoại lệ nếu chưa có bảng hoặc không kết nối được."""
    from app.utils.db_helper import get_db_cursor
    with get_db_cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]


def _is_missing_schema(error):
    message = str(error)
    return "doesn't exist" in message or '1146' in message


def main():
    _make_console_safe()
    from init_db import initialize_database
    from app.services.mvp_seed_service import seed_data

    try:
        count = _users_count()
    except Exception as error:
        if _is_missing_schema(error):
            print('CSDL chưa có bảng -> tạo bảng và seed dữ liệu mẫu...')
            initialize_database()
            seed_data(reset_existing=True)
            print('Đã tạo bảng và seed xong. CSDL sẵn sàng.')
            return 0
        print('Chưa kết nối được CSDL:', type(error).__name__)
        print('Hãy khởi động CSDL rồi chạy lại (vd: docker compose up -d).')
        return 3

    if count == 0:
        print('CSDL trống -> seed dữ liệu mẫu...')
        seed_data(reset_existing=True)
        print('Đã seed xong. CSDL sẵn sàng.')
    else:
        print(f'CSDL đã có {count} tài khoản -> giữ nguyên, không seed lại.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
