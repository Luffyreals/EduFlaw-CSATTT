import re
import math
from datetime import date
from flask import Blueprint, session, redirect, render_template, request, flash, abort
from app.models.grade_model import Grade
from app.models.user_model import User
from app.models.profile_model import StudentProfile
from app.models.announcement_model import Announcement
from app.utils.decorators import role_required
from app.utils.db_helper import get_db_cursor
from app.utils.field_crypto import decrypt_field

student_bp = Blueprint('student', __name__)

@student_bp.route('/student')
@role_required('student')
def student_dashboard():
    user_id = session.get('user_id')
    username = session.get('username')
    
    raw_grades = Grade.get_all_grades_by_student(user_id)
    gpa_data = Grade.calculate_gpa(raw_grades)

    # Biểu đồ xu hướng: GPA tích lũy (hệ 4) sau từng học kỳ có điểm, điểm cuối trùng với GPA tích lũy hiện tại
    terms = sorted({(int(g['year']), int(g['semester'])) for g in raw_grades if g.get('year') and g.get('semester')})
    gpa_trend = []
    for year, semester in terms:
        upto = [g for g in raw_grades
                if g.get('year') and g.get('semester') and (int(g['year']), int(g['semester'])) <= (year, semester)]
        stats = Grade.calculate_gpa(upto)
        if stats['total_credits']:
            gpa_trend.append({'label': f'HK{semester} {year}-{year + 1}', 'gpa': stats['gpa_4']})
    
    profile = StudentProfile.get_student_profile(username)
    class_name = profile['class_name'] if profile else None
    announcements = Announcement.get_announcements_for_student(class_name)
    
    raw_timetable = Grade.get_student_schedule(user_id)
    timetable = []
    if raw_timetable:
        latest_year = raw_timetable[0]['year']
        latest_semester = raw_timetable[0]['semester']
        timetable = [item for item in raw_timetable if item['year'] == latest_year and item['semester'] == latest_semester]

    return render_template('student/dashboard.html', gpa_data=gpa_data, gpa_trend=gpa_trend,
                           announcements=announcements, timetable=timetable)

@student_bp.route('/student/grades')
@role_required('student')
def view_grades():
    raw_grades = Grade.get_all_grades_by_student(session['user_id'])
    overall = Grade.calculate_gpa(raw_grades)

    groups = {}
    for g in raw_grades:
        key = f"Học kỳ {g['semester']} Năm học {g['year']} - {int(g['year'])+1}"
        groups.setdefault(key, []).append(g)

    display_groups = []
    cumulative_passed = 0
    
    for sem_key, items in groups.items():
        sem_stats = Grade.calculate_gpa(items) 
        cumulative_passed += sem_stats['total_passed_credits']
        
        display_groups.append({
            'title': f"{sem_key} (TB học kỳ: {sem_stats['gpa_4']}, Số TC đạt: {sem_stats['total_passed_credits']}, TC tích lũy: {cumulative_passed})",
            'raw_title': sem_key,
            'items': items
        })

    gpa = overall['gpa_4']
    # Cùng thang xếp loại với trang chi tiết sinh viên của Master; chưa có tín chỉ nào có điểm thì chưa xếp loại
    if not overall['total_credits']:
        standing = "Chưa xếp loại"
    else:
        standing = ("Xuất sắc" if gpa >= 3.6 else "Giỏi" if gpa >= 3.2 else "Khá" if gpa >= 2.5
                    else "Trung bình" if gpa >= 2.0 else "Yếu")

    return render_template(
        'student/grades.html', 
        display_groups=display_groups[::-1],
        gpa=gpa,
        total_credits=overall['total_passed_credits'],
        standing=standing
    )

@student_bp.route('/student/profile')
@role_required('student')
def student_profile():
    active_tab = request.args.get('tab', 'info')
    username = session.get('username') 
    
    user_info = {}
    
    try:
        with get_db_cursor(dictionary=True) as cursor:
            sql = """
                SELECT p.*, u.username, u.personal_email
                FROM student_profiles p
                JOIN users u ON p.user_id = u.id
                WHERE u.username = %s
            """
            cursor.execute(sql, (username,))
            result = cursor.fetchone()
            
            if result:
                dob_str = ''
                dob_raw = result.get('date_of_birth')
                if dob_raw:
                    if isinstance(dob_raw, date):
                        dob_str = dob_raw.strftime('%Y-%m-%d')
                    else:
                        dob_str = str(dob_raw).split(' ')[0] 
                
                user_info = {
                    'username': result.get('username') or username,
                    'personal_email': result.get('personal_email') or '',
                    'full_name': result.get('full_name') or '',
                    'student_code': result.get('student_code') or '',
                    'dob': dob_str,
                    'gender': result.get('gender') or 'Nam',
                    'id_card': decrypt_field(result.get('id_card')) or '',
                    'nationality': result.get('nationality') or 'Việt Nam',
                    'ethnicity': result.get('ethnicity') or 'Kinh',
                    'religion': result.get('religion') or 'Không',
                    'major': result.get('major') or '',
                    'cohort': result.get('cohort') or '',
                    'class_name': result.get('class_name') or '',
                    'class_role': result.get('class_role') or 'Thành viên',
                    'status': result.get('status') or 'Đang học',
                    'advisor_name': result.get('advisor_name') or '',
                    'advisor_email': result.get('advisor_email') or '',
                    'tuition_status': result.get('tuition_status') or 'Hoàn thành',
                    'disciplinary_note': result.get('disciplinary_note') or '',
                    'hometown': result.get('hometown') or '',
                    'phone_number': result.get('phone_number') or '',
                    'current_address': result.get('current_address') or ''
                }
                
                if user_info['full_name']:
                    session['display_initial'] = user_info['full_name'].strip()[0].upper()
                else:
                    session['display_initial'] = 'S'
            else:
                flash("Tài khoản chưa được liên kết với hồ sơ sinh viên hợp lệ.", "error")
                
    except Exception:
        flash("Không thể tải thông tin hồ sơ lúc này.", "error")
    
    return render_template('student/profile.html', active_tab=active_tab, user_info=user_info)

