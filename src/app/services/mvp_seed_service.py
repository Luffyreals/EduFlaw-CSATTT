import argparse
import os
import random
import sys
import time
from werkzeug.security import generate_password_hash
from app.utils.field_crypto import encrypt_field
from app.utils.temp_password import build_credentials_workbook, issue_temp_password
from db import db_pool

# =====================================================================
# CẤU HÌNH CƠ BẢN: 3 KHOÁ (D24, D25, D26) - 10 NGÀNH - 4 LỚP/NGÀNH/KHOÁ
# =====================================================================
COHORTS = ('D24', 'D25', 'D26')
STUDENTS_PER_MAJOR_COHORT = 100
ADMIN_CLASSES_PER_MAJOR_COHORT = 4  # 100 SV / 4 lớp = 25 SV / lớp hành chính
SEMESTER = 1
ACADEMIC_YEAR = 2026

# Lộ trình các học kỳ đã và đang học của từng khoá: (year, semester, stage_index)
COHORT_TIMELINE = {
    # D24 (Sinh viên năm 3): Từ Kỳ 1 năm 1 (2024) đến Kỳ 1 năm 3 (2026) -> 5 học kỳ
    'D24': (
        (2024, 1, 1),
        (2024, 2, 2),
        (2025, 1, 3),
        (2025, 2, 4),
        (2026, 1, 5),
    ),
    # D25 (Sinh viên năm 2): Từ Kỳ 1 năm 1 (2025) đến Kỳ 1 năm 2 (2026) -> 3 học kỳ
    'D25': (
        (2025, 1, 1),
        (2025, 2, 2),
        (2026, 1, 3),
    ),
    # D26 (Sinh viên năm 1): Kỳ 1 năm 1 (2026) -> 1 học kỳ
    'D26': (
        (2026, 1, 1),
    ),
}

MAJORS_CONFIG = (
    ('Công nghệ thông tin', 'CN', 100),
    ('An toàn thông tin', 'AT', 100),
    ('Khoa học máy tính', 'KH', 100),
    ('Công nghệ Đa phương tiện', 'PT', 100),
    ('Kỹ thuật Điện tử Viễn thông', 'VT', 100),
    ('Kỹ thuật Điện - Điện tử', 'DT', 100),
    ('Quản trị kinh doanh', 'QT', 100),
    ('Marketing', 'MR', 100),
    ('Kế toán', 'KT', 100),
    ('Thương mại điện tử', 'TM', 100),
)

