#!/bin/sh
# Khởi động container web: chờ CSDL sẵn sàng, tự tạo bảng + seed nếu là CSDL mới, rồi chạy web.
set -e

echo "==> Chuan bi CSDL (tao bang + seed neu CSDL moi)..."
attempt=0
until python bootstrap_db.py; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 20 ]; then
    echo "!! Khong ket noi duoc CSDL sau nhieu lan thu. Dung lai."
    exit 1
  fi
  echo "   CSDL chua san sang, thu lai sau 3s... ($attempt)"
  sleep 3
done

echo "==> Khoi dong web (waitress) tren cong ${PORT:-8000}..."
exec python serve.py
