from app.models.grade_model import Grade

def test_score_conversion():
    """Kiểm tra logic quy đổi điểm hệ 10 sang hệ 4 và điểm chữ"""
    assert Grade.convert_score(9.5) == {'score_4': 4.0, 'letter': 'A+', 'color': '#16a34a'}
    assert Grade.convert_score(8.0) == {'score_4': 3.5, 'letter': 'B+', 'color': '#3b82f6'}
    assert Grade.convert_score(6.5) == {'score_4': 2.5, 'letter': 'C+', 'color': '#f59e0b'}
    assert Grade.convert_score(3.0) == {'score_4': 0.0, 'letter': 'F', 'color': '#ef4444'}
    assert Grade.convert_score(None) == {'score_4': None, 'letter': '--', 'color': '#cbd5e1'}

def test_calculate_final_score():
    """Kiểm tra công thức tính tổng kết điểm học phần theo trọng số"""
    weights = {
        'weight_cc': 10, 'weight_bttl': 0, 'weight_tbkt': 20, 
        'weight_tgk': 0, 'weight_tnth': 0, 'weight_thi': 70
    }
    data = {
        'score_cc': 10.0, 'score_bttl': None, 'score_tbkt': 8.5,
        'score_tgk': None, 'score_tnth': None, 'score_thi': 9.0, 'score_thi_2': None
    }
    # Công thức: (10 * 0.1) + (8.5 * 0.2) + (9.0 * 0.7) = 1 + 1.7 + 6.3 = 9.0
    result = Grade.calculate_final_score(data, weights)
    assert result == 9.0

def test_calculate_gpa():
    """Kiểm tra logic tính điểm trung bình chung tích lũy (GPA)"""
    mock_grades = [
        {'score': 9.0, 'credits': 3, 'score_4': 4.0}, # Qua môn
        {'score': 3.0, 'credits': 2, 'score_4': 0.0}  # Trượt môn
    ]
    result = Grade.calculate_gpa(mock_grades)
    
    # Tính tay: GPA 10 = ((9*3) + (3*2)) / 5 = 33 / 5 = 6.6
    assert result['gpa_10'] == 6.6
    # Tính tay: GPA 4 = ((4*3) + (0*2)) / 5 = 12 / 5 = 2.4
    assert result['gpa_4'] == 2.4
    assert result['total_credits'] == 5
    assert result['total_passed_credits'] == 3