# Danh mục Môn học: mã môn -> (Tên môn học, Số tín chỉ, Trọng số (CC, BTTL, TBKT, TGK, TNTH, THI))
SUBJECT_CATALOG = {
    # --- Giai đoạn 1: Học kỳ 1 Năm nhất (Đại cương 1) ---
    'BAS101': ('Giải tích 1', 3, (10, 0, 20, 0, 0, 70)),
    'BAS102': ('Đại số tuyến tính', 3, (10, 0, 20, 0, 0, 70)),
    'BAS103': ('Triết học Mác - Lênin', 3, (10, 10, 10, 0, 0, 70)),
    'BAS104': ('Pháp luật đại cương', 2, (10, 0, 20, 0, 0, 70)),
    'BAS105': ('Tiếng Anh học thuật 1', 3, (10, 10, 20, 0, 0, 60)),
    'BAS106': ('Tin học cơ sở 1', 3, (10, 0, 10, 0, 10, 70)),
    'BAS107': ('Lập trình C cơ bản', 3, (10, 0, 10, 0, 10, 70)),
    'BAS108': ('Vật lý bán dẫn', 3, (10, 0, 10, 10, 0, 70)),
    'BAS109': ('Kinh tế vi mô', 3, (10, 10, 10, 0, 0, 70)),
    'BAS110': ('Nhập môn Quản trị kinh doanh', 3, (10, 10, 10, 0, 0, 70)),
    'BAS111': ('Toán cao cấp Kinh tế 1', 3, (10, 0, 20, 0, 0, 70)),
    'BAS112': ('Nguyên lý thống kê kinh tế', 3, (10, 10, 10, 0, 0, 70)),
    'BAS113': ('Cơ sở tạo hình và Mỹ thuật', 3, (10, 20, 10, 0, 0, 60)),

    # --- Giai đoạn 2: Học kỳ 2 Năm nhất (Đại cương 2) ---
    'BAS121': ('Giải tích 2', 3, (10, 0, 20, 0, 0, 70)),
    'BAS122': ('Xác suất thống kê', 3, (10, 0, 20, 0, 0, 70)),
    'BAS123': ('Kinh tế chính trị Mác - Lênin', 2, (10, 10, 10, 0, 0, 70)),
    'BAS124': ('Tiếng Anh học thuật 2', 3, (10, 10, 20, 0, 0, 60)),
    'BAS125': ('Kỹ thuật lập trình', 3, (10, 0, 10, 0, 10, 70)),
    'BAS126': ('Vật lý đại cương', 3, (10, 0, 10, 10, 0, 70)),
    'BAS127': ('Kỹ năng giao tiếp và Làm việc nhóm', 2, (10, 20, 10, 0, 0, 60)),
    'BAS128': ('Kinh tế vĩ mô', 3, (10, 10, 10, 0, 0, 70)),
    'BAS129': ('Toán cao cấp Kinh tế 2', 3, (10, 0, 20, 0, 0, 70)),
    'BAS130': ('Nhập môn Thiết kế Đa phương tiện', 3, (10, 20, 10, 0, 0, 60)),
    'BAS131': ('Nhập môn Thương mại điện tử', 3, (10, 10, 10, 0, 0, 70)),
    'BAS132': ('Tin học ứng dụng kinh doanh', 3, (10, 0, 10, 0, 10, 70)),

    # --- Giai đoạn 3: Học kỳ 1 Năm hai (Cơ sở ngành 1) ---
    'IT201': ('Cấu trúc dữ liệu và giải thuật', 3, (10, 0, 10, 0, 10, 70)),
    'IT202': ('Cơ sở dữ liệu', 3, (10, 10, 10, 0, 0, 70)),
    'IT203': ('Kiến trúc máy tính', 3, (10, 0, 20, 0, 0, 70)),
    'IT207': ('Toán rời rạc', 3, (10, 0, 20, 0, 0, 70)),
    'CS201': ('Chủ nghĩa xã hội khoa học', 2, (10, 10, 10, 0, 0, 70)),
    'CS202': ('Tiếng Anh chuyên ngành 1', 3, (10, 10, 20, 0, 0, 60)),
    'EL201': ('Lý thuyết mạch điện', 3, (10, 0, 10, 10, 0, 70)),
    'EL202': ('Điện tử tương tự', 3, (10, 0, 10, 0, 10, 70)),
    'EL204': ('Tín hiệu và hệ thống', 3, (10, 0, 20, 0, 0, 70)),
    'BZ201': ('Nguyên lý kế toán', 3, (10, 0, 20, 0, 0, 70)),
    'BZ202': ('Quản trị học', 3, (10, 10, 10, 0, 0, 70)),
    'BZ203': ('Nguyên lý Marketing', 3, (10, 10, 10, 0, 0, 70)),
    'BZ206': ('Kinh tế lượng', 3, (10, 10, 10, 0, 0, 70)),
    'PT201': ('Đồ họa Vector và Xử lý ảnh số', 3, (10, 20, 10, 0, 0, 60)),
    'PT202': ('Kịch bản và Phân cảnh Đa phương tiện', 3, (10, 20, 10, 0, 0, 60)),

    # --- Giai đoạn 4: Học kỳ 2 Năm hai (Cơ sở ngành 2) ---
    'IT204': ('Hệ điều hành', 3, (10, 10, 10, 0, 0, 70)),
    'IT205': ('Lập trình Hướng đối tượng', 3, (10, 10, 0, 0, 10, 70)),
    'IT206': ('Mạng máy tính', 3, (10, 0, 10, 0, 10, 70)),
    'IT208': ('Lập trình Python', 3, (10, 10, 0, 0, 10, 70)),
    'CS203': ('Lịch sử Đảng Cộng sản Việt Nam', 2, (10, 10, 10, 0, 0, 70)),
    'CS204': ('Tư tưởng Hồ Chí Minh', 2, (10, 10, 10, 0, 0, 70)),
    'EL203': ('Điện tử số', 3, (10, 0, 10, 0, 10, 70)),
    'EL205': ('Kỹ thuật vi xử lý', 3, (10, 10, 0, 0, 10, 70)),
    'EL206': ('Trường điện từ', 3, (10, 0, 20, 0, 0, 70)),
    'EL207': ('Cấu kiện điện tử', 3, (10, 0, 10, 0, 10, 70)),
    'BZ204': ('Tài chính doanh nghiệp', 3, (10, 10, 10, 0, 0, 70)),
    'BZ205': ('Hệ thống thông tin quản lý', 3, (10, 10, 10, 0, 0, 70)),
    'BZ207': ('Luật kinh doanh', 3, (10, 10, 10, 0, 0, 70)),
    'BZ208': ('Phương pháp nghiên cứu kinh doanh', 3, (10, 10, 10, 0, 0, 70)),
    'PT203': ('Thiết kế Ấn phẩm Điện tử', 3, (10, 20, 10, 0, 0, 60)),
    'PT204': ('Kỹ thuật Nhiếp ảnh và Quay phim', 3, (10, 20, 10, 0, 0, 60)),

    # --- Giai đoạn 5: Học kỳ 1 Năm ba (Chuyên ngành sâu) ---
    'CN301': ('Lập trình Web', 3, (10, 10, 10, 0, 0, 70)),
    'CN302': ('Công nghệ phần mềm', 3, (10, 10, 10, 0, 0, 70)),
    'CN303': ('Phát triển ứng dụng di động', 3, (10, 10, 0, 0, 10, 70)),
    'CN304': ('Điện toán đám mây', 3, (10, 10, 10, 0, 0, 70)),
    'CN305': ('Phân tích và thiết kế hệ thống', 3, (10, 10, 10, 0, 0, 70)),
    'CN306': ('Kiểm thử và đảm bảo chất lượng PM', 3, (10, 10, 10, 0, 0, 70)),
    'AT301': ('An toàn mạng máy tính', 3, (10, 0, 10, 0, 10, 70)),
    'AT302': ('Kiểm thử xâm nhập (Pentest)', 3, (10, 10, 0, 0, 10, 70)),
    'AT303': ('Bảo mật ứng dụng Web', 3, (10, 10, 0, 0, 10, 70)),
    'AT304': ('Mật mã học ứng dụng', 3, (10, 0, 20, 0, 0, 70)),
    'AT305': ('Điều tra số và Phân tích mã độc', 3, (10, 10, 0, 0, 10, 70)),
    'KH301': ('Trí tuệ nhân tạo', 3, (10, 10, 10, 0, 0, 70)),
    'KH302': ('Học máy (Machine Learning)', 3, (10, 10, 10, 0, 0, 70)),
    'KH303': ('Học sâu (Deep Learning)', 3, (10, 10, 0, 0, 10, 70)),
    'KH304': ('Xử lý ngôn ngữ tự nhiên', 3, (10, 10, 10, 0, 0, 70)),
    'KH305': ('Thị giác máy tính', 3, (10, 10, 0, 0, 10, 70)),
    'PT301': ('Thiết kế giao diện UI/UX', 3, (10, 20, 10, 0, 0, 60)),
    'PT302': ('Kỹ xảo và Hoạt hình 3D', 3, (10, 20, 10, 0, 0, 60)),
    'PT303': ('Lập trình Game 2D/3D', 3, (10, 10, 0, 0, 10, 70)),
    'PT304': ('Sản xuất Audio và Video số', 3, (10, 20, 10, 0, 0, 60)),
    'VT301': ('Kỹ thuật thông tin số', 3, (10, 0, 20, 0, 0, 70)),
    'VT302': ('Thông tin di động 5G', 3, (10, 10, 10, 0, 0, 70)),
    'VT303': ('Kỹ thuật Anten và Siêu cao tần', 3, (10, 0, 10, 0, 10, 70)),
    'VT304': ('Mạng viễn thông thế hệ mới', 3, (10, 10, 10, 0, 0, 70)),
    'VT305': ('Xử lý tín hiệu số DSP', 3, (10, 0, 10, 0, 10, 70)),
    'DT301': ('Hệ thống nhúng và IoT', 3, (10, 10, 0, 0, 10, 70)),
    'DT302': ('Thiết kế vi mạch VLSI', 3, (10, 10, 0, 0, 10, 70)),
    'DT303': ('Lý thuyết điều khiển tự động', 3, (10, 0, 20, 0, 0, 70)),
    'DT304': ('Điện tử công suất', 3, (10, 0, 10, 0, 10, 70)),
    'DT305': ('Cảm biến và Kỹ thuật đo lường', 3, (10, 0, 10, 0, 10, 70)),
    'QT301': ('Quản trị chiến lược', 3, (10, 10, 10, 0, 0, 70)),
    'QT302': ('Quản trị nguồn nhân lực', 3, (10, 10, 10, 0, 0, 70)),
    'QT303': ('Quản trị chuỗi cung ứng Logistics', 3, (10, 10, 10, 0, 0, 70)),
    'QT304': ('Quản trị dự án đầu tư', 3, (10, 10, 10, 0, 0, 70)),
    'QT305': ('Khởi nghiệp và Đổi mới sáng tạo', 3, (10, 20, 10, 0, 0, 60)),
    'MR301': ('Digital Marketing', 3, (10, 10, 10, 0, 0, 70)),
    'MR302': ('Quản trị thương hiệu', 3, (10, 10, 10, 0, 0, 70)),
    'MR303': ('Nghiên cứu thị trường', 3, (10, 10, 10, 0, 0, 70)),
    'MR304': ('Truyền thông Marketing tích hợp', 3, (10, 10, 10, 0, 0, 70)),
    'MR305': ('Hành vi khách hàng', 3, (10, 10, 10, 0, 0, 70)),
    'KT301': ('Kế toán tài chính nâng cao', 3, (10, 0, 20, 0, 0, 70)),
    'KT302': ('Kế toán quản trị', 3, (10, 0, 20, 0, 0, 70)),
    'KT303': ('Kiểm toán căn bản', 3, (10, 10, 10, 0, 0, 70)),
    'KT304': ('Thuế và Kế toán thuế', 3, (10, 0, 20, 0, 0, 70)),
    'KT305': ('Phân tích báo cáo tài chính', 3, (10, 10, 10, 0, 0, 70)),
    'TM301': ('Hệ thống Thương mại điện tử', 3, (10, 10, 10, 0, 0, 70)),
    'TM302': ('Thanh toán điện tử và Fintech', 3, (10, 10, 10, 0, 0, 70)),
    'TM303': ('Quản trị quan hệ khách hàng CRM', 3, (10, 10, 10, 0, 0, 70)),
    'TM304': ('Phân tích dữ liệu kinh doanh số', 3, (10, 10, 10, 0, 0, 70)),
}

