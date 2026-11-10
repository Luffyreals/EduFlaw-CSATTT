from app.services.mvp_seed_service import build_demo_students

def test_build_demo_students_count_and_structure():
    """Kiểm tra hàm sinh dữ liệu mẫu tạo đúng số lượng và cấu trúc sinh viên"""
    students = build_demo_students(seed=42, count=8)

    assert len(students) == 8

    first_student = students[0]
    assert 'username' in first_student
    assert 'student_code' in first_student
    assert first_student['student_code'] == 'B24DCCN001'
    assert first_student['username'] == 'b24dccn001@eduflaw.com'
