import re
import math
import time
import pandas as pd
from flask import Blueprint, session, redirect, render_template, request, flash, abort, send_file
from app.models.grade_model import Grade
from app.models.profile_model import StudentProfile
from app.models.staff_model import StaffProfile
from app.models.user_model import User
from app.models.announcement_model import Announcement
from app.services.student_import_service import StudentImportService
from app.services.grade_export_service import GradeExportService
from app.utils.decorators import role_required
from app.utils.navigation import safe_referrer
from app.utils.pagination import get_page_args
from app.utils.temp_password import render_issued_credentials, send_credentials_workbook
from app.utils.db_helper import get_db_cursor
from app.utils.security_log import log_security_event

master_bp = Blueprint('master', __name__)

SYSTEM_COUNT_QUERIES = {
    'total_students': "SELECT COUNT(*) FROM student_profiles",
    'total_grades': "SELECT COUNT(*) FROM grades",
    'total_admins': "SELECT COUNT(*) FROM users WHERE role = 'admin'",
    'total_classes': "SELECT COUNT(*) FROM credit_classes",
    'total_majors': "SELECT COUNT(*) FROM majors",
    'total_audit_logs': "SELECT COUNT(*) FROM grade_audit_logs",
    # Phổ điểm toàn trường theo nhóm điểm chữ của Grade.convert_score (chỉ tính môn đã có điểm tổng kết)
    'dist_gioi': "SELECT COUNT(*) FROM grades WHERE score >= 8.5",
    'dist_kha': "SELECT COUNT(*) FROM grades WHERE score >= 7.0 AND score < 8.5",
    'dist_tb': "SELECT COUNT(*) FROM grades WHERE score >= 5.5 AND score < 7.0",
    'dist_yeu': "SELECT COUNT(*) FROM grades WHERE score >= 4.0 AND score < 5.5",
    'dist_kem': "SELECT COUNT(*) FROM grades WHERE score < 4.0",
}
GRADE_DISTRIBUTION_KEYS = ('dist_gioi', 'dist_kha', 'dist_tb', 'dist_yeu', 'dist_kem')


def _system_counts(*names):
    """Đếm nhiều bảng trong một truy vấn duy nhất (mỗi truy vấn tới CSDL từ xa tốn một vòng mạng); lỗi thì trả về 0"""
    counts = dict.fromkeys(names, 0)
    try:
        sql = "SELECT " + ", ".join(f"({SYSTEM_COUNT_QUERIES[name]}) AS {name}" for name in names)
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute(sql)
            row = cursor.fetchone() or {}
            counts.update({name: row.get(name) or 0 for name in names})
    except Exception:
        pass
    return counts


@master_bp.route('/master')
@role_required('master')
def master_dashboard():
    counts = _system_counts('total_students', 'total_grades', 'total_admins', *GRADE_DISTRIBUTION_KEYS)
    grade_distribution = [counts.pop(key) for key in GRADE_DISTRIBUTION_KEYS]
    return render_template('master/dashboard.html', grade_distribution=grade_distribution, **counts)

@master_bp.route('/master/students')
@role_required('master')
def manage_students():
    requested_major = request.args.get('major')
    requested_class = request.args.get('class_name')
    requested_cohort = request.args.get('cohort')

    if requested_class:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        profiles, total_records = StudentProfile.get_profiles_by_class(requested_class, page, per_page)
        
        total_pages = math.ceil(total_records / per_page) if total_records > 0 else 0
        # Chỉ giảng viên đang hoạt động mới được chọn làm cố vấn
        admins_list = StaffProfile.get_admin_options()
        
        return render_template('master/manage_students.html', 
                               profiles=profiles, 
                               selected_class=requested_class, 
                               selected_major=requested_major,
                               selected_cohort=requested_cohort,
                               admins_list=admins_list,
                               current_page=page,
                               total_pages=total_pages)

    elif requested_major:
        classes_stats = StudentProfile.get_classes_summary_by_major(requested_major)
        return render_template('master/manage_students.html', 
                               classes_stats=classes_stats, 
                               selected_major=requested_major,
                               selected_class=None,
                               selected_cohort=requested_cohort)
    else:
        major_stats, total_students = StudentProfile.get_overview_stats()
        return render_template('master/manage_students.html', 
                               major_stats=major_stats, 
                               total_students=total_students, 
                               selected_major=None, 
                               selected_class=None, 
                               selected_cohort=None)