# Lộ trình 5 giai đoạn học kỳ (Stage 1 -> Stage 5) cho từng ngành (6 môn/kỳ, hoàn toàn không trùng lặp giữa các kỳ)
STAGE_CURRICULUM = {
    # --- STAGE 1: KỲ 1 NĂM NHẤT (D24 học năm 2024-S1, D25 học năm 2025-S1, D26 học năm 2026-S1) ---
    ('CN', 1): ('BAS101', 'BAS102', 'BAS103', 'BAS105', 'BAS106', 'BAS107'),
    ('AT', 1): ('BAS101', 'BAS102', 'BAS103', 'BAS104', 'BAS106', 'BAS107'),
    ('KH', 1): ('BAS101', 'BAS102', 'BAS103', 'BAS105', 'BAS106', 'BAS107'),
    ('PT', 1): ('BAS103', 'BAS104', 'BAS105', 'BAS106', 'BAS107', 'BAS113'),
    ('VT', 1): ('BAS101', 'BAS102', 'BAS103', 'BAS105', 'BAS107', 'BAS108'),
    ('DT', 1): ('BAS101', 'BAS102', 'BAS104', 'BAS105', 'BAS107', 'BAS108'),
    ('QT', 1): ('BAS103', 'BAS104', 'BAS109', 'BAS110', 'BAS111', 'BAS112'),
    ('MR', 1): ('BAS103', 'BAS105', 'BAS109', 'BAS110', 'BAS111', 'BAS112'),
    ('KT', 1): ('BAS104', 'BAS105', 'BAS109', 'BAS110', 'BAS111', 'BAS112'),
    ('TM', 1): ('BAS106', 'BAS109', 'BAS110', 'BAS111', 'BAS112', 'BAS113'),

    # --- STAGE 2: KỲ 2 NĂM NHẤT (D24 học năm 2024-S2, D25 học năm 2025-S2) ---
    ('CN', 2): ('BAS121', 'BAS122', 'BAS123', 'BAS124', 'BAS125', 'BAS127'),
    ('AT', 2): ('BAS121', 'BAS122', 'BAS123', 'BAS124', 'BAS125', 'BAS126'),
    ('KH', 2): ('BAS121', 'BAS122', 'BAS123', 'BAS124', 'BAS125', 'BAS127'),
    ('PT', 2): ('BAS122', 'BAS123', 'BAS124', 'BAS125', 'BAS127', 'BAS130'),
    ('VT', 2): ('BAS121', 'BAS122', 'BAS123', 'BAS124', 'BAS125', 'BAS126'),
    ('DT', 2): ('BAS121', 'BAS122', 'BAS123', 'BAS124', 'BAS125', 'BAS126'),
    ('QT', 2): ('BAS122', 'BAS123', 'BAS124', 'BAS127', 'BAS128', 'BAS129'),
    ('MR', 2): ('BAS122', 'BAS123', 'BAS124', 'BAS127', 'BAS128', 'BAS130'),
    ('KT', 2): ('BAS122', 'BAS123', 'BAS124', 'BAS128', 'BAS129', 'BAS132'),
    ('TM', 2): ('BAS122', 'BAS123', 'BAS124', 'BAS128', 'BAS131', 'BAS132'),

    # --- STAGE 3: KỲ 1 NĂM HAI (D24 học năm 2025-S1, D25 học năm 2026-S1) ---
    ('CN', 3): ('IT201', 'IT202', 'IT203', 'IT207', 'CS201', 'CS202'),
    ('AT', 3): ('IT201', 'IT202', 'IT203', 'IT207', 'CS201', 'CS202'),
    ('KH', 3): ('IT201', 'IT202', 'IT203', 'IT207', 'CS201', 'CS202'),
    ('PT', 3): ('IT201', 'IT202', 'PT201', 'PT202', 'CS201', 'CS202'),
    ('VT', 3): ('EL201', 'EL202', 'EL204', 'IT203', 'CS201', 'CS202'),
    ('DT', 3): ('EL201', 'EL202', 'EL204', 'IT203', 'CS201', 'CS202'),
    ('QT', 3): ('BZ201', 'BZ202', 'BZ203', 'BZ206', 'CS201', 'CS202'),
    ('MR', 3): ('BZ201', 'BZ202', 'BZ203', 'BZ206', 'CS201', 'CS202'),
    ('KT', 3): ('BZ201', 'BZ202', 'BZ203', 'BZ206', 'CS201', 'CS202'),
    ('TM', 3): ('BZ201', 'BZ202', 'BZ203', 'IT202', 'CS201', 'CS202'),

    # --- STAGE 4: KỲ 2 NĂM HAI (D24 học năm 2025-S2) ---
    ('CN', 4): ('IT204', 'IT205', 'IT206', 'IT208', 'CS203', 'CS204'),
    ('AT', 4): ('IT204', 'IT205', 'IT206', 'IT208', 'CS203', 'CS204'),
    ('KH', 4): ('IT204', 'IT205', 'IT206', 'IT208', 'CS203', 'CS204'),
    ('PT', 4): ('IT205', 'IT206', 'PT203', 'PT204', 'CS203', 'CS204'),
    ('VT', 4): ('EL203', 'EL205', 'EL206', 'EL207', 'CS203', 'CS204'),
    ('DT', 4): ('EL203', 'EL205', 'EL206', 'EL207', 'CS203', 'CS204'),
    ('QT', 4): ('BZ204', 'BZ205', 'BZ207', 'BZ208', 'CS203', 'CS204'),
    ('MR', 4): ('BZ204', 'BZ205', 'BZ207', 'BZ208', 'CS203', 'CS204'),
    ('KT', 4): ('BZ204', 'BZ205', 'BZ207', 'BZ208', 'CS203', 'CS204'),
    ('TM', 4): ('BZ204', 'BZ205', 'BZ207', 'IT208', 'CS203', 'CS204'),

    # --- STAGE 5: KỲ 1 NĂM BA (D24 học năm 2026-S1) ---
    ('CN', 5): ('CN301', 'CN302', 'CN303', 'CN304', 'CN305', 'CN306'),
    ('AT', 5): ('AT301', 'AT302', 'AT303', 'AT304', 'AT305', 'CN304'),
    ('KH', 5): ('KH301', 'KH302', 'KH303', 'KH304', 'KH305', 'CN304'),
    ('PT', 5): ('PT301', 'PT302', 'PT303', 'PT304', 'CN301', 'CN303'),
    ('VT', 5): ('VT301', 'VT302', 'VT303', 'VT304', 'VT305', 'DT301'),
    ('DT', 5): ('DT301', 'DT302', 'DT303', 'DT304', 'DT305', 'VT305'),
    ('QT', 5): ('QT301', 'QT302', 'QT303', 'QT304', 'QT305', 'TM303'),
    ('MR', 5): ('MR301', 'MR302', 'MR303', 'MR304', 'MR305', 'QT305'),
    ('KT', 5): ('KT301', 'KT302', 'KT303', 'KT304', 'KT305', 'QT304'),
    ('TM', 5): ('TM301', 'TM302', 'TM303', 'TM304', 'MR301', 'CN301'),
}

