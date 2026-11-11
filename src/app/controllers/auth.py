import re
import time
from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.models.user_model import User
from app.models.profile_model import StudentProfile
from app.models.staff_model import StaffProfile
from app.models.security_state_model import SecurityState
from app.services.token_service import OtpService
from app.utils.db_helper import get_db_cursor
from app.utils.password_policy import validate_password_strength
from app.utils.security_log import log_security_event

auth_bp = Blueprint('auth', __name__)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60
GENERIC_OTP_SENT_MESSAGE = 'Nếu thông tin khớp với một tài khoản đã kích hoạt, mã OTP 6 số sẽ được gửi tới Gmail cá nhân đã liên kết.'
LEGACY_PASSWORD_DISABLED_MESSAGE = 'Mật khẩu mặc định cũ đã bị vô hiệu hóa. Vui lòng liên hệ Cố vấn học tập hoặc Phòng Đào tạo để được cấp mật khẩu tạm thời mới.'

# Trạng thái khóa đăng nhập nằm trong CSDL (SecurityState) nên đúng với nhiều worker và không mất khi restart

def _lockout_remaining(key):
    return max(0, int(SecurityState.lockout_until(key) - time.time()))

def _register_login_failure(key):
    """Ghi nhận một lần đăng nhập sai; trả về True nếu khóa tạm thời vừa được kích hoạt"""
    return SecurityState.register_failure(key, LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_SECONDS)

def _resolve_user(identifier):
    if not identifier:
        return None
    clean_id = identifier.strip()
    user = User.get_user_by_username(clean_id)
    if user:
        return user
    if '@' not in clean_id:
        return User.get_user_by_username(f"{clean_id.lower()}@eduflaw.com")
    return None