@master_bp.route('/master/students/update', methods=['POST'])
@role_required('master')
def update_student():
    username = request.form.get('username') 

    allowed_fields = [
        'full_name', 'gender', 'dob', 'phone_number', 
        'class_role', 'status', 'nationality', 'ethnicity', 'religion', 
        'id_card', 'hometown', 'current_address', 'tuition_status', 'disciplinary_note'
    ]
    update_data = {k: request.form.get(k) for k in allowed_fields if k in request.form}
    
    success = StudentProfile.update_student_profile(username, update_data)
    if success:
        flash('Đã cập nhật thông tin sinh viên thành công!', 'success')
    else:
        flash('Có lỗi xảy ra khi cập nhật dữ liệu.', 'error')
        
    return redirect(safe_referrer('/master/students'))

@master_bp.route('/master/students/add', methods=['POST'])
@role_required('master')
def add_student():
    student_code = (request.form.get('student_code') or '').strip().upper()
    if not student_code:
        flash('Vui lòng nhập Mã sinh viên.', 'error')
        return redirect(safe_referrer('/master/students'))
    try:
        cohort = "D" + student_code[1:3]
        major_code = student_code[5:7]
        major_name = StudentProfile.get_major_name_by_code(major_code)
        
        if not major_name:
            flash(f'Lỗi: Không tìm thấy ngành nào có mã "{major_code}".', 'error')
            return redirect(safe_referrer('/master/students'))
            
        seq_num = int(student_code[7:]) 
        num_classes = 5 if "CLC" in major_name else 12 
        class_index = (seq_num % num_classes) + 1
        class_name = f"{cohort}CQ{major_code}{class_index:02d}"

        data = {
            'full_name': request.form.get('full_name'),
            'student_code': student_code,
            'dob': request.form.get('dob'),
            'gender': request.form.get('gender'),
            'major': major_name,
            'cohort': cohort,
            'class_name': class_name
        }
        
        issued = StudentProfile.add_student_profile(data)
        if issued:
            username, temp_password = issued
            return render_issued_credentials(
                [{'username': username, 'full_name': data['full_name'], 'password': temp_password}],
                safe_referrer('/master/students'),
                f'Đã thêm sinh viên vào lớp {class_name} thành công!'
            )
        flash('Lỗi: Mã sinh viên có thể đã tồn tại.', 'error')
    except Exception:
        flash('Lỗi định dạng Mã sinh viên.', 'error')
    return redirect(safe_referrer('/master/students'))

@master_bp.route('/master/students/delete', methods=['POST'])
@role_required('master')
def delete_student_route():
    username = request.form.get('username')
    success = StudentProfile.delete_student_profile(username)
    
    if success:
        flash('Đã xóa vĩnh viễn sinh viên khỏi hệ thống!', 'success')
    else:
        flash('Lỗi: Không thể xóa sinh viên này.', 'error')
        
    referrer = safe_referrer('/master/students')
    if '/master/student/detail' in referrer:
        return redirect('/master/students')
        
    return redirect(referrer)

@master_bp.route('/master/majors/add', methods=['POST'])
@role_required('master')
def add_major():
    major_name = request.form.get('major_name')
    major_code = request.form.get('major_code')
    try:
        max_students = int(request.form.get('max_students', 1000))
    except ValueError:
         flash('Chỉ tiêu phải là một số nguyên!', 'error')
         return redirect('/master/students')
    
    if StudentProfile.add_major(major_name, major_code, max_students):
        flash(f'Đã thêm ngành {major_name} thành công!', 'success')
    else:
        flash('Lỗi: Ngành này có thể đã tồn tại trong hệ thống.', 'error')
    return redirect('/master/students')

@master_bp.route('/master/majors/delete', methods=['POST'])
@role_required('master')
def delete_major():
    major_name = request.form.get('major_name')
    success, message = StudentProfile.delete_major(major_name)
    if success:
        flash(message, 'success')
        return redirect('/master/students')
    else:
        flash(message, 'error')
        return redirect(safe_referrer('/master/students'))