LAST_NAMES = ('Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Hồ', 'Ngô', 'Dương')
MIDDLE_NAMES_MALE = ('Văn', 'Hoàng', 'Đức', 'Minh', 'Quốc', 'Tuấn', 'Hữu', 'Gia', 'Anh', 'Đình')
MIDDLE_NAMES_FEMALE = ('Thị', 'Ngọc', 'Phương', 'Thu', 'Thanh', 'Mai', 'Khánh', 'Bảo', 'Hồng', 'Thùy')
FIRST_NAMES_MALE = ('Tùng', 'Dũng', 'Hùng', 'Nam', 'Minh', 'Khôi', 'Long', 'Phúc', 'Khang', 'Đức', 'Tú', 'Hiếu', 'An', 'Bình')
FIRST_NAMES_FEMALE = ('Anh', 'Linh', 'Hà', 'Trang', 'Chi', 'Nhi', 'Mai', 'Uyên', 'Thủy', 'Hương', 'Lan', 'Ngân', 'Tâm', 'Vân')
PROVINCES = ('Hà Nội', 'Hải Phòng', 'Nam Định', 'Thanh Hóa', 'Nghệ An', 'Bắc Ninh', 'Hải Dương', 'Thái Bình', 'Quảng Ninh', 'Ninh Bình')

# Hằng số tương thích ngược với bộ test cũ
MAJOR_NAME = MAJORS_CONFIG[0][0]
MAJOR_CODE = MAJORS_CONFIG[0][1]
CLASS_NAME = 'D24CQCN01'
COHORT = 'D24'
LECTURER_USERNAME = 'gv.001@eduflaw.com'
CLASS_DEFINITIONS = (
    ('CN301-2026-S1-01', 'Lập trình Web', 3, 1, 2026),
    ('IT202-2026-S1-01', 'Cơ sở dữ liệu', 3, 1, 2026),
)


def _generate_full_name(rng, gender):
    last = rng.choice(LAST_NAMES)
    if gender == 'Nam':
        mid = rng.choice(MIDDLE_NAMES_MALE)
        first = rng.choice(FIRST_NAMES_MALE)
    else:
        mid = rng.choice(MIDDLE_NAMES_FEMALE)
        first = rng.choice(FIRST_NAMES_FEMALE)
    return f"{last} {mid} {first}"


