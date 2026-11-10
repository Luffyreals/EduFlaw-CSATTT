# EduFlaw Lab Demo — hướng dẫn buổi thuyết trình

- **Slide:** https://canva.link/bntwb18xbi8e0g3 (25 slide, bản gốc: `EduFlaw-OWASP2025.pptx`)
- **Trang demo online:** https://claude.ai/artifact/XCSEMHpM127x3BzVPKkGbq (riêng tư — chủ tài khoản bật Share mới xem được)
- **Trang demo offline:** nhấp đúp `demo/index.html`. Không cần mạng, không cần cài gì.
- **Lời dẫn từng slide:** [`NOI-DUNG-THUYET-TRINH.md`](../NOI-DUNG-THUYET-TRINH.md)

> Trang demo là **mô phỏng** bằng JavaScript: không gọi máy chủ, không có CSDL, mọi dữ liệu đều giả.

## Các phần của buổi thuyết trình

| Phần | Slide | Người trình bày | Demo |
|---|---|---|---|
| Mở đầu, giới thiệu EduFlaw | 1 – 4 | Tùng | — |
| Vai trò & phân quyền, phương pháp kiểm thử | 5 – 10 | Đức | — |
| Fuzzing, bằng chứng, các cách tấn công | 11 – 17 | Tú | — |
| Phòng thủ: ví dụ A01 IDOR | 20 | Tú | Tab **A01** |
| Phòng thủ: ví dụ A03 chuỗi cung ứng | 21 | Khang | Tab **A03** |
| Phòng thủ: ví dụ A07 & A10 | 22 | Tú (A07), Khang (A10) | Tab **A07**, **A10** |
| Bảng tổng hợp | 23 | Khang | Tab **Tổng kết** |
| Kết quả, bài học, cảm ơn | 24 – 25 | Khang | — |

## Trước giờ thuyết trình

1. Mở trang demo, bấm **Chế độ trình chiếu** (hoặc phím `P`). Trang nhớ chế độ này cho lần mở sau.
2. Bấm `F` để toàn màn hình. Để sẵn tab trình duyệt này cạnh slide.
3. Chạy thử mỗi bài một lần, rồi bấm `R` để xóa kết quả.

## Demo từng bài (luôn chạy bản lỗi trước, bản vá sau)

| Bài | Bản lỗi (`V`) | Chuyển bản vá (`S`) |
|---|---|---|
| **A01** | Chọn `B24DCAT002`, bấm `Enter` → đọc được điểm và CCCD người khác | Request tự gửi lại → chỉ thấy dữ liệu của mình |
| **A03** | Bấm `Enter` (Đăng nhập) → máy chủ kẻ tấn công nhận được mật khẩu | Trình duyệt so SHA-256 → không khớp → chặn file |
| **A07** | Bấm `Enter` → thử 12 mật khẩu, đoán trúng ở lần 12 | Tự chạy lại → lần sai thứ 5 kích hoạt khóa, sau đó trả 429 |
| **A10** | Bấm `Enter` → lộ stack trace; tài khoản đã khóa vẫn vào được | Tự chạy lại → trả 400 câu chung; CSDL lỗi thì hủy phiên |

Kết thúc ở tab **Tổng kết** (phím `5`): cột "Đã demo" đánh dấu các chế độ vừa chạy.

## Phím tắt

| Phím | Tác dụng |
|---|---|
| `1` – `5` | Mở A01, A03, A07, A10, Tổng kết (`←` `→` để chuyển bài) |
| `V` / `S` | Có lỗ hổng / Đã vá — thao tác vừa làm tự chạy lại |
| `Enter` | Chạy thao tác chính của bài |
| `D` | Bật/tắt sự cố: CDN bị chiếm (A03), CSDL gặp sự cố (A10) |
| `R` | Làm lại bài đang mở |
| `T` | Đổi giao diện: Tự động (theo máy) → Sáng → Tối. Trang nhớ lựa chọn cho lần mở sau |
| `P` / `F` / `?` | Chế độ trình chiếu / toàn màn hình / bảng phím tắt |

Mở thẳng một bài bằng cách thêm `#a01`, `#a03`, `#a07`, `#a10` hoặc `#tong-ket` vào cuối link.