# Bộ lọc khối/ngành của trang lớp tín chỉ: giá trị gửi lên là danh sách đầu mã lớp, chỉ chấp nhận các giá trị ở đây
CREDIT_CLASS_PREFIX_GROUPS = [
    ('BAS,CS', 'Khối Đại cương (BAS/CS)'),
    ('IT,CN', 'Công nghệ thông tin (IT/CN)'),
    ('AT', 'An toàn thông tin (AT)'),
    ('KH', 'Khoa học máy tính (KH)'),
    ('PT', 'Đa phương tiện (PT)'),
    ('EL,VT', 'Điện tử Viễn thông (EL/VT)'),
    ('DT', 'Điện - Điện tử (DT)'),
    ('BZ,QT', 'Quản trị kinh doanh (BZ/QT)'),
    ('MR', 'Marketing (MR)'),
    ('KT', 'Kế toán (KT)'),
    ('TM', 'Thương mại điện tử (TM)'),
]
CREDIT_CLASS_YEARS = [2026, 2025, 2024]
CREDIT_CLASS_PAGE_SIZES = (25, 50, 100)
ADMIN_PAGE_SIZES = (20, 50, 100)
AUDIT_LOG_PAGE_SIZES = (25, 50, 100)


@master_bp.route('/master/grades')
@role_required('master')
def manage_grades():
    credit_class_id = request.args.get('credit_class_id')

    if credit_class_id:
        current_class = Grade.get_credit_class(credit_class_id)
        if not current_class:
            abort(404)

        students = Grade.get_students_in_credit_class(credit_class_id)
        return render_template('master/manage_grades.html',
                               current_class=current_class,
                               students=students)

    page, per_page, keyword = get_page_args(CREDIT_CLASS_PAGE_SIZES, CREDIT_CLASS_PAGE_SIZES[0])
    prefix = request.args.get('prefix', '')
    if prefix not in dict(CREDIT_CLASS_PREFIX_GROUPS):
        prefix = ''
    semester = request.args.get('semester', type=int)
    if semester not in (1, 2, 3):
        semester = None
    year = request.args.get('year', type=int)

    credit_classes, total_records, page = Grade.search_credit_classes(
        keyword, prefix.split(',') if prefix else (), semester, year, page, per_page
    )
    filters = {'q': keyword, 'prefix': prefix, 'semester': semester, 'year': year,
               'per_page': per_page if per_page != CREDIT_CLASS_PAGE_SIZES[0] else None}
    year_options = CREDIT_CLASS_YEARS if year in CREDIT_CLASS_YEARS or not year else sorted(CREDIT_CLASS_YEARS + [year], reverse=True)

    return render_template('master/manage_grades.html',
                           credit_classes=credit_classes,
                           admin_options=StaffProfile.get_admin_options(),
                           current_class=None,
                           filters=filters,
                           query_params={k: v for k, v in filters.items() if v},
                           prefix_groups=CREDIT_CLASS_PREFIX_GROUPS,
                           year_options=year_options,
                           page_sizes=CREDIT_CLASS_PAGE_SIZES,
                           per_page=per_page,
                           current_page=page,
                           total_pages=math.ceil(total_records / per_page),
                           total_records=total_records)

@master_bp.route('/master/grades/enroll', methods=['POST'])
@role_required('master')
def enroll_students_in_credit_class():
    credit_class_id = request.form.get('credit_class_id', '').strip()
    raw_identifiers = request.form.get('student_identifiers', '')
    
    excel_file = request.files.get('excel_file')
    excel_identifiers = []
    
    if excel_file and excel_file.filename.lower().endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(excel_file, dtype=str)
            target_cols = ['masv', 'mã sv', 'mã sinh viên', 'email', 'username']
            for col in df.columns:
                if str(col).strip().lower() in target_cols:
                    excel_identifiers.extend(df[col].dropna().astype(str).tolist())
        except Exception:
            flash("Lỗi đọc file Excel: Vui lòng kiểm tra định dạng tệp.", "error")
            return redirect(safe_referrer('/master/grades'))

    combined_raw = raw_identifiers + " " + " ".join(excel_identifiers)
    
    student_identifiers = [
        identifier.strip()
        for identifier in re.split(r'[\s,;]+', combined_raw)
        if identifier.strip()
    ]
    
    if not credit_class_id or not student_identifiers:
        flash('Hãy chọn lớp và nhập (hoặc tải lên) ít nhất một mã sinh viên/email.', 'error')
        return redirect(safe_referrer('/master/grades'))

    success, message = Grade.enroll_students(credit_class_id, student_identifiers)
    flash(message, 'success' if success else 'error')
    return redirect(safe_referrer('/master/grades'))

