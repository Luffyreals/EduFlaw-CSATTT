from contextlib import contextmanager
from decimal import Decimal

from app.models import grade_model
from app.models.grade_model import Grade

WEIGHTS = {'weight_cc': 10, 'weight_bttl': 0, 'weight_tbkt': 20, 'weight_tgk': 0, 'weight_tnth': 0, 'weight_thi': 70}
EMPTY_SCORES = {column: None for column in Grade.SCORE_COLUMNS}


class RecordingCursor:
    def __init__(self, old_grades):
        self.old_grades = old_grades
        self.executed = []
        self.batches = []

    def execute(self, sql, params=()):
        self.executed.append((' '.join(sql.split()), params))

    def executemany(self, sql, rows):
        self.batches.append((' '.join(sql.split()), list(rows)))

    def fetchone(self):
        return WEIGHTS

    def fetchall(self):
        return self.old_grades


def _patch_cursor(monkeypatch, cursor):
    @contextmanager
    def fake_get_db_cursor(dictionary=False, commit=False):
        yield cursor

    monkeypatch.setattr(grade_model, 'get_db_cursor', fake_get_db_cursor)


def _scores(cc=None, tbkt=None, thi=None):
    return {'score_cc': cc, 'score_bttl': None, 'score_tbkt': tbkt, 'score_tgk': None,
            'score_tnth': None, 'score_thi': thi, 'score_thi_2': None}


def test_saving_class_grades_uses_one_update_and_one_audit_insert(monkeypatch):
    """Lưu điểm cả lớp: một câu UPDATE (CASE theo id) và một lần INSERT nhật ký, không phải mỗi sinh viên một câu"""
    old_grades = [{'id': grade_id, **EMPTY_SCORES} for grade_id in (11, 12, 13)]
    cursor = RecordingCursor(old_grades)
    _patch_cursor(monkeypatch, cursor)

    grades_data = {'11': _scores(10, 8.5, 9), '12': _scores(5, 5, 5), '13': _scores(7, 7, 7)}
    assert Grade.update_detailed_grades(90001, grades_data, user_id=2, reason='Nhập điểm') is True

    updates = [sql for sql, _ in cursor.executed if sql.startswith('UPDATE grades')]
    assert len(updates) == 1
    assert 'CASE id WHEN %s THEN %s' in updates[0]

    update_params = [params for sql, params in cursor.executed if sql.startswith('UPDATE grades')][0]
    assert update_params[-4:] == (90001, 11, 12, 13)

    assert len(cursor.batches) == 1
    audit_sql, audit_rows = cursor.batches[0]
    assert audit_sql.startswith('INSERT INTO grade_audit_logs')
    # Mỗi sinh viên: 3 đầu điểm + điểm tổng kết thay đổi từ NULL
    assert len(audit_rows) == 12
    assert (11, 'Tổng kết hệ 10', None, 9.0, 2, 'Nhập điểm') in audit_rows


def test_unchanged_rows_are_not_rewritten_or_logged(monkeypatch):
    """Dòng không đổi điểm thì không UPDATE và không ghi nhật ký"""
    unchanged = {'id': 21, **EMPTY_SCORES, 'score_cc': Decimal('10.0'), 'score_tbkt': Decimal('8.5'),
                 'score_thi': Decimal('9.0'), 'score': Decimal('9.0')}
    cursor = RecordingCursor([unchanged])
    _patch_cursor(monkeypatch, cursor)

    assert Grade.update_detailed_grades(90001, {'21': _scores(10, 8.5, 9)}, user_id=2) is True
    assert not [sql for sql, _ in cursor.executed if sql.startswith('UPDATE')]
    assert cursor.batches == []


def test_grade_from_another_class_is_rejected(monkeypatch):
    """grade_id không thuộc lớp tín chỉ đang sửa thì từ chối toàn bộ, không ghi gì"""
    cursor = RecordingCursor([{'id': 31, **EMPTY_SCORES}])
    _patch_cursor(monkeypatch, cursor)

    assert Grade.update_detailed_grades(90001, {'31': _scores(5), '999': _scores(5)}, user_id=2) is False
    assert not [sql for sql, _ in cursor.executed if sql.startswith('UPDATE')]
    assert cursor.batches == []


