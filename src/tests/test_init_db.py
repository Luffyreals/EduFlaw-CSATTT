import os
import re

def _schema_tables():
    with open('schema.sql', encoding='utf-8') as schema_file:
        schema = schema_file.read()
    return dict(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\) ENGINE', schema, re.S))

def test_schema_columns_are_comma_separated():
    """Mỗi dòng định nghĩa cột/khóa (trừ dòng cuối) phải kết thúc bằng dấu phẩy, nếu không init_db.py sẽ lỗi cú pháp"""
    for table, body in _schema_tables().items():
        definitions = []
        for line in (line.strip() for line in body.strip().splitlines()):
            if not line:
                continue
            # "CONSTRAINT ..." xuống dòng "FOREIGN KEY ..." là cùng một định nghĩa
            if line.startswith('FOREIGN KEY') and definitions:
                definitions[-1] = f'{definitions[-1]} {line}'
            else:
                definitions.append(line)
        for line in definitions[:-1]:
            assert line.endswith(','), f'Bảng {table} thiếu dấu phẩy sau: {line}'

def test_schema_includes_all_tables_used_by_app():
    """schema.sql phải tạo đủ bảng để DB mới chạy được mà không cần áp migration"""
    assert {'grade_audit_logs', 'announcements'} <= set(_schema_tables())

def test_schema_file_exists():
    """Đảm bảo file cấu trúc DB gốc luôn tồn tại"""
    assert os.path.exists('schema.sql') is True

def test_migrations_directory_exists():
    """Đảm bảo thư mục lưu trữ các file nâng cấp DB tồn tại"""
    assert os.path.exists('migrations') is True
    assert os.path.isdir('migrations') is True