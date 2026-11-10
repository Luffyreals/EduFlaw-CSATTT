"""
Tính lại điểm tổng kết (grades.score) đã lưu theo quy tắc làm tròn hiện tại của Grade.calculate_final_score.

Phiên bản cũ làm tròn bằng round() trên số thực (6.05 -> 6.0), nên một phần điểm đã lưu thấp hơn 0.1.
Mặc định chỉ chạy thử (không ghi gì); thêm --apply để cập nhật trong MỘT transaction và ghi nhật ký
grade_audit_logs cho từng dòng thay đổi.

    python -m app.services.score_recalculation_service            # chạy thử, in thống kê
    python -m app.services.score_recalculation_service --apply    # áp dụng
"""
import argparse
from collections import Counter

from app.models.grade_model import Grade
from db import db_pool

REASON = 'Hệ thống hiệu chỉnh làm tròn điểm tổng kết (làm tròn 5 lên, thay cho round() số thực)'
SCORE_FIELD_NAME = Grade.AUDIT_FIELD_NAMES['score']
BATCH_SIZE = 500

GRADE_ROW_SELECT = """
    SELECT g.id, g.credit_class_id, g.score,
           g.score_cc, g.score_bttl, g.score_tbkt, g.score_tgk, g.score_tnth, g.score_thi, g.score_thi_2,
           c.weight_cc, c.weight_bttl, c.weight_tbkt, c.weight_tgk, c.weight_tnth, c.weight_thi
    FROM grades g
    JOIN credit_classes c ON c.id = g.credit_class_id
"""


def find_score_changes(rows):
    """Trả về danh sách (grade_id, điểm cũ, điểm mới) cho các dòng có điểm đã lưu khác điểm tính lại"""
    changes = []
    for row in rows:
        new_score = Grade.calculate_final_score(row, row)
        old_score = row['score']
        if Grade._score_changed(old_score, new_score):
            changes.append((row['id'], None if old_score is None else float(old_score), new_score))
    return changes


def summarize(changes):
    letter_changes = sum(
        1 for _, old, new in changes
        if old is not None and new is not None
        and Grade.convert_score(old)['letter'] != Grade.convert_score(new)['letter']
    )
    deltas = Counter(round(new - old, 1) for _, old, new in changes if old is not None and new is not None)
    return {'changed': len(changes), 'letter_changes': letter_changes, 'deltas': dict(deltas)}


def _update_scores(cursor, changes):
    """Cập nhật theo lô bằng UPDATE ... CASE id (mỗi câu lệnh tới CSDL ở xa tốn một vòng mạng)"""
    for start in range(0, len(changes), BATCH_SIZE):
        batch = changes[start:start + BATCH_SIZE]
        cases = ' '.join(['WHEN %s THEN %s'] * len(batch))
        params = [value for grade_id, _, new in batch for value in (grade_id, new)]
        ids = [grade_id for grade_id, _, _ in batch]
        cursor.execute(
            f"UPDATE grades SET score = CASE id {cases} END WHERE id IN ({', '.join(['%s'] * len(ids))})",
            (*params, *ids)
        )


def recalculate(apply=False, modified_by_username=None):
    """
    Chạy thử (apply=False) hoặc áp dụng. Khi áp dụng: khóa các dòng cần sửa (SELECT ... FOR UPDATE),
    tính lại trên dữ liệu đã khóa, cập nhật và ghi nhật ký trong cùng một transaction.
    """
    connection = db_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(GRADE_ROW_SELECT + " WHERE g.score_thi IS NOT NULL OR g.score_thi_2 IS NOT NULL OR g.score IS NOT NULL")
        changes = find_score_changes(cursor.fetchall())
        result = {'applied': False, **summarize(changes), 'examples': changes[:5]}
        if not apply or not changes:
            connection.rollback()
            return result

        if modified_by_username:
            cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'master'", (modified_by_username,))
        else:
            cursor.execute("SELECT id FROM users WHERE role = 'master' ORDER BY id LIMIT 1")
        master = cursor.fetchone()
        if not master:
            raise RuntimeError('Không tìm thấy tài khoản Master để ghi nhật ký hiệu chỉnh.')

        # Khóa và tính lại trên dữ liệu mới nhất: dòng nào đã được giảng viên sửa trong lúc chạy sẽ tự được tính đúng
        candidate_ids = [grade_id for grade_id, _, _ in changes]
        locked_rows = []
        for start in range(0, len(candidate_ids), BATCH_SIZE):
            batch_ids = candidate_ids[start:start + BATCH_SIZE]
            cursor.execute(
                GRADE_ROW_SELECT + f" WHERE g.id IN ({', '.join(['%s'] * len(batch_ids))}) FOR UPDATE",
                tuple(batch_ids)
            )
            locked_rows.extend(cursor.fetchall())
        changes = find_score_changes(locked_rows)

        _update_scores(cursor, changes)
        Grade.log_grade_changes(cursor, [
            (grade_id, SCORE_FIELD_NAME, old, new, master['id'], REASON) for grade_id, old, new in changes
        ])
        connection.commit()
        return {'applied': True, **summarize(changes), 'examples': changes[:5]}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tính lại điểm tổng kết đã lưu theo quy tắc làm tròn hiện tại.')
    parser.add_argument('--apply', action='store_true', help='Ghi thay đổi vào CSDL (mặc định chỉ chạy thử).')
    parser.add_argument('--modified-by', help='Username Master ghi vào nhật ký (mặc định: Master đầu tiên).')
    arguments = parser.parse_args()

    outcome = recalculate(apply=arguments.apply, modified_by_username=arguments.modified_by)
    mode = 'ĐÃ ÁP DỤNG' if outcome['applied'] else 'CHẠY THỬ (chưa ghi gì)'
    print(f"[{mode}] Số điểm tổng kết thay đổi: {outcome['changed']} | đổi điểm chữ: {outcome['letter_changes']}")
    print(f"Mức chênh lệch: {outcome['deltas']}")
    print(f"Ví dụ (grade_id, cũ, mới): {outcome['examples']}")
