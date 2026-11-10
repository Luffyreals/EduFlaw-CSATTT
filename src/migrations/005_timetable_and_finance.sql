-- Thêm cột Thời khóa biểu vào bảng Lớp tín chỉ
ALTER TABLE credit_classes
ADD COLUMN day_of_week INT NULL COMMENT '2=Thứ 2, 3=Thứ 3... 8=Chủ Nhật',
ADD COLUMN shift VARCHAR(20) NULL COMMENT 'VD: 1-3, 4-6',
ADD COLUMN room VARCHAR(50) NULL COMMENT 'VD: P.301';

-- Thêm cột Tài chính & Kỷ luật vào bảng Hồ sơ sinh viên
ALTER TABLE student_profiles
ADD COLUMN tuition_status VARCHAR(50) DEFAULT 'Hoàn thành' COMMENT 'Hoàn thành / Còn nợ',
ADD COLUMN disciplinary_note TEXT NULL COMMENT 'Ghi chú kỷ luật';