def build_demo_students(seed=42, count=8):
    """Hàm phụ trợ tương thích ngược với bộ test cũ"""
    rng = random.Random(seed)
    result = []
    for idx in range(1, count + 1):
        gender = 'Nam' if idx % 2 else 'Nữ'
        code = f'B24DCCN{idx:03d}'
        result.append({
            'username': f'{code.lower()}@eduflaw.com',
            'student_code': code,
            'full_name': _generate_full_name(rng, gender),
            'gender': gender,
            'date_of_birth': f'2006-{(idx % 12) + 1:02d}-15'
        })
    return result


def _split_into_credit_classes(students_list, rng):
    """
    Chia danh sách sinh viên (100, 200 hoặc 300 SV) thành từ 5 đến 10 lớp tín chỉ,
    đảm bảo mỗi lớp tín chỉ có từ 20 đến 40 sinh viên.
    """
    total = len(students_list)
    if total == 100:
        num_classes = 5  # 5 lớp x 20 SV/lớp
    elif total == 200:
        num_classes = rng.choice((6, 7, 8))  # 6-8 lớp (25 - 34 SV/lớp)
    elif total == 300:
        num_classes = rng.choice((8, 9, 10))  # 8-10 lớp (30 - 38 SV/lớp)
    else:
        num_classes = max(5, min(10, round(total / 28)))

    base_size = total // num_classes
    remainder = total % num_classes
    chunks = []
    start = 0
    for i in range(num_classes):
        size = base_size + (1 if i < remainder else 0)
        chunks.append(students_list[start:start + size])
        start += size
    return chunks


