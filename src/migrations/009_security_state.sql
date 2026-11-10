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
