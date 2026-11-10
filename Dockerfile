# Ảnh Docker cho web EduFlaw (Flask + waitress). Dùng chung với docker-compose.yml (cùng MySQL).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Cài thư viện trước để tận dụng cache layer (chỉ cài lại khi requirements đổi)
COPY src/requirements.txt ./src/requirements.txt
RUN pip install -r src/requirements.txt

# Mã nguồn + script khởi động
COPY src/ ./src/
COPY docker-entrypoint.sh ./docker-entrypoint.sh
# Khử ký tự CR (nếu file bị CRLF do git trên Windows) để shebang chạy được trong Linux, rồi cho phép thực thi
RUN sed -i 's/\r$//' ./docker-entrypoint.sh && chmod +x ./docker-entrypoint.sh

# Mọi lệnh chạy từ src/ (module import lẫn nhau như module cấp cao nhất, schema.sql là đường dẫn tương đối)
WORKDIR /app/src
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
