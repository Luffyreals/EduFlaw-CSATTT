-- 010: Mở rộng cột id_card (CCCD) để chứa dữ liệu mã hóa AES-GCM ở tầng ứng dụng (app/utils/field_crypto.py).
-- Giá trị mã hóa dài hơn CCCD gốc nên cột cần >= 255 ký tự. Áp thủ công trên DB cũ, theo thứ tự số.
-- Sau khi áp migration này, chạy backfill để mã hóa dữ liệu cũ dạng rõ:
--   python -m app.services.pii_backfill_service --apply
ALTER TABLE student_profiles MODIFY id_card VARCHAR(255) NULL;
ALTER TABLE admin_profiles MODIFY id_card VARCHAR(255) NULL;
ALTER TABLE master_profiles MODIFY id_card VARCHAR(255) DEFAULT NULL;
