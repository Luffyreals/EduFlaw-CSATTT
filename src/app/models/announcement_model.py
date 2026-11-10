from app.utils.db_helper import get_db_cursor

class Announcement:
    @classmethod
    def get_announcements_for_student(cls, class_name):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT a.*, COALESCE(ap.full_name, mp.full_name, 'Hệ thống') as author_name
                    FROM announcements a
                    LEFT JOIN admin_profiles ap ON a.created_by = ap.user_id
                    LEFT JOIN master_profiles mp ON a.created_by = mp.user_id
                    WHERE a.target_class IS NULL OR a.target_class = %s
                    ORDER BY a.created_at DESC
                    LIMIT 10
                """
                cursor.execute(sql, (class_name,))
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def create_announcement(cls, title, content, target_class, created_by):
        try:
            with get_db_cursor(commit=True) as cursor:
                sql = "INSERT INTO announcements (title, content, target_class, created_by) VALUES (%s, %s, %s, %s)"
                target = target_class if target_class and target_class.strip() else None
                cursor.execute(sql, (title, content, target, created_by))
                return True
        except Exception:
            return False

    @classmethod
    def get_all_announcements(cls):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT a.*, COALESCE(ap.full_name, mp.full_name, 'Hệ thống') as author_name
                    FROM announcements a
                    LEFT JOIN admin_profiles ap ON a.created_by = ap.user_id
                    LEFT JOIN master_profiles mp ON a.created_by = mp.user_id
                    ORDER BY a.created_at DESC
                """
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception:
            return []

    @classmethod
    def get_announcements_by_author(cls, user_id):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT a.*, COALESCE(ap.full_name, mp.full_name, 'Hệ thống') as author_name
                    FROM announcements a
                    LEFT JOIN admin_profiles ap ON a.created_by = ap.user_id
                    LEFT JOIN master_profiles mp ON a.created_by = mp.user_id
                    WHERE a.created_by = %s
                    ORDER BY a.created_at DESC
                """
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        except Exception:
            return []
            
    @classmethod
    def delete_announcement(cls, ann_id):
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("DELETE FROM announcements WHERE id = %s", (ann_id,))
                return cursor.rowcount > 0
        except Exception:
            return False