@master_bp.route('/master/grades/unenroll', methods=['POST'])
@role_required('master')
def unenroll_student_from_credit_class():
    """Hủy ghi danh một sinh viên chưa có điểm (ghi danh nhầm) khỏi lớp tín chỉ"""
    credit_class_id = request.form.get('credit_class_id', '').strip()
    grade_id = request.form.get('grade_id', '').strip()
    if not credit_class_id or not grade_id:
        flash('Thiếu thông tin lớp tín chỉ hoặc sinh viên cần hủy ghi danh.', 'error')
        return redirect(safe_referrer('/master/grades'))

    success, message = Grade.unenroll_student(credit_class_id, grade_id)
    flash(message, 'success' if success else 'error')
    return redirect(safe_referrer('/master/grades'))

@master_bp.route('/master/grades/export')
@role_required('master')
def master_export_grades():
    credit_class_id = request.args.get('credit_class_id')
    if not credit_class_id:
        abort(400)

    current_class = Grade.get_credit_class(credit_class_id)
    if not current_class:
        abort(404)

    students = Grade.get_students_in_credit_class(credit_class_id)
    output, filename = GradeExportService.create_workbook(current_class, students)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@master_bp.route('/master/grades/assign_lecturer', methods=['POST'])
@role_required('master')
def assign_lecturer():
    credit_class_id = request.form.get('credit_class_id')
    lecturer_email = request.form.get('lecturer_email')
    
    if not credit_class_id or not lecturer_email:
        flash("Dữ liệu phân công không hợp lệ.", "error")
        return redirect(safe_referrer('/master/grades'))
        
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, username FROM users WHERE username = %s AND role = 'admin'", (lecturer_email,))
            admin_user = cursor.fetchone()
            
        if admin_user:
            success = Grade.assign_lecturer(credit_class_id, admin_user['id'])
            if success:
                flash(f"Đã phân công tài khoản [{admin_user['username']}] phụ trách lớp tín chỉ!", "success")
            else:
                flash("Không tìm thấy lớp tín chỉ hoặc lỗi cập nhật CSDL.", "error")
        else:
            flash("Không tìm thấy tài khoản Admin này.", "error")
    except Exception:
        flash("Lỗi hệ thống.", "error")
        
    return redirect(safe_referrer('/master/grades'))

@master_bp.route('/master/profile')
@role_required('master')
def master_profile():
    active_tab = request.args.get('tab', 'info')
    user_id = session.get('user_id')
    username = session.get('username')
    
    user_obj = User.get_user_by_username(username)
    result = StaffProfile.get_master_profile(user_id)
    
    user_info = {
        'username': username,
        'personal_email': (user_obj.personal_email or '') if user_obj else '',
        'full_name': '',
        'id_card': '',
        'phone_number': '',
        'dob': '',
        'gender': 'Nam',
        'address': ''
    }
    
    if result:
        dob_str = ''
        if result.get('date_of_birth'):
            dob_raw = result['date_of_birth']
            if hasattr(dob_raw, 'strftime'):
                dob_str = dob_raw.strftime('%Y-%m-%d')
            else:
                dob_str = str(dob_raw).split(' ')[0]
                
        user_info.update({
            # Cột NULL trả về None: dùng `or ''` để ô nhập không hiện chữ "None" (và không bị lưu lại thành "None")
            'full_name': result.get('full_name') or '',
            'id_card': result.get('id_card') or '',
            'phone_number': result.get('phone_number') or '',
            'dob': dob_str,
            'gender': result.get('gender') or '',
            'address': result.get('address') or ''
        })
        
    stats = _system_counts('total_students', 'total_admins', 'total_classes', 'total_majors', 'total_audit_logs')

    return render_template('master/profile.html', 
                           active_tab=active_tab, 
                           user_info=user_info,
                           stats=stats,
                           total_students=stats['total_students'],
                           total_admins=stats['total_admins'],
                           total_classes=stats['total_classes'],
                           total_majors=stats['total_majors'],
                           total_audit_logs=stats['total_audit_logs'])

