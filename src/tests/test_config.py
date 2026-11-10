import os
from config import Config

def test_config_loading():
    """Kiểm tra cấu hình môi trường được nạp chính xác"""
    # Mặc định Secret Key phải tồn tại
    assert Config.SECRET_KEY is not None