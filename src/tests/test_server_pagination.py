from contextlib import contextmanager

import pytest

from app.models import grade_model, staff_model
from app.models.grade_model import Grade
from app.models.staff_model import StaffProfile


def _login_as(client, user_id, username, role):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['force_password_change'] = False


def _login_master(client):
    _login_as(client, 1, 'master@eduflaw.com', 'master')


def _credit_class(class_id, **overrides):
    row = {
        'id': class_id, 'class_code': f'CN{class_id:03d}-2025-S2-01', 'subject_name': f'Môn {class_id}',
        'credits': 3, 'semester': 2, 'year': 2025, 'day_of_week': 3, 'shift': '1-2', 'room': 'A2-101',
        'weight_cc': 10, 'weight_bttl': 0, 'weight_tbkt': 20, 'weight_tgk': 0, 'weight_tnth': 0, 'weight_thi': 70,
        'lecturer_name': 'Nguyễn Văn A', 'lecturer_email': 'gv_a@eduflaw.com',
    }
    row.update(overrides)
    return row


def _admin(user_id, **overrides):
    row = {
        'user_id': user_id, 'email': f'gv{user_id}@eduflaw.com', 'is_active': 1, 'full_name': f'Giảng viên {user_id}',
        'id_card': '', 'phone_number': '0900000000', 'date_of_birth': '', 'gender': 'Nam', 'address': '',
    }
    row.update(overrides)
    return row


@pytest.fixture
def grade_search(monkeypatch):
    """Giả lập truy vấn phân trang lớp tín chỉ và ghi lại tham số controller truyền xuống"""
    calls = []
    result = {'rows': [_credit_class(1), _credit_class(2)], 'total': 120, 'page': None}

    def fake_search(keyword='', prefixes=(), semester=None, year=None, page=1, per_page=25):
        calls.append({'keyword': keyword, 'prefixes': list(prefixes), 'semester': semester,
                      'year': year, 'page': page, 'per_page': per_page})
        return result['rows'], result['total'], result['page'] or page

    monkeypatch.setattr(Grade, 'search_credit_classes', staticmethod(fake_search))
    monkeypatch.setattr(StaffProfile, 'get_admin_options', staticmethod(lambda: [
        {'email': 'gv_a@eduflaw.com', 'full_name': 'Nguyễn Văn A'},
        {'email': 'gv_b@eduflaw.com', 'full_name': None},
    ]))
    return calls, result


@pytest.fixture
def admin_search(monkeypatch):
    calls = []
    result = {'rows': [_admin(41), _admin(42, is_active=0)], 'total': 259, 'page': None}

    def fake_search(keyword='', status=None, page=1, per_page=20):
        calls.append({'keyword': keyword, 'status': status, 'page': page, 'per_page': per_page})
        return result['rows'], result['total'], result['page'] or page

    monkeypatch.setattr(StaffProfile, 'search_admins', staticmethod(fake_search))
    return calls, result


# ---------- /master/grades ----------

def test_manage_grades_passes_filters_to_server_side_query(client, grade_search):
    """Tìm kiếm, bộ lọc và phân trang được gửi xuống truy vấn thay vì lọc bằng JS"""
    calls, _ = grade_search
    _login_master(client)

    response = client.get('/master/grades?q=+Lập trình+&prefix=BAS,CS&semester=2&year=2025&page=3&per_page=50')

    assert response.status_code == 200
    assert calls == [{'keyword': 'Lập trình', 'prefixes': ['BAS', 'CS'], 'semester': 2,
                      'year': 2025, 'page': 3, 'per_page': 50}]
    html = response.get_data(as_text=True)
    assert 'Tổng: 120 lớp' in html
    assert 'Hiển thị <strong>101 – 102</strong>' in html
    # Link phân trang giữ nguyên bộ lọc
    assert 'page=2' in html
    assert 'prefix=BAS,CS' in html
    assert 'per_page=50' in html
    # Không còn phân trang/lọc phía trình duyệt
    assert 'filterClasses' not in html
    assert 'Hiện tất cả' not in html


def test_manage_grades_rejects_invalid_paging_and_filter_values(client, grade_search):
    """per_page ngoài danh sách cho phép, khối ngành lạ hoặc học kỳ sai đều bị bỏ qua"""
    calls, _ = grade_search
    _login_master(client)

    response = client.get('/master/grades?per_page=999999&prefix=X%25&semester=9&page=-3&year=abc')

    assert response.status_code == 200
    assert calls == [{'keyword': '', 'prefixes': [], 'semester': None, 'year': None, 'page': 1, 'per_page': 25}]