@master_bp.route('/master/profile/update_info', methods=['POST'])
@role_required('master')
def master_update_info():
    user_id = session.get('user_id')
    full_name = request.form.get('full_name')
    id_card = request.form.get('id_card')
    phone_number = request.form.get('phone_number')
    dob = request.form.get('dob')
    gender = request.form.get('gender')
    address = request.form.get('address')
    
    success = StaffProfile.update_master_profile(
        user_id, full_name, phone_number, dob, gender, address, id_card=id_card
    )
    
    if success:
        session['display_name'] = full_name.strip()
        session['display_initial'] = full_name.strip()[0].upper()
        flash("Đã lưu thông hồ sơ thành công!", "success")
    else:
        flash("Đã có lỗi xảy ra khi lưu thông tin.", "error")
        
    return redirect('/master/profile?tab=info')

@master_bp.route('/master/profile/update_password', methods=['POST'])
@role_required('master')
def master_update_password():
    user_id = session.get('user_id')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận không khớp!", "error")
        return redirect('/master/profile?tab=settings')
        
    success, message = User.change_password(user_id, current_password, new_password)
    
    if success:
        # Giữ phiên hiện tại; các phiên khác của tài khoản mất hiệu lực vì mật khẩu đã đổi
        session['pw_fp'] = User.current_password_fingerprint(user_id)
        session.pop('force_password_change', None)
        flash(message, "success")
    else:
        flash(message, "error")
        
    return redirect('/master/profile?tab=settings')

@master_bp.route('/master/student/detail')
@role_required('master')
def student_detail():
    username = (request.args.get('username') or '').strip()
    if not username:
        flash("Không tìm thấy sinh viên.", "error")
        return redirect('/master/students')

    profile = StudentProfile.get_student_profile(username) 
    if not profile:
        flash("Hồ sơ sinh viên không tồn tại hoặc đã bị xóa.", "error")
        return redirect('/master/students')

    raw_grades = Grade.get_all_grades_by_student(profile['user_id'])
    
    grouped_grades = {}
    for g in raw_grades:
        term = f"Học kỳ {g['semester']} - Năm học {g['year']}"
        if term not in grouped_grades:
            grouped_grades[term] = []
        grouped_grades[term].append(g)
    
    return render_template('master/student_detail.html', profile=profile, grouped_grades=grouped_grades)

@master_bp.route('/master/classes/assign_advisor', methods=['POST'])
@role_required('master')
def assign_advisor():
    class_name = request.form.get('class_name')
    advisor_data = request.form.get('advisor') 
    
    if not class_name or not advisor_data:
        flash("Vui lòng chọn đầy đủ thông tin.", "error")
        return redirect(safe_referrer('/master/students'))
        
    try:
        advisor_email, advisor_name = advisor_data.split('|', 1)
        
        success = StudentProfile.assign_advisor_to_class(class_name, advisor_email, advisor_name)
        if success:
            flash(f"Đã phân công Cố vấn {advisor_name} phụ trách lớp {class_name}!", "success")
        else:
            flash("Không tìm thấy lớp hành chính này hoặc lỗi cập nhật cơ sở dữ liệu.", "error")
    except ValueError:
        flash("Dữ liệu cố vấn không hợp lệ.", "error")
        
    return redirect(safe_referrer('/master/students'))

@master_bp.route('/master/admins')
@role_required('master')
def manage_admins():
    page, per_page, keyword = get_page_args(ADMIN_PAGE_SIZES, ADMIN_PAGE_SIZES[0])
    status = request.args.get('status', type=int)
    if status not in (0, 1):
        status = None

    admins_list, total_records, page = StaffProfile.search_admins(keyword, status, page, per_page)
    filters = {'q': keyword, 'status': status,
               'per_page': per_page if per_page != ADMIN_PAGE_SIZES[0] else None}

    return render_template('master/manage_admins.html',
                           admins_list=admins_list,
                           filters=filters,
                           query_params={k: v for k, v in filters.items() if v is not None and v != ''},
                           page_sizes=ADMIN_PAGE_SIZES,
                           per_page=per_page,
                           current_page=page,
                           total_pages=math.ceil(total_records / per_page),
                           total_records=total_records)

