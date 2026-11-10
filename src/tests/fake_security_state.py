import time


class FakeSecurityState:
    """Bản thay thế SecurityState lưu trong bộ nhớ, để test không cần CSDL"""

    def __init__(self):
        self.logins = {}
        self.otps = {}
        self.sends = []

    def lockout_until(self, key):
        return self.logins.get(key, {}).get('lockout_until', 0.0)

    def register_failure(self, key, max_attempts, lockout_seconds):
        row = self.logins.setdefault(key, {'attempts': 0, 'lockout_until': 0.0})
        row['attempts'] += 1
        if row['attempts'] >= max_attempts:
            row['attempts'] = 0
            row['lockout_until'] = time.time() + lockout_seconds
            return True
        return False

    def clear_failures(self, *keys):
        for key in keys:
            self.logins.pop(key, None)

    def purge_login_attempts(self):
        pass

    def create_otp(self, otp_id, username, personal_email, otp_hash, expires_at):
        self.otps[otp_id] = {'username': username, 'personal_email': personal_email,
                             'otp_hash': otp_hash, 'expires_at': expires_at, 'attempts': 0}

    def get_otp(self, otp_id):
        record = self.otps.get(otp_id) if otp_id else None
        return dict(record) if record else None

    def increment_otp_attempts(self, otp_id):
        if otp_id in self.otps:
            self.otps[otp_id]['attempts'] += 1

    def delete_otp(self, otp_id):
        self.otps.pop(otp_id, None)

    def record_send(self, username, sent_at):
        self.sends.append((username, sent_at))

    def recent_sends(self, username, since):
        return sorted(sent_at for name, sent_at in self.sends if name == username and sent_at >= since)

    def purge_otp(self, now, send_window):
        for otp_id in [key for key, record in self.otps.items() if record['expires_at'] < now]:
            self.otps.pop(otp_id, None)
        self.sends = [item for item in self.sends if item[1] >= now - send_window]
