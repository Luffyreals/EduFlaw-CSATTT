from app.models.grade_model import Grade

def test_enrollment_empty_list():
    """Kiểm tra chặn ghi danh nếu không truyền mã sinh viên nào"""
    success, msg = Grade.enroll_students(credit_class_id=1, student_identifiers=[])
    assert success is False
    assert 'ít nhất một email hoặc mã sinh viên' in msg

def test_enrollment_max_limit():
    """Kiểm tra chặn ghi danh quá 500 sinh viên cùng lúc"""
    # Tạo danh sách 501 mã sinh viên giả lập
    fake_identifiers = [f"B24DCCE{i:03d}" for i in range(501)]
    success, msg = Grade.enroll_students(credit_class_id=1, student_identifiers=fake_identifiers)
    assert success is False
    assert 'tối đa 500 sinh viên' in msg