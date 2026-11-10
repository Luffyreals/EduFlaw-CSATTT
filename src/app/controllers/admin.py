import math
from flask import Blueprint, session, redirect, render_template, request, flash, abort, send_file, jsonify
from app.models.user_model import User
from app.models.grade_model import Grade
from app.models.profile_model import StudentProfile
from app.models.staff_model import StaffProfile
from app.services.grade_export_service import GradeExportService
from app.models.announcement_model import Announcement
from app.utils.decorators import role_required
from app.utils.navigation import safe_referrer
from app.utils.temp_password import render_issued_credentials
from app.utils.db_helper import get_db_cursor
from app.utils.security_log import log_security_event

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@role_required('admin')
def admin_dashboard():
    username = session.get('username') 
    user_id = session.get('user_id')   

    total_advisor_students = StudentProfile.get_advisor_dashboard_stats(username)
    lecturer_stats = Grade.get_lecturer_dashboard_stats(user_id)
    timetable = Grade.get_lecturer_schedule(user_id)
    
    return render_template('admin/dashboard.html', 
                           total_students=total_advisor_students, 
                           total_classes=lecturer_stats['total_classes'], 
                           total_credits=lecturer_stats['total_credits'], 
                           timetable=timetable)

@admin_bp.route('/admin/students')
@role_required('admin')
def manage_students():
    requested_major = request.args.get('major')
    requested_class = request.args.get('class_name')
    requested_cohort = request.args.get('cohort')
    current_username = session.get('username') 

    if requested_class:
        if not StudentProfile.is_class_assigned_to_advisor(requested_class, current_username):
            abort(403)
            
        page = request.args.get('page', 1, type=int)
        per_page = 50
        profiles, total_records = StudentProfile.get_profiles_by_class(requested_class, page, per_page)
        
        total_pages = math.ceil(total_records / per_page) if total_records > 0 else 0
        
        return render_template('admin/manage_students.html', 
                               profiles=profiles, 
                               selected_class=requested_class, 
                               selected_major=requested_major,
                               selected_cohort=requested_cohort,
                               current_page=page,
                               total_pages=total_pages)

    advisor_classes = StudentProfile.get_classes_by_advisor(current_username)
    return render_template('admin/manage_students.html', 
                           advisor_classes=advisor_classes,
                           selected_class=None,
                           selected_major=None,
                           selected_cohort=None)

@admin_bp.route('/admin/students/update', methods=['POST'])
@role_required('admin')
def update_student():
    username = request.form.get('username') 
    current_admin_email = session.get('username')
    
    if not StudentProfile.is_student_assigned_to_advisor(username, current_admin_email):
        return abort(403)
    
    # Học phí và kỷ luật do Master quản lý (form của cố vấn không có hai trường này): không nhận kể cả khi POST tự tạo
    allowed_fields = [
        'full_name', 'gender', 'dob', 'phone_number',
        'class_role', 'status', 'nationality', 'ethnicity', 'religion',
        'id_card', 'hometown', 'current_address'
    ]
    update_data = {k: request.form.get(k) for k in allowed_fields if k in request.form}

    success = StudentProfile.update_student_profile(username, update_data)
    if success:
        flash('Đã cập nhật thông tin sinh viên thành công!', 'success')
    else:
        flash('Có lỗi xảy ra khi cập nhật dữ liệu.', 'error')
        
    return redirect(safe_referrer('/admin/students'))

