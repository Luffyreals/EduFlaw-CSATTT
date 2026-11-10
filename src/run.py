import os

from app import create_app

# APP_ENV=production để tắt chế độ debug (Werkzeug debugger cho phép chạy mã tùy ý nếu bị lộ ra ngoài)
app = create_app(os.getenv('APP_ENV') or 'development')

if __name__ == '__main__':
    # Chỉ dùng cho phát triển. Production chạy bằng `python serve.py` (waitress), xem README
    app.run(host=os.getenv('HOST') or '127.0.0.1', port=int(os.getenv('PORT') or 5000))