def test_manage_grades_renders_lecturer_dropdown_once(client, grade_search):
    """Dropdown chọn giảng viên chỉ render một lần cho cả trang, không lặp theo từng dòng"""
    _, result = grade_search
    result['rows'] = [_credit_class(i) for i in range(1, 26)]
    _login_master(client)

    html = client.get('/master/grades').get_data(as_text=True)

    assert html.count('<option value="gv_a@eduflaw.com">') == 1
    assert html.count('<option value="gv_b@eduflaw.com">') == 1
    assert html.count('name="lecturer_email"') == 1
    assert html.count('class="dropdown-btn"') == 25


def test_manage_grades_escapes_class_data_and_search_term(client, grade_search):
    """Dữ liệu lớp và từ khóa tìm kiếm được escape, hành động từng dòng đọc từ data-*"""
    _, result = grade_search
    result['rows'] = [_credit_class(7, subject_name='<script>alert(1)</script>', class_code="X'onmouseover=alert(1)")]
    _login_master(client)

    html = client.get('/master/grades', query_string={'q': '"><script>alert(2)</script>'}).get_data(as_text=True)

    assert '<script>alert(1)</script>' not in html
    assert '<script>alert(2)</script>' not in html
    assert 'value="&#34;&gt;&lt;script&gt;alert(2)&lt;/script&gt;"' in html
    assert 'data-subject="&lt;script&gt;alert(1)&lt;/script&gt;"' in html


def test_manage_grades_empty_result_shows_message(client, grade_search):
    _, result = grade_search
    result['rows'], result['total'] = [], 0
    _login_master(client)

    html = client.get('/master/grades?q=khongco').get_data(as_text=True)

    assert 'Không tìm thấy lớp tín chỉ nào khớp với bộ lọc.' in html
    assert 'Tổng: 0 lớp' in html


def test_manage_grades_detail_loads_single_class(client, monkeypatch):
    """Trang chi tiết chỉ truy vấn đúng một lớp, không tải toàn bộ danh sách lớp hay giảng viên"""
    requested = []
    monkeypatch.setattr(Grade, 'get_credit_class', staticmethod(lambda cid: requested.append(cid) or _credit_class(5)))
    monkeypatch.setattr(Grade, 'get_students_in_credit_class', staticmethod(lambda cid: []))

    def fail(*args, **kwargs):
        raise AssertionError('Không được tải danh sách đầy đủ ở trang chi tiết')

    monkeypatch.setattr(Grade, 'search_credit_classes', staticmethod(fail))
    monkeypatch.setattr(StaffProfile, 'get_admin_options', staticmethod(fail))
    _login_master(client)

    response = client.get('/master/grades?credit_class_id=5')

    assert response.status_code == 200
    assert requested == ['5']
    assert 'Môn 5' in response.get_data(as_text=True)


def test_manage_grades_detail_returns_404_for_unknown_class(client, monkeypatch):
    monkeypatch.setattr(Grade, 'get_credit_class', staticmethod(lambda cid: None))
    _login_master(client)

    assert client.get('/master/grades?credit_class_id=999').status_code == 404
    assert client.get('/master/grades/export?credit_class_id=999').status_code == 404


def test_credit_class_actions_return_to_current_page(client, monkeypatch):
    """Sau khi xoá/sửa lớp, Master quay lại đúng trang và bộ lọc đang xem"""
    monkeypatch.setattr(Grade, 'delete_credit_class', staticmethod(lambda cid: (True, 'Đã xoá lớp.')))
    _login_master(client)

    response = client.post(
        '/master/grades/class/delete', data={'class_id': '3'},
        headers={'Referer': 'http://localhost/master/grades?q=web&page=4'}
    )

    assert response.status_code == 302
    assert response.headers['Location'] == '/master/grades?q=web&page=4'


# ---------- /master/admins ----------

def test_manage_admins_passes_filters_to_server_side_query(client, admin_search):
    calls, _ = admin_search
    _login_master(client)

    response = client.get('/master/admins?q=0912&status=0&page=2&per_page=50')

    assert response.status_code == 200
    assert calls == [{'keyword': '0912', 'status': 0, 'page': 2, 'per_page': 50}]
    html = response.get_data(as_text=True)
    assert 'Tổng: 259 GV' in html
    assert 'Hiển thị <strong>51 – 52</strong>' in html
    # STT tiếp nối theo trang, link phân trang giữ trạng thái "Đã khóa" (status=0)
    assert '>51</td>' in html
    assert 'status=0' in html and 'page=3' in html
    assert 'filterAdmins' not in html


