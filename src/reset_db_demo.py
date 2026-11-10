"""
reset_db_demo.py - Xóa sạch dữ liệu cũ và thiết lập lại bộ dữ liệu Demo Tinh Gọn (20 sinh viên, 5 giảng viên).
Dùng khi muốn reset database để thuyết trình hoặc sau khi lỡ seed dữ liệu lớn.

Cách chạy:
    cd src
    .venv\\Scripts\\python reset_db_demo.py
"""
import sys
import os

def _make_console_safe():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

def main():
    _make_console_safe()
    print("=" * 65)
    print("  EduFlaw - RESET CSDL SANG CHẾ ĐỘ DEMO TINH GỌN (NHÓM 7 - PTIT)")
    print("=" * 65)

    # 1. Kiểm tra cấu hình và kết nối CSDL
    from config import Config
    from db import db_pool
    print(f"\n[1/3] Đang kiểm tra kết nối MySQL ({Config.MYSQL_HOST}:{Config.MYSQL_PORT})...")
    try:
        conn = db_pool.get_connection()
        conn.close()
        print("  -> Kết nối MySQL thành công!")
    except Exception as err:
        print(f"\n❌ LỖI KẾT NỐI CSDL: {err}")
        print("\n👉 Hướng dẫn khắc phục:")
        print("   1. Mở file 'src/.env' bằng trình soạn thảo (Notepad / VS Code).")
        print("   2. Kiểm tra dòng MYSQL_PASSWORD=")
        print("      - Nếu MySQL máy bạn có mật khẩu root, hãy điền: MYSQL_PASSWORD=mat_khau_cua_ban")
        print("      - Nếu chưa tạo database eduflaw_db, hãy mở MySQL chạy lệnh:")
        print("        CREATE DATABASE eduflaw_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print("   3. Lưu file .env và chạy lại script này.\n")
        return 1

    # 2. Khởi tạo cấu trúc bảng (schema.sql)
    print("\n[2/3] Đang làm mới cấu trúc bảng từ schema.sql...")
    from init_db import initialize_database
    initialize_database()

    # 3. Nạp dữ liệu Demo Tinh Gọn
    print("\n[3/3] Đang dọn sạch dữ liệu cũ và nạp bộ dữ liệu Demo Tinh Gọn...")
    from app.services.mvp_seed_service import seed_data
    result = seed_data(reset_existing=True, full_dataset=False)

    print("\n" + "=" * 65)
    print("  🎉 HOÀN TẤT THIẾT LẬP BỘ DỮ LIỆU DEMO!")
    print("=" * 65)
    print(f"  - Khoá đào tạo     : {result['cohorts']} khoá (D24 - Năm 3)")
    print(f"  - Ngành đào tạo    : {result['majors']} ngành (ATTT & CNTT)")
    print(f"  - Lớp hành chính   : {result['admin_classes']} lớp (D24CQAT01, D24CQCN01)")
    print(f"  - Tổng sinh viên   : {result['students']} sinh viên (Mỗi ngành 10 SV)")
    print(f"  - Tổng giảng viên  : {result['lecturers']} giảng viên (gv.001 .. gv.005)")
    print(f"  - Tổng lớp tín chỉ : {result['credit_classes']} lớp (Kỳ 2025-S2 & 2026-S1)")
    print(f"  - Tổng lượt điểm   : {result['enrollments']} bản ghi điểm")

    print("\n" + "-" * 65)
    print("  📋 THÔNG TIN TÀI KHOẢN ĐĂNG NHẬP DEMO:")
    print("-" * 65)
    print(f"  👑 Quản trị Master : master@eduflaw.com")
    print(f"     Mật khẩu        : {os.getenv('MASTER_PASSWORD', 'tung12345678')}")
    print()
    print(f"  👨‍🏫 Giảng viên      : gv.001@eduflaw.com .. gv.005@eduflaw.com")
    print(f"     Mật khẩu chung  : EduFlaw@2026")
    print()
    print(f"  🛡️ Sinh viên ATTT  : b24dcat001@eduflaw.com .. b24dcat010@eduflaw.com")
    print(f"     Mã SV           : B24DCAT001 .. B24DCAT010")
    print(f"     Mật khẩu chung  : EduFlaw@2026")
    print()
    print(f"  💻 Sinh viên CNTT  : b24dccn001@eduflaw.com .. b24dccn010@eduflaw.com")
    print(f"     Mã SV           : B24DCCN001 .. B24DCCN010")
    print(f"     Mật khẩu chung  : EduFlaw@2026")
    print("-" * 65)
    if result['credentials_file']:
        print(f"  🔑 File Excel lưu mật khẩu: {result['credentials_file']}")
    print("=" * 65)
    print("\nBây giờ bạn có thể khởi chạy web để demo: python run.py\n")
    return 0

if __name__ == '__main__':
    sys.exit(main())
