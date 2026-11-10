import os
import secrets
import smtplib
import time
import hmac
import hashlib
import math
from email.message import EmailMessage
from flask import current_app
from config import Config
from app.models.security_state_model import SecurityState


class OtpService:
    OTP_EXPIRATION = 300
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN = 60          # giây chờ giữa hai lần gửi trong cùng một phiên
    MAX_SENDS_PER_WINDOW = 5      # số lần gửi tối đa cho mỗi tài khoản trong SEND_WINDOW
    SEND_WINDOW = 900

    # OTP lưu phía máy chủ trong CSDL (SecurityState) theo mã ngẫu nhiên của từng phiên (không theo username), nên:
    # - người khác yêu cầu OTP cho cùng tài khoản không ghi đè được mã của chủ tài khoản
    # - phát lại cookie session cũ không reset được số lần nhập sai
    # - nhiều worker dùng chung trạng thái và restart không làm mất OTP

    PLACEHOLDER_EMAILS = {
        'email_cua_ban@gmail.com',
        'dia_chi_gmail_bot_cua_ban@gmail.com',
        'your_email@gmail.com',
        'example@gmail.com'
    }

    @staticmethod
    def generate_otp():
        return f"{secrets.randbelow(1000000):06d}"

    @staticmethod
    def _hash_otp(username, personal_email, otp_code):
        secret = str(getattr(Config, 'SECRET_KEY', 'eduflaw-default-secret'))
        raw = f"{username.strip().lower()}|{personal_email.strip().lower()}|{str(otp_code).strip()}"
        return hmac.new(
            secret.encode('utf-8'),
            raw.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def _recent_sends(cls, clean_user, now):
        return SecurityState.recent_sends(clean_user, now - cls.SEND_WINDOW)

    @classmethod
    def resend_wait_seconds(cls, session_obj, username):
        """Số giây còn phải chờ trước khi được gửi OTP mới (giới hạn theo phiên và theo tài khoản)"""
        now = time.time()
        session_wait = session_obj.get('otp_last_sent_at', 0) + cls.RESEND_COOLDOWN - now
        recent = cls._recent_sends((username or '').strip().lower(), now)
        account_wait = recent[0] + cls.SEND_WINDOW - now if len(recent) >= cls.MAX_SENDS_PER_WINDOW else 0
        return max(0, math.ceil(max(session_wait, account_wait)))

    @classmethod
    def _discard_session_otp(cls, session_obj):
        SecurityState.delete_otp(session_obj.pop('password_otp_id', None))

    @classmethod
    def create_session_otp(cls, session_obj, username, personal_email):
        otp_code = cls.generate_otp()
        clean_user = username.strip().lower()
        clean_email = personal_email.strip().lower()
        now = time.time()

        SecurityState.purge_otp(now, cls.SEND_WINDOW)
        SecurityState.record_send(clean_user, now)
        cls._discard_session_otp(session_obj)

        otp_id = secrets.token_urlsafe(16)
        SecurityState.create_otp(
            otp_id, clean_user, clean_email,
            cls._hash_otp(clean_user, clean_email, otp_code),
            now + cls.OTP_EXPIRATION
        )
        session_obj['password_otp_id'] = otp_id
        session_obj['otp_last_sent_at'] = now
        return otp_code

    @classmethod
    def verify_session_otp(cls, session_obj, username, personal_email, candidate_otp):
        clean_user = (username or '').strip().lower()
        clean_email = (personal_email or '').strip().lower()
        clean_otp = ''.join(ch for ch in str(candidate_otp or '') if ch.isdigit())

        otp_data = SecurityState.get_otp(session_obj.get('password_otp_id'))
        if not otp_data:
            return False, "Chưa có yêu cầu mã xác nhận hoặc phiên đã hết hạn. Vui lòng bấm gửi lại mã."

        if time.time() > otp_data.get('expires_at', 0):
            cls._discard_session_otp(session_obj)
            return False, "Mã xác nhận OTP đã hết hạn (quá 5 phút). Vui lòng yêu cầu mã mới."

        if otp_data.get('attempts', 0) >= cls.MAX_ATTEMPTS:
            cls._discard_session_otp(session_obj)
            return False, "Bạn đã nhập sai quá 5 lần. Vui lòng bấm gửi lại mã OTP mới."

        if otp_data.get('personal_email') != clean_email:
            return False, "Địa chỉ Email xác thực không khớp với Email đã nhận mã OTP."

        expected_hash = cls._hash_otp(clean_user, clean_email, clean_otp)
        is_match = otp_data.get('username') == clean_user and hmac.compare_digest(otp_data.get('otp_hash', ''), expected_hash)

        if not is_match:
            # Số lần sai được đếm phía máy chủ nên không thể reset bằng cách phát lại cookie
            SecurityState.increment_otp_attempts(session_obj.get('password_otp_id'))
            remaining = max(0, cls.MAX_ATTEMPTS - (otp_data.get('attempts', 0) + 1))
            return False, f"Mã xác nhận OTP không chính xác! (Bạn còn {remaining} lần thử)"

        cls._discard_session_otp(session_obj)
        return True, "Xác thực OTP thành công."

    @classmethod
    def send_otp_email(cls, recipient_email, username, otp_code):
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com').strip()
        smtp_port = int(os.getenv('SMTP_PORT', '587').strip() or 587)
        smtp_email = os.getenv('SMTP_EMAIL', '').strip()
        raw_password = os.getenv('SMTP_PASSWORD', '').strip()
        smtp_password = ''.join(raw_password.split())

        is_placeholder = (
            not smtp_email
            or not smtp_password
            or smtp_email.lower() in cls.PLACEHOLDER_EMAILS
            or 'xxxx' in smtp_password.lower()
            or 'abcdefgh' in smtp_password.lower()
        )

        if is_placeholder:
            # Chế độ mô phỏng chỉ dùng khi chạy debug/test: OTP chỉ in ra console máy chủ (flush ngay: khi stdout không phải terminal, Python giữ dòng này trong bộ đệm)
            if current_app and (current_app.debug or current_app.testing):
                print(f"\n[EDUFLAW OTP - DEV MODE] Tài khoản: {username} | Nhận: {recipient_email} | Mã OTP: {otp_code}\n", flush=True)
                return True, True
            print("\n⚠️ [EDUFLAW OTP] Chưa cấu hình SMTP_EMAIL / SMTP_PASSWORD nên không thể gửi mã OTP.\n", flush=True)
            return False, False

        try:
            msg = EmailMessage()
            msg['Subject'] = f"[{otp_code}] Mã xác thực tài khoản EduFlaw"
            msg['From'] = f"EduFlaw Portal <{smtp_email}>"
            msg['To'] = recipient_email

            html_content = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #701a24 0%, #4a0d15 100%); color: white; padding: 24px; text-align: center;">
                    <h2 style="margin: 0; font-size: 22px;">EduFlaw Academic Portal</h2>
                    <p style="margin: 6px 0 0 0; font-size: 13px; opacity: 0.85;">Xác thực liên kết Gmail & Kích hoạt tài khoản</p>
                </div>
                <div style="padding: 28px; background: #ffffff; color: #334155;">
                    <p style="margin-top: 0;">Xin chào,</p>
                    <p>Bạn đang thực hiện xác thực địa chỉ Gmail cho tài khoản <strong>{username}</strong> trên hệ thống EduFlaw.</p>
                    <p>Mã xác thực (OTP) gồm 6 chữ số của bạn là:</p>
                    <div style="background: #f8fafc; border: 2px dashed #0ea5e9; border-radius: 10px; padding: 18px; text-align: center; margin: 22px 0;">
                        <span style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #0f172a;">{otp_code}</span>
                    </div>
                    <p style="font-size: 13px; color: #64748b; line-height: 1.6;">
                        ⏳ Mã này có hiệu lực trong vòng <strong>5 phút</strong>. Vui lòng nhập 6 chữ số này vào màn hình kích hoạt EduFlaw.
                    </p>
                </div>
            </div>
            """
            msg.set_content(f"Mã xác thực EduFlaw của tài khoản {username} là: {otp_code} (Hiệu lực 5 phút).")
            msg.add_alternative(html_content, subtype='html')

            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                    server.login(smtp_email, smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(smtp_email, smtp_password)
                    server.send_message(msg)

            print(f"\n✅ [SMTP SUCCESS] Đã gửi email OTP tới hộp thư {recipient_email}\n")
            return True, False
        except Exception as err:
            print(f"\n⚠️ [LỖI CẤU HÌNH SMTP GMAIL]: {err}")
            print("👉 Lưu ý: SMTP_PASSWORD trong file .env phải là Mật khẩu ứng dụng (App Password) 16 ký tự của Google, không phải mật khẩu đăng nhập Gmail thường.\n", flush=True)
            return False, False