@admin_bp.route('/admin/profile')
@role_required('admin')
def admin_profile():
    active_tab = request.args.get('tab', 'info')
    user_id = session.get('user_id')
    username = session.get('username')
    
    user_obj = User.get_user_by_username(username)
    result = StaffProfile.get_admin_profile(user_id)
    
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
            'full_name': result.get('full_name') or '',
            'id_card': result.get('id_card') or '',
            'phone_number': result.get('phone_number') or '',
            'dob': dob_str,
            'gender': result.get('gender') or 'Nam',
            'gender_locked': bool(result.get('gender')),
            'address': result.get('address') or ''
        })

    advisor_classes = StudentProfile.get_classes_by_advisor(username)
    lecturer_classes = Grade.get_credit_classes_by_lecturer(user_id)
    total_advisor_students = StudentProfile.get_advisor_dashboard_stats(username)
    lecturer_stats = Grade.get_lecturer_dashboard_stats(user_id)
    
    return render_template(
        'admin/profile.html',
        active_tab=active_tab,
        user_info=user_info,
        advisor_classes=advisor_classes,
        lecturer_classes=lecturer_classes,
        total_advisor_students=total_advisor_students,
        lecturer_stats=lecturer_stats
    )

@admin_bp.route('/admin/profile/update_info', methods=['POST'])
@role_required('admin')
def admin_update_info():
    user_id = session.get('user_id')
    full_name = request.form.get('full_name')
    id_card = request.form.get('id_card')
    phone_number = request.form.get('phone_number')
    dob = request.form.get('dob')
    gender = request.form.get('gender')
    address = request.form.get('address')
    
    saved_full_name = StaffProfile.update_admin_profile_by_self(
        user_id, full_name, id_card, phone_number, dob, gender, address
    )

    if saved_full_name is not None:
        if saved_full_name:
            session['display_name'] = saved_full_name
            session['display_initial'] = saved_full_name.strip()[0].upper()
            
        flash("Đã lưu thông tin hồ sơ giảng viên thành công!", "success")
    else:
        flash("Đã có lỗi xảy ra khi lưu thông tin.", "error")
        
    return redirect('/admin/profile?tab=info')

@admin_bp.route('/admin/profile/update_password', methods=['POST'])
@role_required('admin')
def admin_update_password():
    user_id = session.get('user_id')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận không khớp!", "error")
        return redirect('/admin/profile?tab=settings')
        
    success, message = User.change_password(user_id, current_password, new_password)
    
    if success:
        # Giữ phiên hiện tại; các phiên khác của tài khoản mất hiệu lực vì mật khẩu đã đổi
        session['pw_fp'] = User.current_password_fingerprint(user_id)
        session.pop('force_password_change', None)
        flash(message, "success")
    else:
        flash(message, "error")
        
    return redirect('/admin/profile?tab=settings')

@admin_bp.route('/admin/grades')
@role_required('admin')
def manage_grades():
    credit_class_id = request.args.get('credit_class_id')
    user_id = session.get('user_id')

    if credit_class_id:
        classes = Grade.get_credit_classes_by_lecturer(user_id)
        current_class = next((c for c in classes if str(c['id']) == credit_class_id), None)
        if not current_class:
            abort(403)
        students = Grade.get_students_in_credit_class(credit_class_id)
        
        return render_template('admin/grades.html', 
                               students=students, 
                               current_class=current_class)

    lecturer_classes = Grade.get_credit_classes_by_lecturer(user_id)
    return render_template('admin/grades.html', 
                           lecturer_classes=lecturer_classes,
                           current_class=None)

@admin_bp.route('/admin/grades/export')
@role_required('admin')
def export_grades():
    credit_class_id = request.args.get('credit_class_id')
    if not credit_class_id:
        abort(400)

    classes = Grade.get_credit_classes_by_lecturer(session['user_id'])
    current_class = next((item for item in classes if str(item['id']) == credit_class_id), None)
    if not current_class:
        abort(403)

    students = Grade.get_students_in_credit_class(credit_class_id)
    output, filename = GradeExportService.create_workbook(current_class, students)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@admin_bp.route('/admin/grades/add', methods=['POST'])
