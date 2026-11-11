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

- **Trải nghiệm trực tiếp (GitHub Pages):** https://luffyreals.github.io/EduFlaw-CSATTT/ *(không cần cài đặt backend)*
- **Mở offline từ mã nguồn:** [`demo/index.html`](demo/index.html)

---

## 📦 Hướng dẫn sử dụng Repository

### 1. Cấu trúc thư mục chính

```text
EduFlaw-CSATTT/
├── 1_CHAY_WEB_DEMO.bat            # Bật Web App Flask (http://127.0.0.1:5000/login) kèm nút 1-click
├── 2_MO_LAB_THUYET_TRINH.bat      # Mở Lab mô phỏng 4 lỗ hổng OWASP 2025 (offline)
├── 3_RESET_CSDL_DEMO.bat          # Làm mới MySQL eduflaw_db về bộ dữ liệu demo sạch (20 SV, 5 GV)
├── 4_CHAY_KIEM_THU_PENTEST.bat    # Bật Web Pentest Console (/pentest?toolbar=1) + Thanh nổi Web App
├── HUONG-DAN-SU-DUNG-VA-DEMO.pdf  # Tài liệu hướng dẫn sử dụng, kịch bản demo 6 phần & lời thoại (4 trang)
├── demo/                          # Trang mô phỏng tương tác OWASP Top 10:2025 (GitHub Pages / offline)
├── docs/                          # Báo cáo bằng chứng thực nghiệm (19 ảnh), hướng dẫn triển khai
├── pentest/                       # Launcher Web/CLI (live_demo.py), script PoC & fuzzing độc lập
└── src/                           # Mã nguồn Flask + MySQL, migrations, script cài đặt và bộ test pytest
    ├── app/                       # Controllers, Models, Services, Templates, Utils (bao gồm /pentest dev-only)
    ├── tests/                     # Bộ kiểm thử hồi quy pytest
    ├── setup.ps1 / setup.sh       # Cài đặt tự động môi trường ảo, .env và khởi tạo CSDL
    ├── reset_db_demo.py           # Nạp lại dữ liệu mẫu tinh gọn phục vụ demo
    └── run.py                     # Khởi chạy Flask dev server cục bộ
```

---

### 2. Cài đặt môi trường từ đầu (Sau khi `git clone`)

Yêu cầu hệ thống: **Python ≥ 3.11**, **Git** và **MySQL** chạy cục bộ tại cổng `3306`.

1. **Tải mã nguồn:**
   ```bash
   git clone https://github.com/Luffyreals/EduFlaw-CSATTT.git
   cd EduFlaw-CSATTT
   ```
2. **Tạo cơ sở dữ liệu MySQL:**
   ```sql
   CREATE DATABASE eduflaw_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. **Chạy script cài đặt tự động 1 lệnh:**
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
   *(Script tự tạo môi trường ảo `src/.venv`, cài gói từ `requirements-dev.txt`, sinh `src/.env` kèm khóa ngẫu nhiên `SECRET_KEY` / `FIELD_ENCRYPTION_KEY`, khởi tạo bảng từ `schema.sql`, nạp bộ dữ liệu mẫu **20 sinh viên, 5 giảng viên** và chạy kiểm thử xác nhận).*

---

### 3. Khởi chạy & Sử dụng hằng ngày

#### Cách A — Dùng Launcher 1-Click trên Windows (Khuyên dùng)
Tại thư mục gốc, nhấp đúp trực tiếp các file `.bat`:
1. **`3_RESET_CSDL_DEMO.bat`**: Chạy trước mỗi buổi demo/thuyết trình để khôi phục dữ liệu sạch và xóa sạch khóa brute-force cũ.
2. **`4_CHAY_KIEM_THU_PENTEST.bat`**: Tự bật Web App tại cổng `5000` (nếu chưa chạy) và mở thẳng **Bảng Điều Khiển Pentest Trực Tiếp** (`http://127.0.0.1:5000/pentest?toolbar=1`) kèm **Thanh Pentest Nổi** trên Web thật.
   - Phím tắt trong cửa sổ console: `[O]` Mở lại `/pentest`, `[W]` Mở `/login`, `[C]` Chuyển sang Terminal CLI log cũ, `[Q]` Thoát.
3. **`1_CHAY_WEB_DEMO.bat`**: Chỉ khởi động Web App chuẩn và mở `/login` (có sẵn nút đăng nhập 1-click cho Master, Giảng viên, Sinh viên).
4. **`2_MO_LAB_THUYET_TRINH.bat`**: Mở nhanh Lab mô phỏng 4 lỗ hổng (`demo/index.html`) với phím tắt `1–4`, `V`, `S`, `Enter`.

#### Cách B — Khởi chạy thủ công trên nhiều nền tảng (Windows / macOS / Linux)
```bash
# 1) Bật Web App (từ thư mục src/)
.venv/Scripts/python.exe run.py          # Windows
# hoặc: .venv/bin/python run.py          # macOS / Linux

# 2) Hoặc mở thẳng Web Pentest Console từ thư mục gốc:
src/.venv/Scripts/python.exe pentest/live_demo.py
```
Truy cập trình duyệt:
- **Web App chính:** `http://127.0.0.1:5000/login`
- **Bảng Pentest trực tiếp:** `http://127.0.0.1:5000/pentest?toolbar=1`