@master_bp.route('/master/admins/update', methods=['POST'])
@role_required('master')
def master_update_admin():
    user_id = request.form.get('user_id')
    full_name = request.form.get('full_name')
    id_card = request.form.get('id_card')
    phone_number = request.form.get('phone_number')
    dob = request.form.get('dob')
    gender = request.form.get('gender')
    address = request.form.get('address')
    
    success = StaffProfile.update_admin_profile_by_master(user_id, full_name, id_card, phone_number, dob, gender, address)
    if success:
        flash("Đã cập nhật hồ sơ Giảng viên thành công!", "success")
    else:
        flash("Lỗi cập nhật cơ sở dữ liệu.", "error")
        
    return redirect(safe_referrer('/master/admins'))

@master_bp.route('/master/admins/add', methods=['POST'])
@role_required('master')
def add_admin():
    email = request.form.get('email')
    full_name = request.form.get('full_name')
    
    success, msg, temp_password = StaffProfile.create_admin_account(email, full_name)
    if success:
        return render_issued_credentials(
            [{'username': email, 'full_name': full_name, 'password': temp_password}],
            safe_referrer('/master/admins'),
            msg
        )

    flash(msg, "error")
    return redirect(safe_referrer('/master/admins'))

@master_bp.route('/master/admins/toggle_status', methods=['POST'])
@role_required('master')
def toggle_admin_status():
    user_id = request.form.get('user_id')
    try:
        new_status = int(request.form.get('status', ''))
    except ValueError:
        new_status = None
    if not user_id or new_status not in (0, 1):
        flash("Dữ liệu trạng thái tài khoản không hợp lệ.", "error")
        return redirect(safe_referrer('/master/admins'))

    if StaffProfile.toggle_admin_status(user_id, new_status):
        log_security_event('admin_account_locked' if new_status == 0 else 'admin_account_unlocked',
                           target_user_id=user_id, by=session.get('username'))
        msg = "Đã KHÓA tài khoản và gỡ Giảng viên khỏi các lớp!" if new_status == 0 else "Đã MỞ KHÓA tài khoản thành công."
        flash(msg, "success")
    else:
        flash("Lỗi hệ thống.", "error")
        
    return redirect(safe_referrer('/master/admins'))

@master_bp.route('/master/admins/reset_password', methods=['POST'])
@role_required('master')
def reset_admin_password():
    user_id = request.form.get('user_id')
    
    issued = StaffProfile.reset_admin_password(user_id)
    if issued:
        username, temp_password = issued
        log_security_event('password_reset_by_master', target=username, by=session.get('username'))
        return render_issued_credentials(
            [{'username': username, 'password': temp_password}],
            safe_referrer('/master/admins'),
            f'Đã cấp mật khẩu tạm thời mới cho tài khoản {username}.'
        )

    flash("Lỗi hệ thống.", "error")
    return redirect(safe_referrer('/master/admins'))