@role_required('admin')
def add_grade():
    user_id = session.get('user_id')
    credit_class_id = request.form.get('credit_class_id')
    
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT lecturer_id FROM credit_classes WHERE id = %s", (credit_class_id,))
            class_info = cursor.fetchone()
            
            if not class_info or class_info['lecturer_id'] != user_id:
                flash("⛔ Cảnh báo bảo mật: Bạn không có quyền nhập điểm cho lớp học phần này!", "error")
                return redirect('/admin/grades')
    except Exception:
        flash("Lỗi hệ thống khi xác thực quyền truy cập.", "error")
        return redirect('/admin/grades')

    score_field_names = {
        'cc': 'score_cc',
        'bttl': 'score_bttl',
        'tbkt': 'score_tbkt',
        'tgk': 'score_tgk',
        'tnth': 'score_tnth',
        'thi': 'score_thi',
        'thi2': 'score_thi_2'
    }
    grade_ids = set()
    for key in request.form.keys():
        field_name, separator, grade_id = key.partition('_')
        if separator and field_name in score_field_names and grade_id.isdecimal():
            grade_ids.add(grade_id)

    if not grade_ids:
        flash('Không tìm thấy điểm sinh viên cần lưu.', 'error')
        return redirect(f'/admin/grades?credit_class_id={credit_class_id}')

    grades_data = {}
    invalid_score_ids = []
    for gid in grade_ids:
        invalid_score = False

        def get_float_or_null(field_name):
            nonlocal invalid_score
            val = request.form.get(f"{field_name}_{gid}")
            if not val or not val.strip():
                return None
            try:
                score = float(val)
            except ValueError:
                invalid_score = True
                return None
            if not Grade.is_valid_score(score):
                invalid_score = True
                return None
            return score
            
        data = {
            'score_cc': get_float_or_null('cc'),
            'score_bttl': get_float_or_null('bttl'),
            'score_tbkt': get_float_or_null('tbkt'),
            'score_tgk': get_float_or_null('tgk'),
            'score_tnth': get_float_or_null('tnth'),
            'score_thi': get_float_or_null('thi'),
            'score_thi_2': get_float_or_null('thi2')
        }

        if invalid_score:
            invalid_score_ids.append(gid)
        else:
            grades_data[gid] = data

    if invalid_score_ids:
        flash('Điểm phải là số trong khoảng 0–10. Chưa có dữ liệu nào được lưu.', 'error')
        return redirect(f'/admin/grades?credit_class_id={credit_class_id}')

    reason = request.form.get('reason')
    if not Grade.update_detailed_grades(credit_class_id, grades_data, user_id=user_id, reason=reason):
        flash('Không thể lưu bảng điểm. Hãy kiểm tra dữ liệu và quyền lớp học phần.', 'error')
    else:
        flash("Đã tính toán và lưu bảng điểm thành công!", "success")
    return redirect(f'/admin/grades?credit_class_id={credit_class_id}')

@admin_bp.route('/admin/announcements')
@role_required('admin')
def manage_announcements():
    user_id = session.get('user_id')
    username = session.get('username')
    announcements = Announcement.get_announcements_by_author(user_id)
    advisor_classes = StudentProfile.get_classes_by_advisor(username)
    
    return render_template('admin/announcements.html', announcements=announcements, advisor_classes=advisor_classes)
    
@admin_bp.route('/admin/announcements/add', methods=['POST'])
@role_required('admin')
def add_announcement():
    title = request.form.get('title')
    content = request.form.get('content')
    target_class = request.form.get('target_class') 
    user_id = session.get('user_id')
    username = session.get('username')
    
    if not target_class or not target_class.strip():
        flash('Vui lòng chọn lớp đích để nhận thông báo.', 'error')
        return redirect('/admin/announcements')
        
    if not StudentProfile.is_class_assigned_to_advisor(target_class, username):
        flash('⛔ Cảnh báo bảo mật: Bạn không có quyền gửi thông báo cho lớp này!', 'error')
        return abort(403)
    
    if Announcement.create_announcement(title, content, target_class, user_id):
        flash('Đăng thông báo thành công!', 'success')
    else:
        flash('Lỗi khi đăng thông báo.', 'error')
    return redirect('/admin/announcements')

