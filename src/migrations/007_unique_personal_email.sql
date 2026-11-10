-- Mỗi Gmail cá nhân chỉ được liên kết với một tài khoản (NULL không bị ràng buộc).
-- Trước khi chạy, kiểm tra dữ liệu trùng: SELECT personal_email, COUNT(*) FROM users WHERE personal_email IS NOT NULL GROUP BY personal_email HAVING COUNT(*) > 1
ALTER TABLE users ADD UNIQUE KEY uq_users_personal_email (personal_email);
