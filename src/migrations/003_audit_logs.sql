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