@master_bp.route('/master/grades/class/save', methods=['POST'])
@role_required('master')
def save_credit_class():
    class_id = request.form.get('class_id')
    class_code = request.form.get('class_code')
    subject_name = request.form.get('subject_name')
    try:
        credits = int(request.form.get('credits', ''))
        semester = int(request.form.get('semester', ''))
        year = int(request.form.get('year', ''))
    except ValueError:
        flash('Số tín chỉ, học kỳ và năm phải là số nguyên hợp lệ.', 'error')
        return redirect(safe_referrer('/master/grades'))

    if not class_code or not subject_name or credits < 1 or semester not in (1, 2, 3) or year < 2000:
        flash('Thông tin lớp tín chỉ không hợp lệ.', 'error')
        return redirect(safe_referrer('/master/grades'))
    
    def get_float(field):
        val = request.form.get(field)
        return float(val) if val and val.strip() else 0.0

    try:
        weights = {
            'cc': get_float('weight_cc'), 'bttl': get_float('weight_bttl'),
            'tbkt': get_float('weight_tbkt'), 'tgk': get_float('weight_tgk'),
            'tnth': get_float('weight_tnth'), 'thi': get_float('weight_thi')
        }
    except ValueError:
        flash('Hệ số điểm phải là số hợp lệ.', 'error')
        return redirect(safe_referrer('/master/grades'))

    schedule = {
        'day_of_week': request.form.get('day_of_week') or None,
        'shift': request.form.get('shift'),
        'room': request.form.get('room')
    }

    if class_id:
        success, msg = Grade.update_credit_class(class_id, class_code, subject_name, credits, semester, year, weights, schedule,
                                               user_id=session.get('user_id'))
    else:
        success, msg = Grade.create_credit_class(class_code, subject_name, credits, semester, year, weights, schedule)
        
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
        
    return redirect(safe_referrer('/master/grades'))

@master_bp.route('/master/grades/class/delete', methods=['POST'])
@role_required('master')
def delete_credit_class():
    class_id = request.form.get('class_id')
    success, msg = Grade.delete_credit_class(class_id)
    
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
        
    return redirect(safe_referrer('/master/grades'))

@master_bp.route('/master/students/search', methods=['GET'])
@role_required('master')
def global_search_students():
    page, per_page, keyword = get_page_args((20,), 20)

    results = []
    total_records = 0

    if keyword:
        results, total_records, page = StudentProfile.search_global_students(keyword, page, per_page)

    total_pages = math.ceil(total_records / per_page) if total_records > 0 else 0
    
    return render_template(
        'master/search_results.html', 
        keyword=keyword, 
        students=results,
        current_page=page,
        total_pages=total_pages,
        total_records=total_records
    )

