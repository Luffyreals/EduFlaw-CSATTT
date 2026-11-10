CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('master', 'admin', 'student') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    personal_email VARCHAR(255) DEFAULT NULL,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_personal_email (personal_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS majors (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    major_name VARCHAR(160) NOT NULL,
    major_code VARCHAR(16) NOT NULL,
    max_students_per_cohort INT UNSIGNED NOT NULL DEFAULT 1000,
    PRIMARY KEY (id),
    UNIQUE KEY uq_majors_name (major_name),
    UNIQUE KEY uq_majors_code (major_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS student_profiles (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NOT NULL,
    student_code VARCHAR(32) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(32) NULL,
    class_role VARCHAR(64) NULL DEFAULT 'Thành viên',
    status VARCHAR(64) NULL DEFAULT 'Đang học',
    nationality VARCHAR(80) NULL DEFAULT 'Việt Nam',
    ethnicity VARCHAR(80) NULL,
    religion VARCHAR(80) NULL,
    id_card VARCHAR(255) NULL COMMENT 'CCCD - mã hóa AES-GCM ở tầng ứng dụng (field_crypto)',
    hometown VARCHAR(255) NULL,
    current_address VARCHAR(255) NULL,
    phone_number VARCHAR(32) NULL,
    major VARCHAR(160) NOT NULL,
    cohort VARCHAR(16) NOT NULL,
    class_name VARCHAR(64) NOT NULL,
    advisor_name VARCHAR(200) NULL,
    advisor_email VARCHAR(255) NULL,
    avatar_url VARCHAR(512) NULL,
    tuition_status VARCHAR(50) DEFAULT 'Hoàn thành' COMMENT 'Hoàn thành / Còn nợ',
    disciplinary_note TEXT NULL COMMENT 'Ghi chú kỷ luật',
    PRIMARY KEY (id),
    UNIQUE KEY uq_student_profiles_user (user_id),
    UNIQUE KEY uq_student_profiles_code (student_code),
    KEY ix_student_profiles_class (class_name),
    KEY ix_student_profiles_advisor (advisor_email),
    KEY ix_student_profiles_major_cohort (major, cohort),
    CONSTRAINT fk_student_profiles_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS admin_profiles (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NOT NULL,
    full_name VARCHAR(200) NULL,
    id_card VARCHAR(255) NULL COMMENT 'CCCD - mã hóa AES-GCM ở tầng ứng dụng (field_crypto)',
    phone_number VARCHAR(32) NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(32) NULL,
    address VARCHAR(255) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_admin_profiles_user (user_id),
    CONSTRAINT fk_admin_profiles_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS master_profiles (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NOT NULL,
    full_name VARCHAR(200) NULL,
    phone_number VARCHAR(32) NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(32) NULL,
    id_card VARCHAR(255) DEFAULT NULL COMMENT 'CCCD - mã hóa AES-GCM ở tầng ứng dụng (field_crypto)',
    address VARCHAR(255) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_master_profiles_user (user_id),
    CONSTRAINT fk_master_profiles_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS credit_classes (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    class_code VARCHAR(64) NOT NULL,
    subject_name VARCHAR(200) NOT NULL,
    credits SMALLINT UNSIGNED NOT NULL,
    semester TINYINT UNSIGNED NOT NULL,
    year SMALLINT UNSIGNED NOT NULL,
    lecturer_id INT UNSIGNED NULL,
    weight_cc DECIMAL(5,2) NOT NULL DEFAULT 10,
    weight_bttl DECIMAL(5,2) NOT NULL DEFAULT 0,
    weight_tbkt DECIMAL(5,2) NOT NULL DEFAULT 20,
    weight_tgk DECIMAL(5,2) NOT NULL DEFAULT 0,
    weight_tnth DECIMAL(5,2) NOT NULL DEFAULT 0,
    weight_thi DECIMAL(5,2) NOT NULL DEFAULT 70,
    day_of_week INT NULL COMMENT '2=Thứ 2, 3=Thứ 3... 8=Chủ Nhật',
    shift VARCHAR(20) NULL COMMENT 'VD: 1-3, 4-6',
    room VARCHAR(50) NULL COMMENT 'VD: P.301',
    PRIMARY KEY (id),
    UNIQUE KEY uq_credit_classes_code (class_code),
    KEY ix_credit_classes_lecturer (lecturer_id),
    KEY ix_credit_classes_term (year, semester),
    CONSTRAINT fk_credit_classes_lecturer
        FOREIGN KEY (lecturer_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS grades (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_id INT UNSIGNED NOT NULL,
    credit_class_id INT UNSIGNED NULL,
    subject VARCHAR(200) NULL,
    credits SMALLINT UNSIGNED NOT NULL DEFAULT 3,
    score DECIMAL(4,1) NULL,
    semester TINYINT UNSIGNED NULL,
    year SMALLINT UNSIGNED NULL,
    score_cc DECIMAL(4,1) NULL,
    score_bttl DECIMAL(4,1) NULL,
    score_tbkt DECIMAL(4,1) NULL,
    score_tgk DECIMAL(4,1) NULL,
    score_tnth DECIMAL(4,1) NULL,
    score_thi DECIMAL(4,1) NULL,
    score_thi_2 DECIMAL(4,1) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_grades_student_class (student_id, credit_class_id),
    KEY ix_grades_credit_class (credit_class_id),
    KEY ix_grades_student_term (student_id, year, semester),
    CONSTRAINT fk_grades_student
        FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_grades_credit_class
        FOREIGN KEY (credit_class_id) REFERENCES credit_classes (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS grade_audit_logs (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    grade_id INT UNSIGNED NOT NULL,
    field_name VARCHAR(64) NOT NULL,
    old_score DECIMAL(4,1) NULL,
    new_score DECIMAL(4,1) NULL,
    modified_by INT UNSIGNED NULL,
    reason VARCHAR(500) NULL,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_audit_logs_grade (grade_id),
    KEY ix_audit_logs_modifier (modified_by),
    CONSTRAINT fk_audit_logs_grade
        FOREIGN KEY (grade_id) REFERENCES grades (id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_logs_modifier
        FOREIGN KEY (modified_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS announcements (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    target_class VARCHAR(50) NULL COMMENT 'NULL = Thông báo toàn trường',
    created_by INT UNSIGNED NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_announcements_author
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
    throttle_key VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    lockout_until DOUBLE NOT NULL DEFAULT 0,
    updated_at DOUBLE NOT NULL DEFAULT 0,
    PRIMARY KEY (throttle_key),
    KEY ix_login_attempts_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS otp_requests (
    otp_id VARCHAR(64) NOT NULL,
    username VARCHAR(255) NOT NULL,
    personal_email VARCHAR(255) NOT NULL,
    otp_hash CHAR(64) NOT NULL,
    expires_at DOUBLE NOT NULL,
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (otp_id),
    KEY ix_otp_requests_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS otp_send_log (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL,
    sent_at DOUBLE NOT NULL,
    PRIMARY KEY (id),
    KEY ix_otp_send_log_user (username, sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
