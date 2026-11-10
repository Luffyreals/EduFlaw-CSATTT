-- Thay mật khẩu mặc định dùng chung bằng mật khẩu tạm ngẫu nhiên cho từng tài khoản.
-- Cột must_change_password = TRUE nghĩa là tài khoản đang dùng mật khẩu tạm do nhà trường cấp và phải onboarding khi đăng nhập.
ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE AFTER personal_email;
-- Tài khoản sinh viên/giảng viên chưa kích hoạt (chưa liên kết Gmail) có thể vẫn đang dùng mật khẩu mặc định cũ.
-- Ứng dụng từ chối đăng nhập bằng mật khẩu mặc định cũ với các tài khoản này: Master/cố vấn cần reset để cấp mật khẩu tạm mới.
UPDATE users SET must_change_password = TRUE WHERE role IN ('student', 'admin') AND personal_email IS NULL;
