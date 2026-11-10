# app/utils/error_pages.py
from flask import jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException, InternalServerError

ERROR_MESSAGES = {
    400: ('Yêu cầu không hợp lệ', 'Dữ liệu gửi lên không hợp lệ. Vui lòng kiểm tra lại và thử lần nữa.'),
    403: ('Không có quyền truy cập', 'Bạn không có quyền truy cập chức năng hoặc dữ liệu này.'),
    404: ('Không tìm thấy trang', 'Trang bạn tìm không tồn tại hoặc đã được chuyển đi.'),
    405: ('Thao tác không được hỗ trợ', 'Phương thức truy cập này không được hỗ trợ cho trang hiện tại.'),
    413: ('Tệp quá lớn', 'Tệp tải lên vượt quá dung lượng cho phép (tối đa 16 MB).'),
    429: ('Thao tác quá nhanh', 'Bạn đã thực hiện quá nhiều yêu cầu. Vui lòng đợi một lát rồi thử lại.'),
    500: ('Hệ thống gặp sự cố', 'Đã có lỗi xảy ra phía máy chủ. Vui lòng thử lại sau ít phút.'),
}
CSRF_MESSAGE = ('Phiên làm việc đã hết hạn',
                'Biểu mẫu đã hết hạn hoặc không hợp lệ. Vui lòng tải lại trang rồi thực hiện lại thao tác.')


def _wants_json():
    # Các endpoint AJAX của ứng dụng đều nằm dưới /api/ và được gọi bằng fetch, mong nhận JSON
    return '/api/' in request.path


def _error_response(code, title, message):
    if _wants_json():
        return jsonify({'success': False, 'message': message}), code
    return render_template('errors/error.html', code=code, title=title, message=message), code


def register_error_handlers(app):
    """Trang lỗi tiếng Việt thống nhất (và JSON cho các endpoint /api/) thay cho trang mặc định tiếng Anh"""

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return _error_response(400, *CSRF_MESSAGE)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if error.code not in ERROR_MESSAGES:
            return error
        return _error_response(error.code, *ERROR_MESSAGES[error.code])

    @app.errorhandler(InternalServerError)
    def handle_internal_error(error):
        # Chi tiết lỗi chỉ ghi log phía máy chủ, không hiển thị cho người dùng
        app.logger.exception('Lỗi máy chủ khi xử lý %s %s', request.method, request.path)
        return _error_response(500, *ERROR_MESSAGES[500])
