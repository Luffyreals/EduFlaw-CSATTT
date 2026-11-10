from io import BytesIO

import pandas as pd
from werkzeug.utils import secure_filename


class GradeExportService:
    TEXT_COLUMNS = (
        'Mã sinh viên', 'Họ và tên', 'Email', 'Lớp hành chính',
        'Mã học phần', 'Tên học phần', 'Điểm chữ'
    )
    COLUMNS = TEXT_COLUMNS + (
        'Tín chỉ', 'Chuyên cần', 'Bài tập lớn', 'Kiểm tra', 'Giữa kỳ',
        'Thực hành', 'Thi lần 1', 'Thi lần 2', 'Tổng kết hệ 10', 'Tổng kết hệ 4'
    )

    @classmethod
    def create_workbook(cls, credit_class, students):
        rows = [{
            'Mã sinh viên': student['student_code'],
            'Họ và tên': student['full_name'],
            'Email': student['username'],
            'Lớp hành chính': student['class_name'],
            'Mã học phần': credit_class['class_code'],
            'Tên học phần': credit_class['subject_name'],
            'Tín chỉ': credit_class['credits'],
            'Chuyên cần': student['score_cc'],
            'Bài tập lớn': student['score_bttl'],
            'Kiểm tra': student['score_tbkt'],
            'Giữa kỳ': student['score_tgk'],
            'Thực hành': student['score_tnth'],
            'Thi lần 1': student['score_thi'],
            'Thi lần 2': student['score_thi_2'],
            'Tổng kết hệ 10': student['score'],
            'Tổng kết hệ 4': student['score_4'],
            'Điểm chữ': student['letter']
        } for student in students]

        # Tên sinh viên/môn học có thể bắt đầu bằng ký tự công thức (=, +, -, @) hoặc tab/CR: thêm dấu ' để
        # phần mềm bảng tính luôn coi là văn bản, tránh CSV/Excel injection khi mở file điểm tải xuống.
        # Giữ đồng bộ với app/utils/temp_password.py:_excel_text.
        dataframe = pd.DataFrame(rows, columns=cls.COLUMNS)
        for column in cls.TEXT_COLUMNS:
            dataframe[column] = dataframe[column].map(
                lambda value: "'" + value
                if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r'))
                else value
            )

        output = BytesIO()
        dataframe.to_excel(output, index=False, sheet_name='Bang diem', engine='openpyxl')
        output.seek(0)
        class_code = secure_filename(str(credit_class['class_code'])).lstrip('._') or 'class'
        filename = f"bang-diem-{class_code}.xlsx"
        return output, filename