def test_manage_admins_rejects_invalid_paging_values(client, admin_search):
    calls, _ = admin_search
    _login_master(client)

    response = client.get('/master/admins?status=7&per_page=100000&page=0')

    assert response.status_code == 200
    assert calls == [{'keyword': '', 'status': None, 'page': 1, 'per_page': 20}]


def test_manage_admins_keeps_row_actions_via_data_attributes(client, admin_search):
    """Các nút sửa, cấp lại mật khẩu, khoá/mở khoá vẫn có trên từng dòng và đọc dữ liệu qua data-*"""
    _, result = admin_search
    result['rows'] = [_admin(9, full_name="</div><script>alert(1)</script>", email="x'@eduflaw.com")]
    _login_master(client)

    html = client.get('/master/admins').get_data(as_text=True)

    assert '<script>alert(1)</script>' not in html
    assert 'onclick="openAdminModalFromButton(this)"' in html
    assert 'confirmResetPassword(this.dataset.userId, this.dataset.email)' in html
    assert 'confirmToggleStatus(this.dataset.userId, this.dataset.email, 0)' in html
    assert 'data-email="x&#39;@eduflaw.com"' in html


def test_admin_update_returns_to_current_page(client, monkeypatch):
    monkeypatch.setattr(StaffProfile, 'update_admin_profile_by_master', staticmethod(lambda *args: True))
    _login_master(client)

    response = client.post(
        '/master/admins/update', data={'user_id': '9', 'full_name': 'A'},
        headers={'Referer': 'http://localhost/master/admins?status=1&page=3'}
    )

    assert response.headers['Location'] == '/master/admins?status=1&page=3'


# ---------- Truy vấn SQL ----------

class _RecordingCursor:
    def __init__(self, total):
        self.queries = []
        self._total = total

    def execute(self, sql, params=None):
        self.queries.append((' '.join(sql.split()), params))

    def fetchone(self):
        return {'total': self._total}

    def fetchall(self):
        return []


def _patch_cursor(monkeypatch, module, cursor):
    @contextmanager
    def fake_get_db_cursor(*args, **kwargs):
        yield cursor

    monkeypatch.setattr(module, 'get_db_cursor', fake_get_db_cursor)


def test_search_credit_classes_uses_limit_offset_and_escaped_like(monkeypatch):
    cursor = _RecordingCursor(total=120)
    _patch_cursor(monkeypatch, grade_model, cursor)

    rows, total, page = Grade.search_credit_classes('50%_off', ['BAS', 'CS'], 2, 2025, page=3, per_page=50)

    assert (rows, total, page) == ([], 120, 3)
    (count_sql, count_params), (select_sql, select_params) = cursor.queries
    assert count_sql.startswith('SELECT COUNT(*)')
    assert count_params == ('%50\\%\\_off%',) * 4 + ('BAS%', 'CS%', 2, 2025)
    assert select_sql.endswith('LIMIT %s OFFSET %s')
    assert select_params == count_params + (50, 100)


def test_search_credit_classes_clamps_page_past_the_end(monkeypatch):
    """Trang vượt quá tổng số trang (ví dụ sau khi xoá dòng cuối) hiển thị trang cuối"""
    cursor = _RecordingCursor(total=51)
    _patch_cursor(monkeypatch, grade_model, cursor)

    _, _, page = Grade.search_credit_classes(page=99, per_page=25)

    assert page == 3
    assert cursor.queries[1][1] == (25, 50)
    assert 'WHERE' not in cursor.queries[1][0]


def test_search_admins_filters_role_status_and_paginates(monkeypatch):
    cursor = _RecordingCursor(total=259)
    _patch_cursor(monkeypatch, staff_model, cursor)

    rows, total, page = StaffProfile.search_admins('An', 0, page=2, per_page=20)

    assert (rows, total, page) == ([], 259, 2)
    (count_sql, count_params), (select_sql, select_params) = cursor.queries
    assert "u.role = 'admin'" in count_sql and 'u.is_active = %s' in count_sql
    assert count_params == ('%An%', '%An%', '%An%', 0)
    assert select_sql.endswith('ORDER BY u.id ASC LIMIT %s OFFSET %s')
    assert select_params == count_params + (20, 20)
