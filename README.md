# 🎓 EduFlaw — Hệ thống Quản lý Đào tạo & Thực nghiệm Bảo mật Web

> **Bài tập lớn học phần:** Cơ sở An toàn thông tin  
> **Cơ sở đào tạo:** Học viện Công nghệ Bưu chính Viễn thông (PTIT Hà Nội)  
> **Giảng viên hướng dẫn:** ThS. Đỗ Xuân Chợ  
> **Nhóm thực hiện:** Nhóm 7 — Lớp D24CQCE04-B  
> **Chuẩn đánh giá:** OWASP Top 10:2025  

---

## 👥 Danh sách thành viên (Nhóm 7)

| STT | Họ và tên | Mã sinh viên | Vai trò & Phân công nhiệm vụ |
|:---:|---|:---:|---|
| 1 | **Nguyễn Hoàng Tùng** | `B24DCCE284` | **Trưởng nhóm** — Kiến trúc hệ thống, kiểm soát truy cập (A01) & tổng hợp |
| 2 | **Nguyễn Bá Minh Đức** | `B24DCCE053` | Kiểm thử xâm nhập, viết kịch bản khai thác PoC |
| 3 | **Trần Anh Tú** | `B24DCCE277` | Fuzzing đường dẫn & tham số, thu thập dữ liệu bằng chứng thực nghiệm |
| 4 | **Bùi Minh Khang** | `B24DCCE137` | Triển khai các lớp phòng thủ từ gốc, cấu hình bảo mật & kiểm thử hồi quy |

---

## 🎯 Mục đích dự án

EduFlaw được xây dựng nhằm đáp ứng **hai mục tiêu song hành**:

1. **Sản phẩm nghiệp vụ đào tạo thực tế:**  
   Ứng dụng web quản lý đào tạo đại học hoàn chỉnh viết bằng **Python (Flask) + MySQL**, phục vụ 3 vai trò:
   - **Master (Phòng Đào tạo):** Quản lý toàn diện ngành, sinh viên, giảng viên, lớp tín chỉ, nhật ký kiểm toán sửa điểm.
   - **Admin (Giảng viên / Cố vấn):** Nhập/sửa điểm các lớp phụ trách, theo dõi sinh viên lớp cố vấn.
   - **Student (Sinh viên):** Tra cứu bảng điểm chi tiết, GPA hệ 4/10, thời khóa biểu và hồ sơ cá nhân.

2. **Môi trường thực nghiệm an toàn thông tin:**  
   Thực hiện phương pháp tiếp cận **"Tự xây — Tự phá — Tự vá"** theo chuẩn bảo mật **OWASP Top 10:2025**, tập trung vào 4 nhóm trọng tâm:
   - **A01:2025** — Broken Access Control (Kiểm soát truy cập, IDOR, vượt quyền).
   - **A03:2025** — Software Supply Chain Failures (Bảo vệ chuỗi cung ứng, ghim phiên bản & SRI Integrity).
   - **A07:2025** — Authentication Failures (Chống brute-force, chống dò quét OTP, thu hồi phiên).
   - **A10:2025** — Mishandling of Exceptional Conditions (Xử lý ngoại lệ Fail-Closed, không lộ thông tin nhạy cảm).

---

## 📸 Bằng chứng kiểm thử & Thực nghiệm của nhóm

Nhóm đã tiến hành kiểm thử toàn diện trên hệ thống bằng cả hai phương pháp **Kiểm thử thủ công** và **Kiểm thử tự động (Fuzzing / Pentest Scripts)**:

### 1. Bằng chứng Fuzzing thực nghiệm (Slide 11 & Slide 12)

| Dò 69 đường dẫn (`fuzz_content.py`) | Bơm 23 payload dị dạng (`fuzz_input.py`) |
|:---:|:---:|
| ![Fuzzing đường dẫn](docs/evidence_screenshots/14_fuzz_content_69_endpoints.png) | ![Fuzzing tham số](docs/evidence_screenshots/15_fuzz_input_23_payloads.png) |
| *Quét không gian URL: Lập bản đồ ranh giới xác thực, phát hiện lộ `/console`* | *23 payload tấn công: **0 lỗi 5xx**, hệ thống xử lý ngoại lệ an toàn Fail-Closed* |

| Dội đăng nhập bản ĐÃ VÁ (`main`) | Dội đăng nhập bản CHƯA VÁ (Lỗ hổng A07) |
|:---:|:---:|
| ![Bản đã vá](docs/evidence_screenshots/16_bruteforce_locked_429.png) | ![Bản chưa vá](docs/evidence_screenshots/17_bruteforce_vuln_unlimited.png) |
| *Khóa IP và tài khoản (HTTP 429) ngay sau lần thử sai thứ 5* | *Không giới hạn tốc độ, thử 12 lần liên tiếp không bị khóa* |

---

### 2. Bằng chứng phòng thủ lỗ hổng & Kiểm soát dữ liệu

| Phòng thủ IDOR (A01) | Bảo vệ chuỗi cung ứng SRI (A03) |
|:---:|:---:|
| ![Chặn IDOR](docs/evidence_screenshots/11_idor_defense_proof.png) | ![SRI CDN](docs/evidence_screenshots/18_demo_a03_supply_chain.png) |
| *Sửa `?student_id` trên URL vẫn chỉ trả về dữ liệu của chính mình* | *CDN bị can thiệp -> Mã băm SHA-256 không khớp, trình duyệt chặn thực thi* |