@admin_bp.route('/admin/announcements/delete', methods=['POST'])
@role_required('admin')
def delete_announcement():
    ann_id = request.form.get('ann_id')
    user_id = session.get('user_id')
    
    my_announcements = Announcement.get_announcements_by_author(user_id)
    if not any(str(ann['id']) == str(ann_id) for ann in my_announcements):
        flash('⛔ Cảnh báo bảo mật: Bạn không có quyền xóa thông báo của người khác!', 'error')
        return abort(403)
        
    if Announcement.delete_announcement(ann_id):
        flash('Đã xóa thông báo.', 'success')
    else:
        flash('Lỗi khi xóa thông báo.', 'error')
    return redirect('/admin/announcements')

@admin_bp.route('/admin/grades/api/auto-save', methods=['POST'])
@role_required('admin')
def api_auto_save_grade():
    data = request.get_json(silent=True) or {}
    grade_id = str(data.get('grade_id') or '').strip()
    field_name = str(data.get('field') or '').strip()
    raw_value = data.get('value')
    user_id = session.get('user_id')

    allowed_fields = {
        'score_cc', 'score_bttl', 'score_tbkt',
        'score_tgk', 'score_tnth', 'score_thi', 'score_thi_2'
    }
    if not grade_id.isdecimal() or field_name not in allowed_fields:
        return jsonify({'success': False, 'message': 'Dữ liệu đầu điểm không hợp lệ.'}), 400

    if raw_value is None or str(raw_value).strip() == '':
        parsed_value = None
    else:
        try:
            parsed_value = float(raw_value)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Điểm số phải là số hợp lệ.'}), 400

        if not Grade.is_valid_score(parsed_value):
            return jsonify({'success': False, 'message': 'Điểm phải nằm trong khoảng 0–10.'}), 400

    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT g.credit_class_id, c.lecturer_id
                FROM grades g
                JOIN credit_classes c ON g.credit_class_id = c.id
                WHERE g.id = %s
                """,
                (grade_id,)
            )
            row = cursor.fetchone()
    except Exception:
        return jsonify({'success': False, 'message': 'Lỗi truy vấn cơ sở dữ liệu.'}), 500

    if not row or row['lecturer_id'] != user_id:
        return jsonify({
            'success': False,
            'message': '⛔ Bạn không có quyền chỉnh sửa điểm của lớp học phần này!'
        }), 403

    # Chỉ gửi ô vừa sửa: model gộp với giá trị mới nhất trong CSDL (dòng bị khóa), nên hai ô auto-save
    # gửi gần như cùng lúc không đè mất nhau như khi đọc cả dòng ở đây rồi ghi đè lại
    saved = Grade.save_single_score(
        grade_id=grade_id,
        credit_class_id=row['credit_class_id'],
        field=field_name,
        value=parsed_value,
        user_id=user_id,
        reason='Lưu tự động (Auto-save)'
    )
    if saved is None:
        return jsonify({'success': False, 'message': 'Không thể lưu điểm vào cơ sở dữ liệu.'}), 500

    final_score = saved['score']
    converted = Grade.convert_score(final_score)

    return jsonify({
        'success': True,
        'message': 'Đã lưu điểm tự động',
        'score': final_score,
        'score_4': converted['score_4'],
        'letter': converted['letter'],
        'color': converted['color']
    })

@admin_bp.route('/admin/students/reset_password', methods=['POST'])
@role_required('admin')
def reset_student_password():
    username = request.form.get('username')
    current_admin_email = session.get('username')
    
    if not StudentProfile.is_student_assigned_to_advisor(username, current_admin_email):
        return abort(403)
        
    temp_password = User.reset_student_password(username)
    if temp_password:
        log_security_event('password_reset_by_advisor', target=username, by=current_admin_email)
        return render_issued_credentials(
            [{'username': username, 'password': temp_password}],
            safe_referrer('/admin/students'),
            f'Đã cấp mật khẩu tạm thời mới cho tài khoản {username}.'
        )

    flash('Lỗi: Không thể đặt lại mật khẩu. Vui lòng thử lại.', 'error')
    return redirect(safe_referrer('/admin/students'))