@master_bp.route('/master/students/import', methods=['POST'])
@role_required('master')
def import_students_excel():
    file = request.files.get('excel_file')
    if not file or not file.filename or not file.filename.lower().endswith(('.xlsx', '.xls')):
        flash("Vui lòng tải lên file Excel hợp lệ (.xlsx, .xls)", "error")
        return redirect('/master/students')
        
    try:
        dataframe = pd.read_excel(file, dtype=str, keep_default_na=False)
        missing_columns = set(StudentImportService.REQUIRED_FIELDS) - set(dataframe.columns)
        if missing_columns:
            flash(f"Thiếu cột bắt buộc: {', '.join(sorted(missing_columns))}.", "error")
            return redirect('/master/students')

        imported_count, errors, credentials = StudentImportService.import_rows(
            dataframe.to_dict(orient='records')
        )
        if errors:
            flash(f"Import bị hủy: {' '.join(errors[:5])}", "error")
        elif imported_count:
            # Mật khẩu tạm chỉ được trả về một lần dưới dạng file Excel, không lưu dạng rõ ở máy chủ
            flash(f"Đã import thành công {imported_count} hồ sơ sinh viên! File Excel mật khẩu tạm đã được tải xuống.", "success")
            return send_credentials_workbook(
                credentials, f"mat_khau_tam_import_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
    except Exception:
        flash("Lỗi đọc file Excel: Vui lòng kiểm tra lại cấu trúc cột.", "error")
        
    return redirect('/master/students')

@master_bp.route('/master/majors/update', methods=['POST'])
@role_required('master')
def update_major_info():
    major_id = request.form.get('major_id')
    new_name = request.form.get('major_name', '').strip()
    try:
        new_quota = int(request.form.get('quota', ''))
    except ValueError:
        flash('Chỉ tiêu phải là số nguyên dương.', 'error')
        return redirect('/master/students')

    if not major_id or not new_name or new_quota < 1:
        flash('Thông tin ngành không hợp lệ.', 'error')
        return redirect('/master/students')

    success, message = StudentProfile.update_major(major_id, new_name, new_quota)
    flash(message, 'success' if success else 'error')
    return redirect('/master/students')

@master_bp.route('/master/audit_logs')
@role_required('master')
def view_audit_logs():
    page, per_page, keyword = get_page_args(AUDIT_LOG_PAGE_SIZES, AUDIT_LOG_PAGE_SIZES[0])
    field_name = request.args.get('field', '')
    if field_name not in Grade.AUDIT_FIELD_NAMES.values():
        field_name = ''

    logs, total_records, page = Grade.search_audit_logs(keyword, field_name or None, page, per_page)
    filters = {'q': keyword, 'field': field_name,
               'per_page': per_page if per_page != AUDIT_LOG_PAGE_SIZES[0] else None}

    return render_template('master/audit_logs.html',
                           logs=logs,
                           filters=filters,
                           query_params={k: v for k, v in filters.items() if v},
                           field_options=list(Grade.AUDIT_FIELD_NAMES.values()),
                           page_sizes=AUDIT_LOG_PAGE_SIZES,
                           per_page=per_page,
                           current_page=page,
                           total_pages=math.ceil(total_records / per_page),
                           total_records=total_records)

@master_bp.route('/master/announcements')
@role_required('master')
def manage_announcements():
    announcements = Announcement.get_all_announcements()
    return render_template('master/announcements.html', announcements=announcements)
    
@master_bp.route('/master/announcements/add', methods=['POST'])
@role_required('master')
def add_announcement():
    title = request.form.get('title')
    content = request.form.get('content')
    target_class = request.form.get('target_class')
    user_id = session.get('user_id')
    
    if Announcement.create_announcement(title, content, target_class, user_id):
        flash('Phát hành thông báo toàn trường thành công!', 'success')
    else:
        flash('Lỗi khi phát hành thông báo.', 'error')
    return redirect('/master/announcements')

@master_bp.route('/master/announcements/delete', methods=['POST'])
@role_required('master')
def delete_announcement():
    ann_id = request.form.get('ann_id')
    if Announcement.delete_announcement(ann_id):
        flash('Đã thu hồi thông báo.', 'success')
    else:
        flash('Không tìm thấy thông báo hoặc lỗi hệ thống.', 'error')
    return redirect('/master/announcements')

@master_bp.route('/master/admin/detail')
@role_required('master')
def admin_detail():
    target_user_id = request.args.get('user_id')
    if not target_user_id:
        flash("Không tìm thấy ID Giảng viên.", "error")
        return redirect('/master/admins')

    user_account = {}
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT username, personal_email, is_active FROM users WHERE id = %s AND role = 'admin'", (target_user_id,))
            user_account = cursor.fetchone()
    except Exception:
        pass

    if not user_account:
        flash("Tài khoản Giảng viên không tồn tại hoặc đã bị xóa.", "error")
        return redirect('/master/admins')

    email = user_account['username']

    # Cột NULL thành '' để form sửa hồ sơ không hiện và không lưu lại chữ "None"
    profile = {key: ('' if value is None else value) for key, value in (StaffProfile.get_admin_profile(target_user_id) or {}).items()}
    
    dob_str = ''
    if profile.get('date_of_birth'):
        dob_raw = profile['date_of_birth']
        dob_str = dob_raw.strftime('%Y-%m-%d') if hasattr(dob_raw, 'strftime') else str(dob_raw).split(' ')[0]
    profile['date_of_birth'] = dob_str

    profile.update(user_account)

    lecturer_classes = Grade.get_credit_classes_by_lecturer(target_user_id)
    advisor_classes = StudentProfile.get_classes_by_advisor(email)

    return render_template(
        'master/admin_detail.html',
        profile=profile,
        lecturer_classes=lecturer_classes,
        advisor_classes=advisor_classes,
        target_user_id=target_user_id
    )

@master_bp.route('/master/students/reset_password', methods=['POST'])
@role_required('master')
def reset_student_password():
    username = request.form.get('username')
    
    temp_password = User.reset_student_password(username)
    if temp_password:
        log_security_event('password_reset_by_master', target=username, by=session.get('username'))
        return render_issued_credentials(
            [{'username': username, 'password': temp_password}],
            safe_referrer('/master/students'),
            f'Đã cấp mật khẩu tạm thời mới cho tài khoản {username}.'
        )

    flash('Lỗi: Không thể đặt lại mật khẩu. Vui lòng thử lại.', 'error')
    return redirect(safe_referrer('/master/students'))