@student_bp.route('/student/profile/update_info', methods=['POST'])
@role_required('student')
def student_update_info():
    user_id = session.get('user_id')
    phone_number = request.form.get('phone_number')
    current_address = request.form.get('current_address')
    
    success = StudentProfile.update_student_contact(user_id, phone_number, current_address)
    
    if success:
        flash("Đã cập nhật thông tin liên lạc thành công!", "success")
    else:
        flash("Đã có lỗi xảy ra khi lưu thông tin.", "error")
        
    return redirect('/student/profile?tab=info')

@student_bp.route('/student/profile/update_password', methods=['POST'])
@role_required('student')
def student_update_password():
    user_id = session.get('user_id')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận không khớp!", "error")
        return redirect('/student/profile?tab=settings')
        
    success, message = User.change_password(user_id, current_password, new_password)
    
    if success:
        # Giữ phiên hiện tại; các phiên khác của tài khoản mất hiệu lực vì mật khẩu đã đổi
        session['pw_fp'] = User.current_password_fingerprint(user_id)
        session.pop('force_password_change', None)
        flash(message, "success")
    else:
        flash(message, "error")
        
    return redirect('/student/profile?tab=settings')

@student_bp.route('/student/schedule')
@role_required('student')
def view_schedule():
    user_id = session.get('user_id')
    raw_timetable = Grade.get_student_schedule(user_id)
    
    timetable = []
    if raw_timetable:
        latest_year = raw_timetable[0]['year']
        latest_semester = raw_timetable[0]['semester']
        timetable = [item for item in raw_timetable if item['year'] == latest_year and item['semester'] == latest_semester]
    
    schedule_grid = [[None for _ in range(7)] for _ in range(15)]
    
    for item in timetable:
        shift_str = str(item.get('shift', '')).strip()
        sessions = shift_str.replace('/', ';').split(';') if shift_str else []
        day_of_week = item.get('day_of_week')
        
        for s in sessions:
            clean_s = s.replace('Tiết', '').replace('tiết', '').replace('Kíp', '').replace('kíp', '').replace(',', '-').replace(' ', '').strip()
            if not clean_s:
                continue
                
            parts = clean_s.split('-')
            try:
                start = int(parts[0])
                end = int(parts[-1])
            except ValueError:
                continue
            
            if day_of_week and start > 0:
                end = max(end, start)
                day_idx = int(day_of_week) - 2
                if day_idx == 6 or day_idx == -1:
                    day_idx = 6
                    
                start_idx = start - 1
                rowspan = end - start + 1
                
                if 0 <= start_idx < 15 and 0 <= day_idx < 7:
                    cell_item = dict(item)
                    cell_item['rowspan'] = rowspan
                    cell_item['shift'] = f"{start}-{end}" if start != end else str(start)
                    schedule_grid[start_idx][day_idx] = cell_item

                    for i in range(1, rowspan):
                        if start_idx + i < 15:
                            schedule_grid[start_idx + i][day_idx] = 'skip'
                            
    return render_template('student/schedule.html', schedule_grid=schedule_grid)

@student_bp.route('/student/class')
@role_required('student')
def view_class():
    username = session.get('username')
    profile = StudentProfile.get_student_profile(username)
    
    if not profile or not profile.get('class_name'):
        flash("Bạn chưa được phân vào lớp hành chính nào.", "warning")
        return redirect('/student')
        
    class_name = profile['class_name']
    
    # Lấy danh sách thành viên trong lớp (dùng chung hàm với Admin)
    page = request.args.get('page', 1, type=int)
    per_page = 50
    classmates, total_records = StudentProfile.get_profiles_by_class(class_name, page, per_page)
    
    total_pages = math.ceil(total_records / per_page) if total_records > 0 else 0
    
    return render_template('student/class.html', 
                           profile=profile,
                           classmates=classmates,
                           current_page=page,
                           total_pages=total_pages,
                           total_records=total_records)

@student_bp.route('/student/credit-classes')
@role_required('student')
def view_credit_classes():
    user_id = session.get('user_id')
    credit_class_id = request.args.get('credit_class_id')
    
    my_classes = Grade.get_credit_classes_by_student(user_id)
    
    if credit_class_id:
        current_class = next((c for c in my_classes if str(c['id']) == str(credit_class_id)), None)
        if not current_class:
            abort(403)
            
        classmates = Grade.get_roster_in_credit_class(credit_class_id)
        return render_template(
            'student/credit_classes.html',
            current_class=current_class,
            classmates=classmates
        )
        
    return render_template(
        'student/credit_classes.html',
        my_classes=my_classes,
        current_class=None
    )