"""
Mã hóa dữ liệu CCCD (id_card) cũ còn lưu dạng rõ bằng cơ chế mã hóa trường (app/utils/field_crypto.py).

Dùng sau khi áp migration 010 (mở rộng cột id_card). Giải mã đã khoan dung với dữ liệu cũ dạng rõ, nên app
vẫn chạy được ngay cả khi chưa backfill; chạy script này để không còn CCCD dạng rõ nào trong CSDL.

    python -m app.services.pii_backfill_service            # chạy thử, chỉ đếm
    python -m app.services.pii_backfill_service --apply    # mã hóa và ghi vào CSDL

Mỗi bảng được xử lý trong một transaction riêng. An toàn khi chạy lại: chỉ đụng các dòng chưa mã hóa.
"""
import argparse
import sys

from app.utils.field_crypto import ENCRYPTION_PREFIX, encrypt_field, is_encrypted
from db import db_pool

TABLES = ('student_profiles', 'admin_profiles', 'master_profiles')


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


def _plaintext_rows(cursor, table):
    # Chỉ lấy dòng có CCCD và CHƯA mã hóa (không bắt đầu bằng tiền tố)
    cursor.execute(
        f"SELECT id, id_card FROM {table} "
        f"WHERE id_card IS NOT NULL AND id_card <> '' AND id_card NOT LIKE %s",
        (ENCRYPTION_PREFIX + '%',)
    )
    return cursor.fetchall()


def backfill_table(table, apply=False):
    """Trả về số dòng CCCD dạng rõ cần/đã mã hóa cho một bảng."""
    connection = db_pool.get_connection()
    try:
        cursor = connection.cursor()
        rows = _plaintext_rows(cursor, table)
        updates = [(encrypt_field(id_card), row_id) for row_id, id_card in rows if not is_encrypted(id_card)]

        if apply and updates:
            cursor.executemany(f"UPDATE {table} SET id_card = %s WHERE id = %s", updates)
            connection.commit()
        cursor.close()
        return len(updates)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    _make_console_safe()
    parser = argparse.ArgumentParser(description='Mã hóa CCCD (id_card) cũ còn lưu dạng rõ.')
    parser.add_argument('--apply', action='store_true', help='Ghi thay đổi vào CSDL (mặc định chỉ chạy thử).')
    args = parser.parse_args()

    total = 0
    for table in TABLES:
        count = backfill_table(table, apply=args.apply)
        total += count
        print(f'{table}: {count} CCCD dạng rõ' + (' đã mã hóa.' if args.apply else ' sẽ được mã hóa.'))

    if not args.apply:
        print(f'\nChạy thử: tổng {total} CCCD dạng rõ. Thêm --apply để mã hóa thật.')
    else:
        print(f'\nHoàn tất: đã mã hóa {total} CCCD.')


if __name__ == '__main__':
    main()
