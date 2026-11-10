from decimal import Decimal

import pytest

from app.services import score_recalculation_service as service

WEIGHTS = {'weight_cc': Decimal('10.00'), 'weight_bttl': Decimal('0.00'), 'weight_tbkt': Decimal('20.00'),
           'weight_tgk': Decimal('0.00'), 'weight_tnth': Decimal('0.00'), 'weight_thi': Decimal('70.00')}


def _row(grade_id, stored, cc, tbkt, thi):
    return {'id': grade_id, 'credit_class_id': 1, 'score': None if stored is None else Decimal(str(stored)),
            'score_cc': Decimal(str(cc)), 'score_bttl': None, 'score_tbkt': Decimal(str(tbkt)), 'score_tgk': None,
            'score_tnth': None, 'score_thi': Decimal(str(thi)), 'score_thi_2': None, **WEIGHTS}


# 5/5/6.5 -> 6.05: bản cũ lưu 6.0, đúng phải là 6.1; 10/8.5/9 -> 9.0 đã đúng
ROWS = [_row(11, 6.0, 5, 5, 6.5), _row(12, 9.0, 10, 8.5, 9)]


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self._results = []

    def execute(self, sql, params=()):
        sql = ' '.join(sql.split())
        self.connection.executed.append((sql, params))
        if sql.startswith('SELECT id FROM users'):
            self._results = [{'id': 99}]
        elif sql.startswith('SELECT g.id'):
            self._results = list(self.connection.rows)
        else:
            self._results = []

    def executemany(self, sql, rows):
        self.connection.batches.append((' '.join(sql.split()), list(rows)))

    def fetchall(self):
        return self._results

    def fetchone(self):
        return self._results[0] if self._results else None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []
        self.batches = []
        self.events = []

    def cursor(self, **kwargs):
        return FakeCursor(self)

    def commit(self):
        self.events.append('commit')

    def rollback(self):
        self.events.append('rollback')

    def close(self):
        self.events.append('close')


@pytest.fixture
def connection(monkeypatch):
    fake = FakeConnection(ROWS)
    monkeypatch.setattr(service.db_pool, 'get_connection', lambda: fake)
    return fake


def test_dry_run_reports_without_writing(connection):
    """Chạy thử chỉ báo cáo, không UPDATE/INSERT và không commit"""
    result = service.recalculate(apply=False)

    assert result['applied'] is False
    assert result['changed'] == 1
    assert result['examples'] == [(11, 6.0, 6.1)]
    assert not [sql for sql, _ in connection.executed if sql.startswith(('UPDATE', 'INSERT'))]
    assert connection.batches == []
    assert 'commit' not in connection.events


def test_apply_updates_only_changed_rows_and_logs_them(connection):
    """Áp dụng: khóa dòng, một câu UPDATE theo lô, nhật ký ghi tên Master và lý do, rồi commit"""
    result = service.recalculate(apply=True)

    assert result['applied'] is True and result['changed'] == 1
    assert any(sql.endswith('FOR UPDATE') for sql, _ in connection.executed)

    updates = [(sql, params) for sql, params in connection.executed if sql.startswith('UPDATE grades')]
    assert len(updates) == 1
    assert updates[0][1] == (11, 6.1, 11)

    audit_sql, audit_rows = connection.batches[0]
    assert audit_sql.startswith('INSERT INTO grade_audit_logs')
    assert audit_rows == [(11, 'Tổng kết hệ 10', 6.0, 6.1, 99, service.REASON)]
    assert connection.events[-2:] == ['commit', 'close']


def test_apply_rolls_back_on_error(connection, monkeypatch):
    """Lỗi giữa chừng thì rollback toàn bộ, không commit dở dang"""
    def broken_log(cursor, rows):
        raise RuntimeError('mất kết nối')

    monkeypatch.setattr(service.Grade, 'log_grade_changes', broken_log)
    with pytest.raises(RuntimeError):
        service.recalculate(apply=True)

    assert 'commit' not in connection.events
    assert connection.events[-2:] == ['rollback', 'close']