@auth_bp.before_app_request
def enforce_onboarding_gate():
    if 'user_id' not in session or not session.get('force_password_change'):
        return None

    allowed_endpoints = {
        'auth.onboarding',
        'auth.api_onboarding_save_and_send_otp',
        'auth.api_onboarding_verify_otp',
        'auth.onboarding_complete',
        'auth.logout',
        'auth.login',
        'static'
    }
    if request.endpoint in allowed_endpoints or request.blueprint == 'pentest':
        return None

    return redirect(url_for('auth.onboarding'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        ip_key = f"ip:{request.remote_addr}"
        username_input = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        try:
            user = _resolve_user(username_input)
        except Exception as err:
            error = 'Hệ thống chưa kết nối được cơ sở dữ liệu. Vui lòng kiểm tra cấu hình và thử lại.'
            print(f'Lỗi đăng nhập do DB: {type(err).__name__}')
            return render_template('auth/login.html', error=error), 503

        # Khóa theo cả IP lẫn tài khoản để kẻ tấn công không thể đổi IP mà dò tiếp mật khẩu của một tài khoản
        account_key = f"user:{(user.username if user else username_input).lower()}"
        wait_sec = max(_lockout_remaining(ip_key), _lockout_remaining(account_key))
        if wait_sec > 0:
            error = f"Tài khoản tạm khóa do nhập sai nhiều lần. Vui lòng thử lại sau {wait_sec} giây."
            return render_template('auth/login.html', error=error), 429

        if not User.verify_login_password(user, password):
            ip_locked = _register_login_failure(ip_key)
            account_locked = _register_login_failure(account_key)
            log_security_event('login_failed', account=username_input)
            if ip_locked or account_locked:
                log_security_event('login_lockout', account=username_input,
                                   scope='account' if account_locked else 'ip')
                error = f"Bạn đã nhập sai {LOGIN_MAX_ATTEMPTS} lần liên tiếp. Vui lòng đợi {LOGIN_LOCKOUT_SECONDS} giây trước khi thử lại."
                return render_template('auth/login.html', error=error), 429
            else:
                error = "Thông tin đăng nhập không chính xác."
        else:
            SecurityState.clear_failures(ip_key, account_key)
            log_security_event('login_success', account=user.username, role=user.role)

            endpoint_by_role = {
                'student': 'student.student_dashboard',
                'admin': 'admin.admin_dashboard',
                'master': 'master.master_dashboard'
            }
            endpoint = endpoint_by_role.get(user.role)
            needs_onboarding = user.needs_onboarding()
            if endpoint is None:
                error = "Thông tin đăng nhập không chính xác."
            elif needs_onboarding and User.uses_legacy_default_password(user.password):
                # Tài khoản chưa kích hoạt trên DB cũ vẫn dùng mật khẩu mặc định dùng chung (đoán được):
                # không cho đăng nhập để người khác không chiếm tài khoản bằng cách liên kết Gmail của họ
                error = LEGACY_PASSWORD_DISABLED_MESSAGE
            else:
                session.clear()
                session.permanent = True
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role

                session['force_password_change'] = needs_onboarding

                session['pw_fp'] = User.password_fingerprint(user.password)
                if not User.is_password_hashed(user.password):
                    if User.upgrade_legacy_password(user.id, password):
                        session['pw_fp'] = User.current_password_fingerprint(user.id)

                display_name = user.username
                profile_table = {
                    'student': 'student_profiles',
                    'admin': 'admin_profiles',
                    'master': 'master_profiles'
                }[user.role]
                
                try:
                    with get_db_cursor(dictionary=True) as cursor:
                        cursor.execute(f"SELECT full_name FROM {profile_table} WHERE user_id = %s", (user.id,))
                        profile = cursor.fetchone()
                        if profile and profile.get('full_name'):
                            display_name = profile['full_name']
                except Exception:
                    pass

                session['display_name'] = display_name
                session['display_initial'] = display_name.strip()[0].upper() if display_name else 'U'

                if session['force_password_change']:
                    return redirect(url_for('auth.onboarding'))

                return redirect(url_for(endpoint))

    return render_template('auth/login.html', error=error)

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect('/login')

def _valid_onboarding_session():
    """Luồng onboarding chỉ dành cho phiên vừa đăng nhập bằng mật khẩu tạm và vẫn còn hợp lệ.

    Không có kiểm tra này, một phiên cũ (ví dụ cookie bị lộ, dù mật khẩu đã được cấp lại để hủy nó) hay một máy
    bỏ quên đăng nhập có thể tự đặt mật khẩu mới và gắn Gmail khôi phục của người khác mà không cần mật khẩu.
    """
    if 'user_id' not in session or not session.get('force_password_change'):
        return False
    if not User.is_account_active(session.get('user_id'), session.get('role'), session.get('pw_fp', '')):
        session.clear()
        return False
    return True


@auth_bp.route('/onboarding', methods=['GET'])
def onboarding():
    if 'user_id' in session and not session.get('force_password_change'):
        # Tài khoản đã kích hoạt: không còn gì để làm ở trang này
        return redirect({'student': '/student', 'admin': '/admin', 'master': '/master'}.get(session.get('role'), '/login'))
    if not _valid_onboarding_session():
        return redirect('/login')

    role = session.get('role')
    user_id = session.get('user_id')
    username = session.get('username')

    user_obj = User.get_user_by_username(username)
    personal_email = (user_obj.personal_email or '') if user_obj else ''

    profile_data = {}
    if role == 'student':
        raw = StudentProfile.get_student_profile(username) or {}
        profile_data = {
            'student_code': raw.get('student_code') or '',
            'class_name': raw.get('class_name') or '',
            'major': raw.get('major') or '',
            'full_name': raw.get('full_name') or '',
            'dob': raw.get('date_of_birth') or '',
            'gender': raw.get('gender') or 'Nam',
            'gender_locked': bool(raw.get('gender')),
            'id_card': raw.get('id_card') or '',
            'phone_number': raw.get('phone_number') or '',
            'hometown': raw.get('hometown') or '',
            'address': raw.get('current_address') or '',
            'personal_email': personal_email
        }
    elif role == 'admin':
        raw = StaffProfile.get_admin_profile(user_id) or {}
        dob_str = ''
        if raw.get('date_of_birth'):
            dob_raw = raw['date_of_birth']
            dob_str = dob_raw.strftime('%Y-%m-%d') if hasattr(dob_raw, 'strftime') else str(dob_raw).split(' ')[0]
        profile_data = {
            'full_name': raw.get('full_name') or '',
            'dob': dob_str,
            'gender': raw.get('gender') or 'Nam',
            'gender_locked': bool(raw.get('gender')),
            'id_card': raw.get('id_card') or '',
            'phone_number': raw.get('phone_number') or '',
            'address': raw.get('address') or '',
            'personal_email': personal_email
        }
    else:
        raw = StaffProfile.get_master_profile(user_id) or {}
        dob_str = ''
        if raw.get('date_of_birth'):
            dob_raw = raw['date_of_birth']
            dob_str = dob_raw.strftime('%Y-%m-%d') if hasattr(dob_raw, 'strftime') else str(dob_raw).split(' ')[0]
        profile_data = {
            'full_name': raw.get('full_name') or '',
            'id_card': raw.get('id_card') or '',
            'dob': dob_str,
            'gender': raw.get('gender') or 'Nam',
            'phone_number': raw.get('phone_number') or '',
            'address': raw.get('address') or '',
            'personal_email': personal_email
        }

    verified_personal_email = (
        session.get('verified_personal_email') if session.get('onboarding_otp_verified') else None
    )
    return render_template('auth/onboarding.html', profile=profile_data, role=role,
                           verified_personal_email=verified_personal_email)

@auth_bp.route('/auth/api/onboarding/save-and-send-otp', methods=['POST'])
def api_onboarding_save_and_send_otp():
    if not _valid_onboarding_session():
        return jsonify({'success': False, 'message': 'Phiên đăng nhập đã hết hạn.'}), 401

    data = request.get_json(silent=True) or {}
    role = session.get('role')
    user_id = session.get('user_id')
    username = session.get('username')

    full_name = (data.get('full_name') or '').strip()
    dob = (data.get('dob') or '').strip()
    gender = (data.get('gender') or 'Nam').strip()
    id_card = (data.get('id_card') or '').strip()
    phone_number = (data.get('phone_number') or '').strip()
    hometown = (data.get('hometown') or '').strip()
    address = (data.get('address') or '').strip()
    personal_email = (data.get('personal_email') or '').strip().lower()

    if not all([full_name, dob, phone_number, address, personal_email]):
        return jsonify({'success': False, 'message': 'Vui lòng điền đầy đủ Họ tên, Ngày sinh, SĐT, Địa chỉ và Gmail cá nhân.'}), 400

    if role in ('student', 'admin') and not id_card:
        return jsonify({'success': False, 'message': 'Vui lòng nhập số CCCD / Mã định danh cá nhân.'}), 400

    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', personal_email):
        return jsonify({'success': False, 'message': 'Địa chỉ Email cá nhân không hợp lệ.'}), 400

    if personal_email.endswith('@eduflaw.com') or personal_email.endswith('@example.test'):
        return jsonify({'success': False, 'message': 'Vui lòng nhập hộp thư Gmail cá nhân thực tế (VD: @gmail.com), không dùng email nội bộ.'}), 400

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE personal_email = %s AND id != %s LIMIT 1", (personal_email, user_id))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Địa chỉ Gmail này đã được liên kết với một tài khoản khác trong hệ thống.'}), 400
    except Exception:
        pass

    wait_sec = OtpService.resend_wait_seconds(session, username)
    if wait_sec > 0:
        return jsonify({'success': False, 'message': f'Vui lòng đợi {wait_sec} giây trước khi yêu cầu mã OTP mới.'}), 429

    saved_ok = False
    if role == 'student':
        update_payload = {
            'phone_number': phone_number,
            'current_address': address
        }
        # Dữ liệu hồ sơ chính thức do nhà trường quản lý: sinh viên chỉ được bổ sung khi còn trống, không được ghi đè
        current_profile = StudentProfile.get_student_profile(username) or {}
        official_fields = {
            'full_name': full_name,
            'date_of_birth': dob,
            'gender': gender,
            'id_card': id_card,
            'hometown': hometown
        }
        for field, value in official_fields.items():
            if not current_profile.get(field):
                update_payload[field] = value
        full_name = current_profile.get('full_name') or full_name
        saved_ok = StudentProfile.update_student_profile(username, update_payload)
    elif role == 'admin':
        saved_full_name = StaffProfile.update_admin_profile_by_self(
            user_id, full_name, id_card, phone_number, dob, gender, address
        )
        saved_ok = saved_full_name is not None
        full_name = saved_full_name or full_name
    else:
        saved_ok = StaffProfile.update_master_profile(
            user_id, full_name, phone_number, dob, gender, address, id_card=id_card 
        )

    if not saved_ok:
        return jsonify({'success': False, 'message': 'Không thể lưu thông hồ sơ. Vui lòng kiểm tra lại dữ liệu.'}), 500

    session['display_name'] = full_name
    session['display_initial'] = full_name[0].upper()
    session['onboarding_otp_verified'] = False

    otp_code = OtpService.create_session_otp(session, username, personal_email)
    sent_ok, is_dev_mode = OtpService.send_otp_email(personal_email, username, otp_code)

    if not sent_ok:
        return jsonify({'success': False, 'message': 'Đã lưu hồ sơ nhưng không thể gửi email OTP. Hãy kiểm tra cấu hình SMTP.'}), 500

    res = {
        'success': True,
        'personal_email': personal_email,
        'message': f'Đã lưu thông tin cá nhân và gửi mã xác thực 6 số tới {personal_email}.'
    }
    
    return jsonify(res)

@auth_bp.route('/auth/api/onboarding/verify-otp', methods=['POST'])
def api_onboarding_verify_otp():
    if not _valid_onboarding_session():
        return jsonify({'success': False, 'message': 'Phiên đăng nhập đã hết hạn.'}), 401

    data = request.get_json(silent=True) or {}
    personal_email = (data.get('personal_email') or '').strip().lower()
    otp_code = (data.get('otp_code') or '').strip()
    username = session.get('username')

    is_valid, msg = OtpService.verify_session_otp(session, username, personal_email, otp_code)
    if not is_valid:
        return jsonify({'success': False, 'message': msg}), 400

    session['onboarding_otp_verified'] = True
    session['verified_personal_email'] = personal_email
    return jsonify({
        'success': True,
        'message': 'Xác thực Gmail thành công! Vui lòng thiết lập mật khẩu mới ở bước cuối.'
    })

@auth_bp.route('/onboarding/complete', methods=['POST'])
def onboarding_complete():
    if not _valid_onboarding_session():
        return redirect('/login')

    if not session.get('onboarding_otp_verified') or not session.get('verified_personal_email'):
        flash('Vui lòng xác thực mã OTP qua Gmail cá nhân trước khi đặt mật khẩu mới.', 'error')
        return redirect(url_for('auth.onboarding'))

    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if new_password != confirm_password:
        flash('Mật khẩu mới và xác nhận mật khẩu không khớp!', 'error')
        return redirect(url_for('auth.onboarding'))

    user_id = session.get('user_id')
    personal_email = session.get('verified_personal_email')

    success, message = User.complete_onboarding(user_id, personal_email, new_password)
    if not success:
        flash(message, 'error')
        return redirect(url_for('auth.onboarding'))

    # Mật khẩu vừa đổi: cập nhật dấu vân tay để giữ phiên này (các phiên khác của tài khoản sẽ mất hiệu lực)
    session['pw_fp'] = User.current_password_fingerprint(user_id)
    session.pop('force_password_change', None)
    session.pop('onboarding_otp_verified', None)
    session.pop('verified_personal_email', None)
    log_security_event('onboarding_complete', account=session.get('username'))

    flash('Kích hoạt tài khoản và cập nhật hồ sơ thành công! Chào mừng bạn đến với EduFlaw.', 'success')
    role = session.get('role', 'student')
    endpoint_map = {
        'student': 'student.student_dashboard',
        'admin': 'admin.admin_dashboard',
        'master': 'master.master_dashboard'
    }
    return redirect(url_for(endpoint_map.get(role, 'student.student_dashboard')))

@auth_bp.route('/auth/api/send-otp', methods=['POST'])
def api_send_otp():
    data = request.get_json(silent=True) or {}
    identifier = (data.get('account') or session.get('username') or '').strip()
    personal_email = (data.get('personal_email') or '').strip().lower()

    if not identifier or not personal_email:
        return jsonify({'success': False, 'message': 'Vui lòng nhập đầy đủ Tài khoản và Email cá nhân nhận mã.'}), 400

    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', personal_email):
        return jsonify({'success': False, 'message': 'Địa chỉ Email cá nhân không hợp lệ.'}), 400

    try:
        user = _resolve_user(identifier)
        # Trả cùng một phản hồi dù tài khoản/Gmail có khớp hay không để tránh dò tài khoản và Gmail cá nhân
        if (
            not user
            or not user.is_active
            or not user.personal_email
            or user.personal_email.strip().lower() != personal_email
        ):
            return jsonify({'success': True, 'message': GENERIC_OTP_SENT_MESSAGE})

        wait_sec = OtpService.resend_wait_seconds(session, user.username)
        if wait_sec > 0:
            return jsonify({'success': False, 'message': f'Vui lòng đợi {wait_sec} giây trước khi yêu cầu mã OTP mới.'}), 429

        otp_code = OtpService.create_session_otp(session, user.username, personal_email)
        sent_ok, _ = OtpService.send_otp_email(personal_email, user.username, otp_code)

        if not sent_ok:
            return jsonify({'success': False, 'message': 'Không thể gửi email lúc này. Vui lòng kiểm tra cấu hình SMTP.'}), 500

        # Không bao giờ trả mã OTP về client, kể cả ở chế độ mô phỏng
        return jsonify({'success': True, 'message': GENERIC_OTP_SENT_MESSAGE})
    except Exception:
        return jsonify({'success': False, 'message': 'Lỗi kết nối cơ sở dữ liệu.'}), 503

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        action_type = request.form.get('action_type', 'legacy')

        if action_type == 'otp_reset':
            identifier = request.form.get('account', '').strip()
            personal_email = request.form.get('personal_email', '').strip().lower()
            otp_code = request.form.get('otp_code', '').strip()
            new_password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            if new_password != confirm_password:
                flash("Mật khẩu mới và xác nhận mật khẩu không khớp.", "error")
                return redirect('/forgot-password')

            strong, strength_message = validate_password_strength(new_password)
            if not strong:
                flash(strength_message, "error")
                return redirect('/forgot-password')

            try:
                user = _resolve_user(identifier)
                if (
                    not user
                    or not user.is_active
                    or not user.personal_email
                    or user.personal_email.strip().lower() != personal_email
                ):
                    flash("Thông tin khôi phục hoặc mã OTP không chính xác.", "error")
                    return redirect('/forgot-password')

                is_valid, msg = OtpService.verify_session_otp(session, user.username, personal_email, otp_code)
                if not is_valid:
                    flash(msg, "error")
                    return redirect('/forgot-password')

                with get_db_cursor(commit=True) as cursor:
                    cursor.execute(
                        "UPDATE users SET password = %s WHERE id = %s",
                        (generate_password_hash(new_password), user.id)
                    )

                log_security_event('password_reset_otp', account=user.username)
                flash("Đổi mật khẩu bằng mã OTP thành công! Vui lòng đăng nhập lại.", "success")
                return redirect('/login')
            except Exception:
                flash("Lỗi kết nối cơ sở dữ liệu.", "error")
                return redirect('/forgot-password')

        # Chỉ hỗ trợ khôi phục bằng OTP qua Gmail cá nhân; không bao giờ trả link reset về trình duyệt
        flash("Yêu cầu không hợp lệ. Vui lòng khôi phục mật khẩu bằng mã OTP gửi về Gmail cá nhân.", "error")
        return redirect('/forgot-password')

    return render_template('auth/forgot_password.html')