# app/utils/temp_password.py
import secrets
from io import BytesIO

from flask import make_response, render_template, send_file
from openpyxl import Workbook
from werkzeug.security import generate_password_hash

# Bỏ các ký tự dễ nhầm (0/O, 1/l/I) để người nhận gõ lại mật khẩu tạm từ giấy/màn hình không bị sai
TEMP_PASSWORD_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
TEMP_PASSWORD_LENGTH = 12
# Mật khẩu tạm ngẫu nhiên ~70 bit nên không cần hàm băm chậm như mật khẩu do người dùng tự đặt.
# 2000 vòng PBKDF2 (~0,6 ms/lần): import 5000 sinh viên mất vài giây thay vì ~30 giây (20000 vòng),
# tránh vượt thời gian chờ của reverse proxy. Mã băm cũ với số vòng khác vẫn xác thực bình thường.
TEMP_PASSWORD_HASH_METHOD = 'pbkdf2:sha256:2000'
# Mật khẩu mặc định dùng chung của phiên bản cũ: không còn được cấp, chỉ dùng để chặn đăng nhập trên DB cũ
LEGACY_DEFAULT_PASSWORD = '123456'


def generate_temp_password(length=TEMP_PASSWORD_LENGTH):
    """Sinh mật khẩu tạm ngẫu nhiên (CSPRNG), luôn có chữ hoa, chữ thường và chữ số"""
    while True:
        password = ''.join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))
        if (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


def hash_temp_password(password):
    return generate_password_hash(password, method=TEMP_PASSWORD_HASH_METHOD)


def issue_temp_password():
    """Trả về (mật khẩu tạm dạng rõ để hiển thị một lần, mã băm để lưu CSDL)"""
    password = generate_temp_password()
    return password, hash_temp_password(password)


def render_issued_credentials(credentials, back_url, message):
    """
    Hiển thị mật khẩu tạm đúng một lần ngay trong phản hồi của request POST.
    Không dùng flash/session vì session Flask nằm trong cookie (chỉ ký, không mã hóa),
    và đặt no-store để trình duyệt/proxy không lưu lại trang chứa mật khẩu.
    """
    response = make_response(render_template(
        'layouts/issued_credentials.html',
        credentials=credentials,
        back_url=back_url,
        message=message
    ))
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


def _excel_text(value):
    """
    openpyxl ghi chuỗi bắt đầu bằng '=' thành công thức: họ tên/email lấy từ file import có thể chứa
    công thức độc hại (CSV/Excel injection). Thêm dấu ' để Excel luôn coi là văn bản.
    """
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


def build_credentials_workbook(credentials):
    """Tạo file Excel (BytesIO) gồm Tài khoản, Họ tên, Vai trò, Mật khẩu tạm để phát cho người dùng"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'MatKhauTam'
    sheet.append(['Tài khoản', 'Họ tên', 'Vai trò', 'Mật khẩu tạm'])
    for item in credentials:
        sheet.append([
            _excel_text(item['username']), _excel_text(item.get('full_name') or ''),
            item.get('role') or '', item['password']
        ])
    for column, width in (('A', 34), ('B', 30), ('C', 12), ('D', 18)):
        sheet.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def send_credentials_workbook(credentials, download_name):
    response = send_file(
        build_credentials_workbook(credentials),
        as_attachment=True,
        download_name=download_name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response.headers['Cache-Control'] = 'no-store'
    return response