| Dữ liệu mã hóa trong CSDL (Slide 57) | Nhật ký kiểm toán thay đổi điểm (Audit Logs) |
|:---:|:---:|
| ![Mã hóa CCCD](docs/evidence_screenshots/13_database_encrypted_cccd.png) | ![Audit Logs](docs/evidence_screenshots/10_grade_audit_logs.png) |
| *Mật khẩu băm an toàn, CCCD mã hóa AES-256-GCM (`enc:v1:...`)* | *Lưu vết mọi thay đổi điểm: Ai sửa, môn nào, điểm cũ -> mới* |

👉 *Xem toàn bộ 19 ảnh và phân tích chi tiết tại:* **[Báo cáo tổng hợp bằng chứng thực nghiệm](docs/BANG-CHUNG-KIEM-THU.md)**

---

## 🧪 Trang Demo mô phỏng lỗ hổng (Interactive Demo)

Để phục vụ trình bày trực quan tại buổi báo cáo, nhóm đã xây dựng trang web mô phỏng tương tác có công tắc chuyển đổi **"Có lỗ hổng" (Vulnerable)** ↔ **"Đã vá" (Secured)** cho 4 kịch bản OWASP 2025:
- **A01:** IDOR xem điểm người khác qua link URL.
- **A03:** CDN SweetAlert2 bị đầu độc, kiểm tra cơ chế SRI.
- **A07:** Tấn công dò mật khẩu và cơ chế khóa tài khoản.
- **A10:** Xử lý lỗi CSDL (Fail-Closed từ chối an toàn vs Fail-Open lộ quyền).

Mở trực tiếp trên trình duyệt: [`demo/index.html`](demo/index.html) *(không cần cài đặt backend)*.

---

## 🚀 Hướng dẫn khởi chạy ứng dụng (Python + MySQL cục bộ)

Yêu cầu môi trường: **Python ≥ 3.11** và **MySQL** chạy cục bộ (cổng 3306).

### Bước 1: Tạo Database MySQL
Mở MySQL (MySQL Workbench / phpMyAdmin / dòng lệnh) và tạo cơ sở dữ liệu:
```sql
CREATE DATABASE eduflaw_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Bước 2: Cài đặt tự động một lệnh
- **Windows (PowerShell):**
  ```powershell
  cd src
  powershell -ExecutionPolicy Bypass -File .\setup.ps1
  ```
- **macOS / Linux:**
  ```bash
  cd src
  ./setup.sh
  ```
*(Script sẽ tự động tạo môi trường ảo `.venv`, cài thư viện, sinh file `.env`, tạo bảng từ `schema.sql` và tự động nạp dữ liệu mẫu **Demo Tinh Gọn** gồm 20 sinh viên, 5 giảng viên, 17 lớp tín chỉ phục vụ hoàn hảo cho buổi thuyết trình).*

> **Mẹo:** Nếu cần xóa trắng CSDL và reset lại bộ dữ liệu Demo tinh gọn bất kỳ lúc nào, chỉ cần chạy:
> ```powershell
> python reset_db_demo.py
> ```

### Bước 3: Khởi chạy Server
```bash
python run.py
```
Mở trình duyệt: **http://127.0.0.1:5000**  
- **Tài khoản Master:** `master@eduflaw.com` / Mật khẩu trong file `.env` (mặc định: `tung12345678`)  
- **Tài khoản Giảng viên Demo:** `gv.001@eduflaw.com` / Mật khẩu `EduFlaw@2026`  
- **Tài khoản Sinh viên Demo:** `b24dcat001@eduflaw.com` / Mật khẩu `EduFlaw@2026`  

---

## ⚡ Bảng điều khiển kiểm thử trực tiếp (Live Pentest Console)

Nhóm đã phát triển bảng điều khiển kiểm thử tương tác trực tiếp qua Terminal. Trong khi ứng dụng web đang chạy, mở một cửa sổ Terminal mới và gõ:
```bash
python pentest/live_demo.py
```
Menu tương tác cung cấp 5 chức năng kiểm thử thực chiến:
1. **Live Fuzzing (Quét 69 đường dẫn):** Rà quét tiến trình thực, lập bản đồ xác thực và phát hiện route ẩn.
2. **Live Input Fuzzing (23 Payload dị dạng):** Bơm SQLi, XSS, Path Traversal, SSTI vào API để kiểm chứng nguyên tắc **Fail-Closed** (0 lỗi 500).
3. **Live Brute-force Attack (Chống dò mật khẩu A07):** Dội thử mật khẩu sai và kích hoạt cơ chế khóa bảo vệ **HTTP 429** sau lần thứ 5.
4. **Live Database Forensic Inspector:** Kiểm chứng trực tiếp số CCCD được mã hóa AES-256-GCM trong bảng `student_profiles` và kiểm tra nhật ký kiểm toán `grade_audit_logs`.
5. **Quick Automated Audit:** Chạy quét kiểm thử tổng hợp toàn bộ hệ thống.

---

## 📚 Tài liệu báo cáo & Thuyết trình của nhóm

- **Báo cáo toàn văn BTL:** [`BAO-CAO-DAY-DU.md`](BAO-CAO-DAY-DU.md)
- **Kịch bản thuyết trình (Slide 1–25):** [`NOI-DUNG-THUYET-TRINH.md`](NOI-DUNG-THUYET-TRINH.md)
- **Cẩm nang kiến thức & Hỏi đáp phản biện:** [`GIAI-THICH-KIEN-THUC-VA-QA.md`](GIAI-THICH-KIEN-THUC-VA-QA.md)
- **Bộ công cụ Pentest & Fuzzing:** [`pentest/README.md`](pentest/README.md)