def test_auto_save_merges_with_latest_row_and_locks_it(monkeypatch):
    """Auto-save một ô: giữ các đầu điểm khác theo CSDL (có thể vừa được ô khác lưu), khóa dòng bằng FOR UPDATE"""
    latest = {'id': 41, **EMPTY_SCORES, 'score_cc': Decimal('8.5'), 'score_tbkt': Decimal('7.0')}
    cursor = RecordingCursor([latest])
    _patch_cursor(monkeypatch, cursor)

    saved = Grade.save_single_score(41, 90001, 'score_thi', 6.5, user_id=2, reason='Lưu tự động (Auto-save)')

    assert saved['score_cc'] == 8.5 and saved['score_tbkt'] == 7.0 and saved['score_thi'] == 6.5
    assert saved['score'] == 6.8
    select_sql = [sql for sql, _ in cursor.executed if sql.startswith('SELECT id, score_cc')][0]
    assert select_sql.endswith('FOR UPDATE')
    # Chỉ ô vừa sửa và điểm tổng kết được ghi nhật ký
    _, audit_rows = cursor.batches[0]
    assert {row[1] for row in audit_rows} == {'Thi lần 1', 'Tổng kết hệ 10'}


def test_auto_save_rejects_unknown_column(monkeypatch):
    cursor = RecordingCursor([{'id': 42, **EMPTY_SCORES}])
    _patch_cursor(monkeypatch, cursor)

    assert Grade.save_single_score(42, 90001, 'score', 10, user_id=2) is None
    assert cursor.executed == []


def test_editing_credit_class_syncs_grades_and_recomputes_scores(monkeypatch):
    """Sửa lớp tín chỉ: bảng điểm nhận tên môn/tín chỉ/học kỳ mới, điểm tổng kết tính lại theo trọng số mới, có nhật ký"""
    row = {'id': 51, **EMPTY_SCORES, 'score_cc': Decimal('10'), 'score_tbkt': Decimal('8'),
           'score_thi': Decimal('6'), 'score': Decimal('6.8')}
    cursor = RecordingCursor([row])
    _patch_cursor(monkeypatch, cursor)

    weights = {'cc': 10, 'bttl': 0, 'tbkt': 30, 'tgk': 0, 'tnth': 0, 'thi': 60}
    success, message = Grade.update_credit_class(90001, 'INT1306', 'Môn mới', 4, 2, 2026, weights, user_id=1)

    assert success is True and '1 sinh viên' in message
    sync = [params for sql, params in cursor.executed if sql.startswith('UPDATE grades SET subject')]
    assert sync == [('Môn mới', 4, 2, 2026, 90001)]
    recompute = [params for sql, params in cursor.executed if sql.startswith('UPDATE grades SET score = CASE')][0]
    # 10*10% + 8*30% + 6*60% = 7.0
    assert recompute[:2] == (51, 7.0)
    assert cursor.batches[0][1] == [(51, 'Tổng kết hệ 10', 6.8, 7.0, 1, 'Master đổi trọng số điểm của lớp tín chỉ')]


def test_editing_credit_class_without_weight_change_does_not_rewrite_scores(monkeypatch):
    row = {'id': 52, **EMPTY_SCORES, 'score_cc': Decimal('10'), 'score_tbkt': Decimal('8'),
           'score_thi': Decimal('6'), 'score': Decimal('6.8')}
    cursor = RecordingCursor([row])
    _patch_cursor(monkeypatch, cursor)

    weights = {'cc': 10, 'bttl': 0, 'tbkt': 20, 'tgk': 0, 'tnth': 0, 'thi': 70}
    success, _ = Grade.update_credit_class(90001, 'INT1306', 'Môn cũ', 3, 1, 2026, weights, user_id=1)

    assert success is True
    assert not [sql for sql, _ in cursor.executed if sql.startswith('UPDATE grades SET score')]
    assert cursor.batches == []