class MvpSeedService:
    @classmethod
    def seed(cls, random_seed=42, reset_existing=True, credentials_path=None):
        rng = random.Random(random_seed)
        connection = cursor = None
        # Mật khẩu tạm ngẫu nhiên của từng tài khoản mới tạo: chỉ ghi ra file Excel một lần sau khi commit
        issued_credentials = []

        try:
            connection = db_pool.get_connection()
            cursor = connection.cursor(dictionary=True)

            cls._assert_enrollment_unique_index(cursor)

            if reset_existing:
                cls._clean_academic_data(cursor)

            # 1. Đảm bảo tài khoản Master tồn tại
            cursor.execute("SELECT id FROM users WHERE role = 'master' LIMIT 1")
            if not cursor.fetchone():
                master_username = os.getenv('MASTER_USERNAME', 'master@eduflaw.com')
                # Không dùng mật khẩu mặc định cho Master: bắt buộc cấu hình trong .env
                master_password = os.getenv('MASTER_PASSWORD', '').strip()
                if len(master_password) < 12:
                    raise RuntimeError('Hãy đặt MASTER_PASSWORD (tối thiểu 12 ký tự) trong .env trước khi seed tài khoản Master.')
                # Gmail khôi phục của Master phải do chủ hệ thống tự cấu hình, không gán sẵn địa chỉ của người khác
                master_personal_email = os.getenv('MASTER_PERSONAL_EMAIL', '').strip().lower() or None
                cursor.execute(
                    "INSERT INTO users (username, password, role, personal_email) VALUES (%s, %s, 'master', %s)",
                    (master_username, generate_password_hash(master_password), master_personal_email)
                )
                master_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO master_profiles (user_id, full_name, phone_number, gender, address) VALUES (%s, %s, %s, %s, %s)",
                    (master_id, 'Ban Giám Hiệu - Quản Trị Tối Cao', '0901000001', 'Nam', 'Hà Nội')
                )

            # 2. Khởi tạo 10 Ngành đào tạo cơ bản (Chỉ tiêu 100 SV/khoá)
            cursor.executemany(
                """
                INSERT INTO majors (major_name, major_code, max_students_per_cohort)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    major_name = VALUES(major_name),
                    max_students_per_cohort = VALUES(max_students_per_cohort)
                """,
                MAJORS_CONFIG
            )

            # 3. Gom nhóm sinh viên theo từng (year, semester, subject_code)
            # Sắp xếp ưu tiên học kỳ hiện tại (2026, 1) lên đầu để các giảng viên gv.001..gv.085 dạy kỳ hiện tại
            term_subject_groups = {}
            for cohort, timeline in COHORT_TIMELINE.items():
                for year, semester, stage_idx in timeline:
                    for _, major_code, _ in MAJORS_CONFIG:
                        subject_codes = STAGE_CURRICULUM[(major_code, stage_idx)]
                        for scode in subject_codes:
                            term_subject_groups.setdefault((year, semester, scode), []).append((major_code, cohort))

            sorted_term_keys = sorted(
                term_subject_groups.keys(),
                key=lambda k: (-k[0], -k[1], k[2])  # Ưu tiên 2026-S1 trước, sau đó 2025-S2, 2025-S1, 2024-S2, 2024-S1
            )

            lecturer_assignments = []
            lecturer_counter = 1
            for (year, semester, scode) in sorted_term_keys:
                groups = term_subject_groups[(year, semester, scode)]
                # Tách danh sách nhóm (mỗi nhóm 100 SV) thành các lô từ 1 đến 3 nhóm (100 - 300 SV -> 5 - 10 lớp tín chỉ)
                idx = 0
                while idx < len(groups):
                    remaining = len(groups) - idx
                    if remaining <= 3:
                        batch_groups = groups[idx:]
                        idx = len(groups)
                    elif remaining == 4:
                        batch_groups = groups[idx:idx + 2]
                        idx += 2
                    else:
                        batch_groups = groups[idx:idx + 3]
                        idx += 3

                    lecturer_assignments.append({
                        'lecturer_index': lecturer_counter,
                        'year': year,
                        'semester': semester,
                        'subject_code': scode,
                        'groups': batch_groups
                    })
                    lecturer_counter += 1

            # 4. Tạo tài khoản & hồ sơ cho Giảng viên (Admin)
            # Tài khoản đã tồn tại (chạy --no-reset) giữ nguyên mật khẩu, chỉ tài khoản mới được cấp mật khẩu tạm
            cursor.execute("SELECT username FROM users")
            existing_usernames = {row['username'] for row in cursor.fetchall()}
            lecturer_user_rows = []
            lecturer_meta = []

            for item in lecturer_assignments:
                l_idx = item['lecturer_index']
                username = f"gv.{l_idx:03d}@eduflaw.com"
                gender = 'Nam' if l_idx % 2 else 'Nữ'
                full_name = f"ThS. {_generate_full_name(rng, gender)}"
                personal_email = None  # Giảng viên tự liên kết Gmail thật khi kích hoạt tài khoản
                if username not in existing_usernames:
                    temp_password, password_hash = issue_temp_password()
                    lecturer_user_rows.append((username, password_hash, 'admin', personal_email))
                    issued_credentials.append({
                        'username': username, 'full_name': full_name, 'role': 'admin', 'password': temp_password
                    })
                lecturer_meta.append({
                    'username': username,
                    'full_name': full_name,
                    'gender': gender,
                    'id_card': f"001185{l_idx:06d}",
                    'phone': f"0912{l_idx:06d}",
                    'dob': f"198{(l_idx % 9) + 1}-{(l_idx % 12) + 1:02d}-10",
                    'address': rng.choice(PROVINCES),
                    'assignment': item
                })

            if lecturer_user_rows:
                cursor.executemany(
                    """
                    INSERT INTO users (username, password, role, personal_email, must_change_password)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON DUPLICATE KEY UPDATE role = VALUES(role)
                    """,
                    lecturer_user_rows
                )

            cursor.execute("SELECT id, username FROM users WHERE role = 'admin'")
            admin_id_map = {row['username']: row['id'] for row in cursor.fetchall()}

            admin_profile_rows = []
            for meta in lecturer_meta:
                uid = admin_id_map[meta['username']]
                meta['user_id'] = uid
                admin_profile_rows.append((
                    uid, meta['full_name'], encrypt_field(meta['id_card']),
                    meta['phone'], meta['dob'], meta['gender'], meta['address']
                ))

            cursor.execute("DELETE FROM admin_profiles WHERE user_id IN (%s)" % (
                ','.join(str(m['user_id']) for m in lecturer_meta)
            ))
            cursor.executemany(
                """
                INSERT INTO admin_profiles (user_id, full_name, id_card, phone_number, date_of_birth, gender, address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                admin_profile_rows
            )

            # 5. Tạo 3.000 Sinh viên (3 khoá D24, D25, D26 x 10 ngành x 100 SV)
            # Chia làm 120 lớp hành chính (4 lớp/ngành/khoá x 25 SV/lớp)
            student_user_rows = []
            student_meta_list = []
            admin_class_counter = 0

            # D24 (năm 3): sinh 2006 | D25 (năm 2): sinh 2007 | D26 (năm 1): sinh 2008
            birth_year_map = {'D24': 2006, 'D25': 2007, 'D26': 2008}
            active_lecturers = [m for m in lecturer_meta if m['assignment']['year'] == ACADEMIC_YEAR]

            for cohort in COHORTS:
                b_year = birth_year_map[cohort]
                cohort_num = cohort[1:]  # '24', '25', '26'
                for major_name, major_code, _ in MAJORS_CONFIG:
                    for seq in range(1, STUDENTS_PER_MAJOR_COHORT + 1):
                        class_idx = ((seq - 1) // 25) + 1  # 1..4 (mỗi lớp đúng 25 SV)
                        pos_in_class = ((seq - 1) % 25) + 1
                        if pos_in_class == 1:
                            admin_class_counter += 1

                        advisor = active_lecturers[(admin_class_counter - 1) % len(active_lecturers)]
                        class_name = f"{cohort}CQ{major_code}{class_idx:02d}"
                        student_code = f"B{cohort_num}DC{major_code}{seq:03d}"
                        username = f"{student_code.lower()}@eduflaw.com"
                        personal_email = None  # Sinh viên tự liên kết Gmail thật khi kích hoạt tài khoản

                        gender = 'Nam' if rng.random() < 0.55 else 'Nữ'
                        full_name = _generate_full_name(rng, gender)
                        dob = f"{b_year}-{(seq % 12) + 1:02d}-{(seq % 28) + 1:02d}"

                        if pos_in_class == 1:
                            class_role = 'Lớp trưởng'
                        elif pos_in_class == 2:
                            class_role = 'Lớp phó'
                        else:
                            class_role = 'Thành viên'

                        hometown = rng.choice(PROVINCES)
                        if username not in existing_usernames:
                            temp_password, password_hash = issue_temp_password()
                            student_user_rows.append((username, password_hash, 'student', personal_email))
                            issued_credentials.append({
                                'username': username, 'full_name': full_name, 'role': 'student', 'password': temp_password
                            })
                        student_meta_list.append({
                            'username': username,
                            'student_code': student_code,
                            'full_name': full_name,
                            'dob': dob,
                            'gender': gender,
                            'phone': f"098{rng.randint(1000000, 9999999)}",
                            'id_card': f"001{b_year % 100:02d}{rng.randint(1000000, 9999999)}",
                            'hometown': hometown,
                            'current_address': f"Ký túc xá / Nội thành Hà Nội (Quê: {hometown})",
                            'class_role': class_role,
                            'major_name': major_name,
                            'major_code': major_code,
                            'cohort': cohort,
                            'class_name': class_name,
                            'advisor_name': advisor['full_name'],
                            'advisor_email': advisor['username'],
                        })

            # Batch insert 3,000 student users
            for i in range(0, len(student_user_rows), 1000):
                cursor.executemany(
                    """
                    INSERT INTO users (username, password, role, personal_email, must_change_password)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON DUPLICATE KEY UPDATE role = VALUES(role)
                    """,
                    student_user_rows[i:i + 1000]
                )

            cursor.execute("SELECT id, username FROM users WHERE role = 'student'")
            student_id_map = {row['username']: row['id'] for row in cursor.fetchall()}

            student_profile_rows = []
            group_students_map = {}

            for sm in student_meta_list:
                uid = student_id_map[sm['username']]
                sm['user_id'] = uid
                group_students_map.setdefault((sm['major_code'], sm['cohort']), []).append(uid)
                student_profile_rows.append((
                    uid, sm['student_code'], sm['full_name'], sm['dob'], sm['gender'],
                    sm['phone'], encrypt_field(sm['id_card']), sm['hometown'], sm['current_address'],
                    sm['class_role'], 'Đang học', sm['major_name'], sm['cohort'],
                    sm['class_name'], sm['advisor_name'], sm['advisor_email']
                ))

            for i in range(0, len(student_profile_rows), 1000):
                cursor.executemany(
                    """
                    INSERT INTO student_profiles
                    (user_id, student_code, full_name, date_of_birth, gender,
                     phone_number, id_card, hometown, current_address,
                     class_role, status, major, cohort, class_name, advisor_name, advisor_email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        full_name = VALUES(full_name),
                        class_role = VALUES(class_role),
                        major = VALUES(major),
                        cohort = VALUES(cohort),
                        class_name = VALUES(class_name),
                        advisor_name = VALUES(advisor_name),
                        advisor_email = VALUES(advisor_email)
                    """,
                    student_profile_rows[i:i + 1000]
                )

            # 6. Khởi tạo Lớp tín chỉ cho cả các kỳ lịch sử (2024, 2025) và kỳ hiện tại (2026)
            # 30 khung giờ trong tuần: Thứ 2..Thứ 7 (2..7) x 5 ca ('1-2', '3-4', '5-6', '7-8', '9-10')
            all_time_slots = [
                (day, shift)
                for day in (2, 3, 4, 5, 6, 7)
                for shift in ('1-2', '3-4', '5-6', '7-8', '9-10')
            ]

            lecturer_busy_slots = {}
            student_busy_slots = {}  # key: (student_id, year, semester)
            slot_room_counter = {}   # key: (year, semester, day, shift)

            credit_class_rows = []
            credit_class_rosters = []
            term_subject_sec_counter = {}

            for meta in lecturer_meta:
                lecturer_id = meta['user_id']
                assignment = meta['assignment']
                year = assignment['year']
                semester = assignment['semester']
                scode = assignment['subject_code']
                subject_name, credits, weights = SUBJECT_CATALOG[scode]
                w_cc, w_bttl, w_tbkt, w_tgk, w_tnth, w_thi = weights

                pooled_students = []
                for grp in assignment['groups']:
                    pooled_students.extend(group_students_map[grp])

                # Chia thành 5–10 lớp tín chỉ, mỗi lớp 20–40 sinh viên
                rosters = _split_into_credit_classes(pooled_students, rng)

                for roster in rosters:
                    sec_key = (year, semester, scode)
                    sec_num = term_subject_sec_counter.get(sec_key, 0) + 1
                    term_subject_sec_counter[sec_key] = sec_num
                    class_code = f"{scode}-{year}-S{semester}-{sec_num:02d}"

                    lec_busy = lecturer_busy_slots.setdefault(lecturer_id, set())
                    chosen_slot = None
                    shuffled_slots = list(all_time_slots)
                    rng.shuffle(shuffled_slots)

                    for candidate_slot in shuffled_slots:
                        if candidate_slot in lec_busy:
                            continue
                        if any(candidate_slot in student_busy_slots.get((sid, year, semester), ()) for sid in roster):
                            continue
                        chosen_slot = candidate_slot
                        break

                    if chosen_slot is None:
                        for candidate_slot in shuffled_slots:
                            if candidate_slot not in lec_busy:
                                chosen_slot = candidate_slot
                                break

                    day_of_week, shift = chosen_slot
                    lec_busy.add(chosen_slot)
                    for sid in roster:
                        student_busy_slots.setdefault((sid, year, semester), set()).add(chosen_slot)

                    room_key = (year, semester, chosen_slot)
                    room_idx = slot_room_counter.get(room_key, 0) + 1
                    slot_room_counter[room_key] = room_idx
                    building = 'A2' if room_idx <= 25 else 'B1'
                    room_name = f"{building}-{(room_idx % 25) + 101}"

                    credit_class_rows.append((
                        class_code, subject_name, credits, semester, year, lecturer_id,
                        w_cc, w_bttl, w_tbkt, w_tgk, w_tnth, w_thi,
                        day_of_week, shift, room_name
                    ))
                    credit_class_rosters.append({
                        'class_code': class_code,
                        'subject_name': subject_name,
                        'credits': credits,
                        'semester': semester,
                        'year': year,
                        'weights': weights,
                        'roster': roster
                    })

            for i in range(0, len(credit_class_rows), 1000):
                cursor.executemany(
                    """
                    INSERT INTO credit_classes
                    (class_code, subject_name, credits, semester, year, lecturer_id,
                     weight_cc, weight_bttl, weight_tbkt, weight_tgk, weight_tnth, weight_thi,
                     day_of_week, shift, room)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        lecturer_id = VALUES(lecturer_id),
                        day_of_week = VALUES(day_of_week),
                        shift = VALUES(shift),
                        room = VALUES(room)
                    """,
                    credit_class_rows[i:i + 1000]
                )

            cursor.execute("SELECT id, class_code FROM credit_classes")
            credit_class_id_map = {row['class_code']: row['id'] for row in cursor.fetchall()}

            # 7. Ghi danh sinh viên và tạo điểm cho toàn bộ các học kỳ:
            # - D24: 2024-S1, 2024-S2, 2025-S1, 2025-S2, 2026-S1
            # - D25: 2025-S1, 2025-S2, 2026-S1
            # - D26: 2026-S1
            grade_rows = []
            for item in credit_class_rosters:
                cc_id = credit_class_id_map[item['class_code']]
                w_cc, w_bttl, w_tbkt, w_tgk, w_tnth, w_thi = item['weights']
                sem = item['semester']
                yr = item['year']

                for sid in item['roster']:
                    score_cc = round(rng.uniform(7.0, 10.0), 1) if w_cc > 0 else None
                    score_bttl = round(rng.uniform(6.0, 9.5), 1) if w_bttl > 0 else None
                    score_tbkt = round(rng.uniform(5.5, 9.5), 1) if w_tbkt > 0 else None
                    score_tgk = round(rng.uniform(5.5, 9.5), 1) if w_tgk > 0 else None
                    score_tnth = round(rng.uniform(6.5, 10.0), 1) if w_tnth > 0 else None
                    score_thi = round(rng.uniform(4.5, 9.5), 1)

                    total_score = (
                        (score_cc or 0.0) * (w_cc / 100.0)
                        + (score_bttl or 0.0) * (w_bttl / 100.0)
                        + (score_tbkt or 0.0) * (w_tbkt / 100.0)
                        + (score_tgk or 0.0) * (w_tgk / 100.0)
                        + (score_tnth or 0.0) * (w_tnth / 100.0)
                        + score_thi * (w_thi / 100.0)
                    )
                    final_score = round(total_score, 1)

                    grade_rows.append((
                        sid, cc_id, item['subject_name'], item['credits'],
                        sem, yr,
                        score_cc, score_bttl, score_tbkt, score_tgk, score_tnth, score_thi, final_score
                    ))

            for i in range(0, len(grade_rows), 4000):
                cursor.executemany(
                    """
                    INSERT INTO grades
                    (student_id, credit_class_id, subject, credits, semester, year,
                     score_cc, score_bttl, score_tbkt, score_tgk, score_tnth, score_thi, score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        score_cc = VALUES(score_cc),
                        score_bttl = VALUES(score_bttl),
                        score_tbkt = VALUES(score_tbkt),
                        score_tgk = VALUES(score_tgk),
                        score_tnth = VALUES(score_tnth),
                        score_thi = VALUES(score_thi),
                        score = VALUES(score)
                    """,
                    grade_rows[i:i + 4000]
                )

            connection.commit()

            credentials_file = None
            if issued_credentials:
                credentials_file = credentials_path or os.path.join(
                    'instance', f"mat_khau_tam_seed_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                cls._write_credentials_file(credentials_file, issued_credentials)

            return {
                'cohorts': len(COHORTS),
                'majors': len(MAJORS_CONFIG),
                'admin_classes': admin_class_counter,
                'students': len(student_meta_list),
                'lecturers': len(lecturer_meta),
                'credit_classes': len(credit_class_rows),
                'enrollments': len(grade_rows),
                'issued_passwords': len(issued_credentials),
                'credentials_file': credentials_file,
            }
        except Exception:
            if connection:
                connection.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def _write_credentials_file(path, credentials):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, 'wb') as output:
            output.write(build_credentials_workbook(credentials).getvalue())

    @staticmethod
    def _clean_academic_data(cursor):
        """Dọn dẹp dữ liệu mẫu cũ để đảm bảo đúng 10 ngành và 3.000 sinh viên (D24, D25, D26)"""
        cursor.execute("DELETE FROM grade_audit_logs")
        cursor.execute("DELETE FROM grades")
        cursor.execute("DELETE FROM credit_classes")
        cursor.execute("DELETE FROM announcements")
        cursor.execute("DELETE FROM student_profiles")
        cursor.execute("DELETE FROM admin_profiles")
        cursor.execute("DELETE FROM users WHERE role IN ('student', 'admin')")
        cursor.execute("DELETE FROM majors")

    @staticmethod
    def _assert_enrollment_unique_index(cursor):
        cursor.execute('SHOW INDEX FROM grades')
        indexes = {}
        for row in cursor.fetchall():
            if row['Non_unique'] == 0:
                indexes.setdefault(row['Key_name'], []).append(row['Column_name'])
        if not any(
            columns == ['student_id', 'credit_class_id']
            for columns in indexes.values()
        ):
            raise RuntimeError(
                'Run migrations/002_unique_student_credit_class.sql before seeding roster rows.'
            )


def seed_data(random_seed=42, reset_existing=True, credentials_path=None):
    return MvpSeedService.seed(
        random_seed=random_seed, reset_existing=reset_existing, credentials_path=credentials_path
    )


if __name__ == '__main__':
    # Console Windows (cp1252) không in được tiếng Việt/emoji nếu không đổi sang UTF-8
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description='Seed 3,000 students (D24, D25, D26), 10 majors, lecturers, and multi-year transcripts for EduFlaw.'
    )
    parser.add_argument('--small', action='store_true', help='Giữ cờ tương thích CLI cũ.')
    parser.add_argument('--seed', type=int, default=42, help='Random seed cố định dữ liệu.')
    parser.add_argument('--no-reset', action='store_true', help='Không xóa dữ liệu cũ trước khi seed.')
    parser.add_argument(
        '--credentials-out',
        help='File Excel ghi mật khẩu tạm của các tài khoản mới (mặc định: instance/mat_khau_tam_seed_<thời gian>.xlsx).'
    )
    arguments = parser.parse_args()

    result = seed_data(
        random_seed=arguments.seed,
        reset_existing=not arguments.no_reset,
        credentials_path=arguments.credentials_out
    )
    print(
        f"✅ Seed hoàn tất:\n"
        f"   - Khoá đào tạo     : {result['cohorts']} khoá (D24 - Năm 3, D25 - Năm 2, D26 - Năm 1)\n"
        f"   - Ngành đào tạo    : {result['majors']} ngành (100 SV/khoá/ngành)\n"
        f"   - Lớp hành chính   : {result['admin_classes']} lớp (4 lớp/ngành/khoá, 25 SV/lớp)\n"
        f"   - Tổng sinh viên   : {result['students']} sinh viên\n"
        f"   - Tổng giảng viên  : {result['lecturers']} giảng viên (5-10 lớp tín chỉ/GV)\n"
        f"   - Tổng lớp tín chỉ : {result['credit_classes']} lớp (20-40 SV/lớp)\n"
        f"   - Tổng lượt điểm   : {result['enrollments']} bản ghi điểm (2024 - 2026)"
    )
    if result['credentials_file']:
        print(
            f"🔑 Đã cấp {result['issued_passwords']} mật khẩu tạm ngẫu nhiên, lưu tại: {result['credentials_file']}\n"
            f"   File chứa mật khẩu dạng rõ: chỉ phát cho chủ tài khoản rồi xóa, không commit lên git."
        )
