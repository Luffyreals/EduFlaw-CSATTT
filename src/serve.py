"""Chạy production bằng waitress (chạy được cả Windows/Linux): python serve.py

Nhiều worker: chạy nhiều tiến trình sau reverse proxy (khóa đăng nhập và OTP nằm trong CSDL nên dùng chung được).
"""
import os
import time

from waitress import serve

from app import create_app
from db import db_pool

app = create_app(os.getenv('APP_ENV') or 'production')


def warm_up_database():
    """Tạo sẵn pool kết nối trước khi nhận request: pool mở toàn bộ kết nối một lượt, với CSDL ở xa (TiDB Cloud)
    mất vài giây, nếu để lười thì người dùng đầu tiên phải chờ. Lỗi chỉ ghi cảnh báo, app vẫn chạy và thử lại sau."""
    started = time.monotonic()
    try:
        db_pool.get_connection().close()
        app.logger.info('Đã kết nối CSDL sau %.1f giây.', time.monotonic() - started)
    except Exception as err:
        app.logger.warning('Chưa kết nối được CSDL lúc khởi động (%s): sẽ thử lại khi có request.', type(err).__name__)


if __name__ == '__main__':
    warm_up_database()
    serve(
        app,
        host=os.getenv('HOST') or '0.0.0.0',
        port=int(os.getenv('PORT') or 8000),
        threads=int(os.getenv('WAITRESS_THREADS') or 8),
    )
