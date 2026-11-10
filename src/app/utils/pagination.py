# app/utils/pagination.py
import math
from flask import request

MAX_SEARCH_LENGTH = 100


def escape_like(value):
    """Escape ký tự đại diện của LIKE (\\, %, _) để từ khóa tìm kiếm được so khớp nguyên văn"""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def get_page_args(allowed_per_page, default_per_page):
    """
    Đọc page, per_page, q từ query string. per_page chỉ nhận các giá trị trong `allowed_per_page`
    để client không yêu cầu được cả bảng trong một trang.
    """
    page = request.args.get('page', 1, type=int) or 1
    per_page = request.args.get('per_page', default_per_page, type=int)
    if per_page not in allowed_per_page:
        per_page = default_per_page
    q = (request.args.get('q') or '').strip()[:MAX_SEARCH_LENGTH]
    return max(page, 1), per_page, q


def clamp_page(page, per_page, total):
    """Đưa số trang về khoảng hợp lệ [1, tổng số trang] để trang vượt quá vẫn hiện trang cuối"""
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    return min(max(page, 1), total_pages)
