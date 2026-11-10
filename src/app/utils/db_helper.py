# app/utils/db_helper.py
from contextlib import contextmanager
import mysql.connector
from db import db_pool
from flask import current_app, g, has_app_context


def _acquire_connection():
    """
    Trong app/request context: mọi get_db_cursor dùng chung một kết nối, trả về pool ở teardown
    (mỗi lần mượn/trả kết nối tới CSDL từ xa tốn một vòng mạng). Ngoài context (script seed, init_db)
    mượn riêng cho từng lần. Trả về (kết nối, có phải tự đóng hay không).
    """
    if has_app_context():
        connection = g.get('_db_connection')
        if connection is None:
            connection = g._db_connection = db_pool.get_connection()
        return connection, False
    return db_pool.get_connection(), True


def release_request_connection(exception=None):
    """Đăng ký bằng app.teardown_appcontext: trả kết nối của request về pool (rollback phần chưa commit)"""
    connection = g.pop('_db_connection', None)
    if connection is not None:
        connection.close()


@contextmanager
def get_db_cursor(dictionary=False, commit=False):
    """
    Context manager tự động quản lý kết nối CSDL và xử lý transaction.
    - dictionary=True: Trả về kết quả dạng dict (cột: giá trị)
    - commit=True: Tự động commit nếu không có lỗi, tự động rollback nếu có lỗi
    Cursor luôn buffered để các khối chỉ đọc một phần kết quả (fetchone) không để lại
    "unread result" trên kết nối dùng chung.
    """
    connection = None
    owns_connection = False
    cursor = None
    try:
        connection, owns_connection = _acquire_connection()
        cursor = connection.cursor(dictionary=dictionary, buffered=True)
        yield cursor

        if commit:
            connection.commit()
    except Exception as err:
        # Rollback với mọi lỗi (không chỉ lỗi CSDL): kết nối được dùng tiếp trong request,
        # nên thay đổi dở dang không được để lại cho khối commit sau
        if connection is not None and commit:
            try:
                connection.rollback()
            except mysql.connector.Error:
                pass

        if isinstance(err, mysql.connector.Error):
            # Ghi log lỗi thay vì dùng print()
            if current_app:
                current_app.logger.error(f"Database Error: {err}")
            else:
                print(f"Database Error: {err}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection is not None and owns_connection:
            connection.close()
