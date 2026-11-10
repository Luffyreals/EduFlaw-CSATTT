# app/utils/password_policy.py
MIN_PASSWORD_LENGTH = 12

# Danh sách mật khẩu phổ biến/dễ đoán, kiểm tra OFFLINE (không gọi API ngoài để tránh lộ mật khẩu,
# thêm độ trễ và phụ thuộc mạng ở luồng đặt mật khẩu). So khớp sau khi chuẩn hóa chữ thường.
# Chỉ cần liệt kê các mật khẩu dài >= MIN_PASSWORD_LENGTH; mật khẩu ngắn hơn đã bị chặn bởi độ dài.
COMMON_PASSWORDS = frozenset({
    '123456789012', '1234567890123', '12345678901234', '123456789012345',
    'password1234', 'password12345', 'password@123', 'passw0rd@123',
    'qwerty123456', 'qwertyuiop12', 'qwertyuiop123', 'qwerty@12345',
    'matkhau12345', 'matkhau@123', 'admin1234567', 'administrator1',
    'iloveyou1234', 'welcome12345', 'letmein12345', 'abc123456789',
    'eduflaw12345', 'eduflaw@2026', 'sinhvien1234', 'giangvien123',
})

LENGTH_MESSAGE = f"Mật khẩu mới phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự."
COMMON_MESSAGE = "Mật khẩu này quá phổ biến hoặc dễ đoán. Vui lòng chọn mật khẩu khác."
SIMPLE_MESSAGE = "Mật khẩu quá đơn giản (lặp lại quá ít ký tự). Vui lòng chọn mật khẩu phức tạp hơn."


def validate_password_strength(password):
    """
    Kiểm tra độ mạnh mật khẩu phía máy chủ (offline). Trả về (hợp lệ, thông báo lỗi).
    - Đủ độ dài tối thiểu
    - Không nằm trong danh sách mật khẩu phổ biến/dễ đoán
    - Không lặp lại quá ít ký tự khác nhau (vd 'aaaaaaaaaaaa', '121212121212')
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        return False, LENGTH_MESSAGE
    if password.strip().lower() in COMMON_PASSWORDS:
        return False, COMMON_MESSAGE
    if len(set(password)) <= 2:
        return False, SIMPLE_MESSAGE
    return True, ''
