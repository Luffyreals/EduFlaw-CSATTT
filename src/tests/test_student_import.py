from app.services.student_import_service import StudentImportService

def test_import_empty_rows():
    """Kiểm tra khi import danh sách rỗng"""
    count, errors, credentials = StudentImportService.import_rows([])
    assert count == 0
    assert 'Tệp không có dữ liệu' in errors[0]

def test_import_exceeds_max_limit():
    """Kiểm tra giới hạn 5000 dòng mỗi lần import"""
    fake_rows = [{'Email': f'test{i}@eduflaw.com'} for i in range(5001)]
    count, errors, credentials = StudentImportService.import_rows(fake_rows)
    assert count == 0
    assert 'tối đa 5000' in errors[0]

def test_import_missing_required_fields():
    """Kiểm tra báo lỗi khi thiếu các cột dữ liệu bắt buộc"""
    # Thiếu MaSV, Lop, Nganh
    rows = [{'Email': 'b24dcce123@eduflaw.com', 'HoTen': 'Nguyen Van A'}]
    count, errors, credentials = StudentImportService.import_rows(rows)
    assert count == 0
    assert 'thiếu' in errors[0]

def test_import_invalid_email_format():
    """Kiểm tra định dạng email không hợp lệ"""
    rows = [{
        'Email': 'email-khong-hop-le',
        'MaSV': 'B24DCCE284',
        'HoTen': 'Nguyen Van A',
        'Lop': 'D24CQCE01',
        'Nganh': 'CNTT'
    }]
    count, errors, credentials = StudentImportService.import_rows(rows)
    assert count == 0
    assert 'email không hợp lệ' in errors[0]