#### Cách C — Chạy bộ kiểm thử tự động (`pytest`)
```powershell
cd src
.\.venv\Scripts\python.exe -m pytest -v   # Windows (macOS/Linux: .venv/bin/python -m pytest -v)
```

---

### 4. Tài khoản Demo Chuẩn

Sau khi chạy `setup.ps1` / `setup.sh` hoặc `3_RESET_CSDL_DEMO.bat`, hệ thống có sẵn các tài khoản chuẩn (có thể đăng nhập **1-Click** ngay trên `/login`, `/pentest` hoặc **Thanh Pentest Nổi**):

| Vai trò | Tài khoản (Email) | Mật khẩu mặc định | Ghi chú |
|---|---|---|---|
| **Master (Đào tạo)** | `master@eduflaw.com` | Theo `MASTER_PASSWORD` trong `src/.env` (`tung12345678`) | Toàn quyền quản trị & xem `grade_audit_logs` |
| **Giảng viên 1** | `gv.001@eduflaw.com` | `EduFlaw@2026` | Phụ trách lớp tín chỉ mẫu (`AT301`) |
| **Giảng viên 2** | `gv.002@eduflaw.com` | `EduFlaw@2026` | Dùng kiểm thử phân quyền chéo A01-3 |
| **Sinh viên 1** | `b24dcat001@eduflaw.com` | `EduFlaw@2026` | Dùng kiểm thử IDOR & leo thang dọc A01 |
| **Sinh viên 2** | `b24dcat002@eduflaw.com` | `EduFlaw@2026` | Tài khoản sinh viên đối chứng |

---

## ⚡ Bảng điều khiển Pentest trực tiếp trên Web App (`/pentest`)

Thay vì chỉ xem log trong Terminal, `/pentest` tích hợp trực tiếp trên Web App cục bộ (tự khóa **HTTP 404** ở `production` và **HTTP 403** từ ngoài `localhost`) cho phép thao tác kiểm thử thời gian thực:

- **Đổi vai trò thật 1-Click & Thanh Pentest Nổi:** Chuyển phiên trình duyệt tức thì sang Master, GV1, GV2, SV1, SV2 và bấm tấn công nhanh (`🎯 Thử IDOR ?student_id=2`, `🚀 Thử vào /master`, `✏️ GV2 sửa lớp GV1`, `🔓 Mở khóa A07`) ngay khi đang đứng trên `/student/grades` hay `/admin/grades`.
- **6 Tab kiểm thử tương tác thực tế:**
  1. **Bài 1 (OWASP A01):** Kiểm thử IDOR ngang (`/student/grades`), leo thang dọc 6 route `/master/*` & `/admin/*`, và can thiệp chéo GV2 sửa điểm lớp GV1 (`HTTP 403`).
  2. **Bài 2 (OWASP A03):** Đối soát mã băm SHA-256 W3C SRI từ `/login` + `10/10` gói ghim cứng `==` trong `src/requirements.txt`, kèm nút thử **SRI Đúng vs Sai 1 ký tự** ngay trên DOM/DevTools Console.
  3. **Bài 3 (OWASP A07):** Dội thử brute-force tới `/login`, quan sát khóa kép (`ip:` + `user:`) `60s` (`HTTP 429`) trực tiếp trên bảng `login_attempts` và nút **Mở Khóa Nhanh**.
  4. **Bài 4 (OWASP A10):** Thử từng payload hoặc bơm đồng loạt **23 payload dị dạng** vào API để xác nhận `0 lỗi 5xx` và `0 lộ Stack Trace` (Fail-Closed).
  5. **Bài 5 (Attack Surface):** Quét **69 endpoints** dưới góc nhìn chưa đăng nhập/sinh viên kèm bộ lọc nhanh (`302 Bảo vệ`, `404 Không có`, `⚠️ Cảnh báo /console`).
  6. **Bài 6 (DB Forensic):** Soi dữ liệu CCCD mã hóa `AES-256-GCM` (`enc:v1:...`) và nhật ký sửa điểm `grade_audit_logs` trực tiếp từ MySQL thật.
- **Chế độ Terminal CLI (khi cần):** Chạy `python pentest/live_demo.py --cli` hoặc truyền số `1..7` (hoặc nhấn phím `C` trong cửa sổ launcher).

---

## 📚 Tài liệu báo cáo & Hướng dẫn

- **Hướng dẫn sử dụng, kịch bản demo 6 phần & lời thuyết trình (PDF 4 trang):** [`HUONG-DAN-SU-DUNG-VA-DEMO.pdf`](HUONG-DAN-SU-DUNG-VA-DEMO.pdf)
- **Báo cáo toàn văn BTL:** [`BAO-CAO-DAY-DU.md`](BAO-CAO-DAY-DU.md)
- **Báo cáo tổng hợp bằng chứng thực nghiệm:** [`docs/BANG-CHUNG-KIEM-THU.md`](docs/BANG-CHUNG-KIEM-THU.md)
- **Hướng dẫn triển khai & vận hành an toàn:** [`docs/DEPLOY.md`](docs/DEPLOY.md)
- **Bộ công cụ Pentest & Fuzzing chi tiết:** [`pentest/README.md`](pentest/README.md)
