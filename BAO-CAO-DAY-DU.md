# BÁO CÁO BÀI TẬP LỚN
# Kiểm thử bảo mật ứng dụng web EduFlaw

**Học phần:** Cơ sở An toàn thông tin  
**Cơ sở đào tạo:** Học viện Công nghệ Bưu chính Viễn thông (PTIT Hà Nội)  
**Lớp:** D24CQCE04-B  
**Giảng viên hướng dẫn:** ThS. Đỗ Xuân Chợ  
**Nhóm thực hiện:** Nhóm 7  
**Chuẩn đánh giá:** OWASP Top 10:2025  

| STT | Thành viên | Mã sinh viên | Vai trò & Phân công |
|:---:|---|:---:|---|
| 1 | Nguyễn Hoàng Tùng | B24DCCE284 | Trưởng nhóm — kiến trúc & phân tích lỗ hổng |
| 2 | Nguyễn Bá Minh Đức | B24DCCE053 | Kiểm thử & viết PoC |
| 3 | Trần Anh Tú | B24DCCE277 | Fuzzing & thu thập bằng chứng |
| 4 | Bùi Minh Khang | B24DCCE137 | Phòng thủ & tổng hợp báo cáo |

> **Tuyên bố phạm vi & đạo đức:** Toàn bộ hoạt động "tấn công" trong báo cáo này chỉ thực hiện trên **máy lab cô lập của nhóm** (`localhost`), với **dữ liệu seed giả**. Khi phát hành repository công khai, toàn bộ mã nguồn trên nhánh `main` là bản đã được phòng thủ và vá toàn diện; trang demo công khai (`demo/index.html`) là **mô phỏng tương tác bằng JavaScript** với dữ liệu giả, không chứa mã lỗi thật. Mọi tài khoản, mật khẩu, CCCD xuất hiện trong báo cáo đều là dữ liệu sinh tự động, **không phải thông tin thật của bất kỳ ai**.

---

## MỤC LỤC

1. [Lời mở đầu](#1-lời-mở-đầu)
2. [Tổng quan dự án EduFlaw](#2-tổng-quan-dự-án-eduflaw)
3. [Cơ sở lý thuyết](#3-cơ-sở-lý-thuyết)
4. [Phương pháp & quy trình kiểm thử](#4-phương-pháp--quy-trình-kiểm-thử)
5. [Kết quả kiểm thử theo 4 nhóm OWASP 2025](#5-kết-quả-kiểm-thử-theo-4-nhóm-owasp-2025)
   - [5.1. A01 — Broken Access Control](#51-a012025--broken-access-control)
   - [5.2. A03 — Software Supply Chain Failures](#52-a032025--software-supply-chain-failures-mới)
   - [5.3. A07 — Authentication Failures](#53-a072025--authentication-failures)
   - [5.4. A10 — Mishandling of Exceptional Conditions](#54-a102025--mishandling-of-exceptional-conditions-mới)
6. [Bằng chứng fuzzing, rà soát & demo](#6-bằng-chứng-fuzzing-rà-soát--demo)
7. [Tổng hợp các lớp phòng thủ](#7-tổng-hợp-các-lớp-phòng-thủ)
8. [Kết quả, bài học, hạn chế & hướng phát triển](#8-kết-quả-bài-học-hạn-chế--hướng-phát-triển)
9. [Phụ lục](#9-phụ-lục) — gồm 6 lỗ hổng A02/A05 (bản 2021) đã kiểm thử ngoài trọng tâm

---

## 1. LỜI MỞ ĐẦU

An toàn thông tin không phải là một tính năng gắn thêm vào cuối dự án, mà là một thuộc tính phải được thiết kế và kiểm chứng xuyên suốt vòng đời phần mềm. Để hiểu điều đó một cách thực chất, nhóm 7 đã chọn cách tiếp cận **"tự xây — tự phá — tự vá"**: nhóm tự phát triển một ứng dụng web quản lý sinh viên hoàn chỉnh mang tên **EduFlaw**, sau đó đóng vai kẻ tấn công để tìm và khai thác lỗ hổng trên chính sản phẩm của mình, rồi vá từ gốc và kiểm chứng lại bằng bằng chứng thật.

Báo cáo bám theo **OWASP Top 10:2025** — bản mới nhất (OWASP chưa phát hành bản web năm 2026). Bản 2025 có **hai hạng mục hoàn toàn mới** là **A03 Software Supply Chain Failures** và **A10 Mishandling of Exceptional Conditions**; nhóm chọn cả hai, cùng hai nhóm kinh điển **A01** và **A07**, làm trọng tâm.

Báo cáo trình bày:
- Kiến trúc và mô hình phân quyền của EduFlaw.
- Cơ sở lý thuyết về kiểm thử bảo mật, OWASP Top 10:2025 và các khái niệm then chốt (IDOR, SRI, fail-open/fail-closed…).
- Phương pháp kiểm thử hộp trắng kết hợp fuzzing, rà soát chuỗi cung ứng, và quy trình "mỗi lỗ hổng một nhánh git".
- Phân tích chi tiết các lỗ hổng của 4 nhóm trọng tâm: **A01 (4 lỗ hổng), A03 (3), A07 (3), A10 (4)** — từ đoạn code sai, kịch bản khai thác, hậu quả, đến cách vá và lý do vá đó hiệu quả.
- Bằng chứng thực nghiệm (log fuzzer, log brute-force, kết quả rà soát) và **trang demo** mô phỏng từng lỗ hổng.
- Bài học, hạn chế trung thực và hướng phát triển.
- Phụ lục: **6 lỗ hổng A02/A05** (theo bản 2021) nhóm đã khai thác và vá trước khi chuyển chuẩn — giữ lại đầy đủ để không mất công việc đã làm.

Mục tiêu cuối cùng không chỉ là "đã chặn được lỗ hổng", mà là **hiểu vì sao chặn được** — đó mới là năng lực an toàn thông tin thật sự.

---

## 2. TỔNG QUAN DỰ ÁN EDUFLAW

### 2.1. EduFlaw là gì

EduFlaw là một **ứng dụng web quản lý sinh viên** cho môi trường đào tạo đại học, cung cấp các nghiệp vụ:
- Quản lý **hồ sơ sinh viên** (thông tin cá nhân, ngành, lớp hành chính, CCCD).
- Quản lý **lớp tín chỉ**, ghi danh, phân công giảng viên và cố vấn học tập.
- **Nhập, tính và tra cứu điểm** (6 đầu điểm thành phần + thi lại, tính điểm tổng kết theo trọng số, quy đổi hệ 10 → hệ 4 → điểm chữ, tính GPA).
- **Thời khóa biểu**, **thông báo** (toàn trường hoặc theo lớp).
- Nhật ký sửa điểm, import/export Excel.

Dự án được xây dựng với **hai mục tiêu song song**:

| Mục tiêu | Mô tả |
|---|---|
| **Sản phẩm nghiệp vụ** | Một nền tảng web quản lý học tập hoàn chỉnh, vận hành được thật, có phân trang, tìm kiếm phía máy chủ, xử lý hàng nghìn bản ghi (~3.000 sinh viên, ~1.900 lớp tín chỉ). |
| **Môi trường thực nghiệm ATTT** | Một "thao trường" để nhóm cố ý cài lỗ hổng, khai thác và vá theo chuẩn **OWASP Top 10:2025**. |

Vì nhóm **tự viết toàn bộ mã nguồn**, nhóm có điều kiện kiểm thử theo **hộp trắng** — mức độ hiểu sâu nhất về hệ thống.

### 2.2. Công nghệ nền tảng

| Thành phần | Công nghệ |
|---|---|
| Backend | Python + **Flask 3.1.3** (app factory, blueprint) |
| Cơ sở dữ liệu | **MySQL / TiDB** (kết nối qua pool, TLS) |
| Giao diện | HTML, CSS, Jinja2; **SweetAlert2 11.10.5**, **Chart.js 4.4.1** tải từ CDN jsDelivr có **SRI** |
| Thư viện bảo mật | Flask-WTF (CSRF), Werkzeug (băm mật khẩu), cryptography (AES-GCM), certifi (TLS) |
| Phụ thuộc | 10 gói Python **ghim chính xác phiên bản** trong `src/requirements.txt` |
| Kiểm thử & CI | pytest (171 test, không cần CSDL); GitHub Actions trên Ubuntu + Windows |
| Triển khai | `run.py` (dev), `serve.py` (waitress, production), Docker Compose |

### 2.3. Kiến trúc ứng dụng

- **App factory** `create_app` (`app/__init__.py`) đăng ký bốn blueprint trong `app/controllers/`: `auth`, `student`, `admin` (giảng viên), `master`. Route có tiền tố theo vai trò: `/student/...`, `/admin/...`, `/master/...`.
- **Bảo vệ CSRF** (Flask-WTF) bật toàn cục → mọi form POST và lời gọi AJAX đều cần CSRF token.
- **Header bảo mật** gắn ở hook `after_request`: `X-Frame-Options: DENY`, CSP, `nosniff`, `Referrer-Policy`, và `HSTS` khi chạy production.
- **Truy cập dữ liệu không dùng ORM**: các model chạy **SQL thuần tham số hóa** qua context manager `get_db_cursor` — **SQL Injection bị chặn sẵn từ thiết kế**. `get_db_cursor` **rollback với mọi exception** trong khối ghi.
- **Pool kết nối** khởi tạo lười, bọc bằng `SafePooledConnection` — **rollback giao dịch dở** trước khi trả kết nối về pool.
- **Xử lý lỗi tập trung**: `app/utils/error_pages.py` thay trang lỗi mặc định bằng trang tiếng Việt (400, 403, 404, 405, 413, 429, 500); đường dẫn `/api/` nhận JSON `{success: false, message}`; lỗi 500 chỉ ghi log, **không lộ stack trace**.

### 2.4. Ba vai trò và mô hình phân quyền

| Vai trò | Quyền hạn |
|---|---|
| **Master** | Quản trị cao nhất: toàn quyền CRUD trên mọi đối tượng (sinh viên, ngành, giảng viên, lớp, điểm, phân công, thông báo, nhật ký). |
| **Giảng viên (admin)** | Chỉ thao tác **lớp tín chỉ mình phụ trách** (`lecturer_id`) và **sinh viên lớp mình cố vấn** (`advisor_email`). Ra ngoài phạm vi → **403**. |
| **Sinh viên (student)** | Chỉ xem dữ liệu **của chính mình**: điểm & GPA, lịch học, lớp, hồ sơ. Chỉ tự sửa thông tin liên lạc. |

**Nguyên tắc cốt lõi:** quyền được kiểm tra **ở từng request trong controller** (qua `is_class_assigned_to_advisor`, `is_student_assigned_to_advisor`, kiểm `lecturer_id`…), **không** chỉ dựa vào decorator hay việc ẩn nút trên giao diện. Decorator `role_required` kiểm vai trò chung và còn gọi `User.is_account_active` ở **mỗi request** để thu hồi phiên của tài khoản bị khóa hoặc đã đổi mật khẩu.

#### Ma trận phân quyền chi tiết

| Đối tượng / chức năng | MASTER | GIẢNG VIÊN | SINH VIÊN |
|---|---|---|---|
| Hồ sơ sinh viên | C R U D (toàn trường) | R U (SV lớp mình cố vấn) | R (chỉ của mình) |
| Tài khoản giảng viên/admin | C R U D* (khóa/mở) | R U (hồ sơ bản thân) | — |
| Lớp tín chỉ | C R U D | R (lớp mình dạy) | R (lớp đã ghi danh) |
| Điểm số | R (xem chi tiết) | C U (lớp mình; auto-save) | R (điểm mình + GPA) |
| Mật khẩu | U | U | U |
| Thời khóa biểu | R (gián tiếp) | R (lịch dạy) | R (lịch học) |

> C = Tạo · R = Xem · U = Sửa · D = Xóa · — = không có · * khóa/mở, không xóa cứng.

---

## 3. CƠ SỞ LÝ THUYẾT

### 3.1. OWASP Top 10:2025

**OWASP (Open Worldwide Application Security Project)** là tổ chức phi lợi nhuận về an toàn ứng dụng. **OWASP Top 10** là danh sách **mười rủi ro bảo mật web phổ biến và nguy hiểm nhất**, cập nhật định kỳ, được dùng rộng rãi làm **thước đo chuẩn**. Bản hiện hành là **2025** (phát hành cuối năm 2025); các danh sách "2026" của OWASP chỉ dành cho ứng dụng LLM và AI agent, không áp dụng cho EduFlaw.

| Mã 2025 | Tên | Ghi chú so với 2021 |
|---|---|---|
| A01 | Broken Access Control | Giữ vị trí số 1 |
| A02 | Security Misconfiguration | Tăng từ A05:2021 |
| **A03** | **Software Supply Chain Failures** | **Mới** — mở rộng từ "Vulnerable and Outdated Components" |
| A04 | Cryptographic Failures | Từ A02:2021 |
| A05 | Injection | Từ A03:2021 |
| A06 | Insecure Design | |
| A07 | Authentication Failures | Đổi tên từ "Identification & Authentication Failures" |
| A08 | Software or Data Integrity Failures | |
| A09 | Security Logging & Alerting Failures | |
| **A10** | **Mishandling of Exceptional Conditions** | **Mới hoàn toàn** |

**Bốn nhóm trọng tâm của báo cáo:**

| Mã | Tên | Bản chất | Vì sao chọn |
|---|---|---|---|
| **A01** | Broken Access Control | Người dùng làm được việc **ngoài quyền** | Rủi ro số 1; trung tâm mô hình phân quyền của EduFlaw |
| **A03** | Software Supply Chain Failures | Thư viện, CDN, công cụ build **bên thứ ba bị lỗi thời, bị đầu độc hoặc bị chiếm** | Hạng mục mới; EduFlaw phụ thuộc 10 gói Python + 2 thư viện CDN |
| **A07** | Authentication Failures | Không chống dò mật khẩu, quản lý phiên kém | Có bằng chứng fuzzing rõ nhất |
| **A10** | Mishandling of Exceptional Conditions | Xử lý sai khi gặp lỗi: **lộ thông tin**, **fail-open**, để **trạng thái dở dang** | Hạng mục mới; EduFlaw dùng CSDL ở xa nên lỗi mạng/timeout là thực tế |

> Hai nhóm A02 (Cryptographic Failures) và A05 (Security Misconfiguration) **theo bản 2021** — tương ứng **A04:2025** và **A02:2025** — nhóm đã khai thác và vá 6 lỗ hổng; nội dung đầy đủ nằm ở **Phụ lục 9.1**.

### 3.2. Các kiểu kiểm thử: hộp đen / xám / trắng

| Kiểu | Hiểu biết về hệ thống | Góc nhìn |
|---|---|---|
| **Hộp đen** (black-box) | Không biết mã nguồn | Như hacker ngoài, dò từ bên ngoài. |
| **Hộp xám** (grey-box) | Biết một phần (ví dụ có một tài khoản hợp lệ) | Người dùng nội bộ lạm quyền. |
| **Hộp trắng** (white-box) | **Biết toàn bộ mã nguồn** | Soi sâu nhất — phát hiện lỗi logic ẩn. |

Nhóm **chủ yếu dùng hộp trắng** (vì tự viết app), đồng thời **mô phỏng góc nhìn hộp xám/đen** khi khai thác.

### 3.3. Fuzzing

**Fuzzing** là kỹ thuật **tự động bơm nhiều dữ liệu đầu vào** (hợp lệ, dị dạng, ngẫu nhiên, hàng loạt) để phát hiện: endpoint ẩn, **ngoại lệ chưa xử lý (lỗi 5xx)**, thiếu giới hạn tần suất. Nhóm **tự viết fuzzer bằng Python** (thư viện chuẩn `urllib`), chạy localhost và ghi log làm bằng chứng. Fuzzing là công cụ tự nhiên để kiểm A10: chỉ cần **một** payload gây lỗi 500 là đã chứng minh có ngoại lệ không được xử lý.

### 3.4. Các khái niệm bảo mật then chốt

**IDOR (Insecure Direct Object Reference) — A01:** ứng dụng dùng **mã định danh do client cung cấp** (ví dụ `?student_id=`) để truy dữ liệu mà **không kiểm người dùng có quyền với mã đó không**.

**Leo thang đặc quyền — A01:** từ quyền thấp (sinh viên) chiếm được quyền cao (master), thường do hàng rào phân quyền bị bỏ.

**Chuỗi cung ứng phần mềm — A03:** mọi thứ **không do mình viết** nhưng chạy trong ứng dụng: gói Python (pip), script JS từ CDN, image Docker, GitHub Actions, công cụ build. Kẻ tấn công không cần hack ứng dụng — **hack thứ ứng dụng tin tưởng**. Các sự cố thật gần đây:
- **polyfill.io (2024):** tên miền CDN đổi chủ, bắt đầu phát tán mã độc tới hơn 100 nghìn website đang nhúng script.
- **xz-utils (2024, CVE-2024-3094):** backdoor được một "người đóng góp" cài vào thư viện nén sau thời gian dài lấy lòng tin.
- **Shai-Hulud (9/2025):** sâu tự lây qua hàng trăm gói npm bằng token đánh cắp từ máy lập trình viên.

**Ghim phiên bản (version pinning) — A03:** ghi `Flask==3.1.3` thay vì `Flask` hay `Flask>=3`. Không ghim → mỗi lần cài có thể kéo **bản mới bị đầu độc** mà không ai hay.

**SRI (Subresource Integrity) — A03:** thuộc tính `integrity="sha256-…"` trên thẻ `<script>`. Trình duyệt **tự tính SHA-256** của file tải về và so với giá trị ghim; **lệch một byte là từ chối chạy**. Cần kèm `crossorigin="anonymous"` để trình duyệt được phép đọc nội dung file khác nguồn mà kiểm tra. Mã băm nằm **trong template của mình**, nên kẻ chiếm CDN không sửa được nó; và không thể tạo file độc **trùng SHA-256** (tính kháng va chạm).

**Fail-open vs. fail-closed — A10:** khi một bước kiểm tra **gặp lỗi** (CSDL mất kết nối, timeout, dữ liệu lạ), hệ thống phải chọn **cho qua** (fail-open — nguy hiểm, kẻ tấn công cố tình gây lỗi để vượt kiểm tra) hay **từ chối** (fail-closed — an toàn). Nguyên tắc: *"không chắc thì từ chối"*.

**Lộ thông tin qua lỗi — A10:** stack trace, câu SQL, tên bảng/cột, đường dẫn máy chủ, phiên bản thư viện là **bản đồ** cho bước tấn công tiếp theo. Người dùng chỉ cần thông báo chung; chi tiết thuộc về **log phía máy chủ**.

**Trạng thái dở dang — A10:** lỗi xảy ra giữa chừng một giao dịch mà không rollback → dữ liệu nửa vời có thể bị commit ở request sau (đặc biệt khi kết nối được tái sử dụng qua pool).

**pw_fp (password fingerprint) — A07:** vì session Flask nằm trong **cookie** (không xóa được phía máy chủ), hệ thống lưu `session['pw_fp']` = HMAC của hash mật khẩu. Đổi mật khẩu → `pw_fp` đổi → **mọi phiên cũ mất hiệu lực**.

**Account enumeration (dò tài khoản) — A07:** suy ra tài khoản/email nào có thật dựa vào khác biệt trong phản hồi; chống bằng cách **trả phản hồi giống nhau** cho mọi trường hợp.

### 3.5. Các lớp phòng thủ "có sẵn" (không phải trọng tâm khai thác)

| Nguy cơ | Phòng thủ sẵn trong EduFlaw |
|---|---|
| **SQL Injection** (A05:2025) | 100% truy vấn **tham số hóa** qua `get_db_cursor` — không nối chuỗi. |
| **XSS** | Jinja2 **auto-escape**, không chèn `{{ }}` vào JavaScript, CSP. |
| **CSRF** | Flask-WTF bật toàn cục, mọi POST cần token. |
| **MITM** | **TLS** tới cơ sở dữ liệu (xác thực chứng chỉ). |
| **Lộ dữ liệu nhạy cảm** (A04:2025) | CCCD mã hóa AES-GCM, mật khẩu băm scrypt/pbkdf2 (chi tiết ở Phụ lục 9.1). |

---

## 4. PHƯƠNG PHÁP & QUY TRÌNH KIỂM THỬ

### 4.1. Phương pháp tổng thể

Nhóm kiểm thử theo **hộp trắng**, kết hợp **hai kỹ thuật bù trừ nhau**:

| | Thủ công (manual) | Fuzzing |
|---|---|---|
| **Bắt tốt** | Lỗi **logic & phân quyền** (IDOR, vượt quyền — A01); **chuỗi cung ứng** (thư viện không ghim, thiếu SRI — A03). | **Ngoại lệ chưa xử lý** (5xx — A10), endpoint ẩn, **thiếu khóa brute-force** (A07). |
| **Cách làm** | Đọc mã nguồn, đổi tham số/URL, phát lại request, mở DB kiểm chứng; **rà `requirements.txt` và từng thẻ `<script>`**. | Tự viết fuzzer Python, bơm payload dị dạng, dội đăng nhập hàng loạt. |

**Vì sao cần cả hai:**
- *Fuzzing bắt tốt* những gì chỉ lộ khi lặp lại tự động nhiều lần (thiếu khóa brute-force) hoặc khi quét diện rộng nhiều đầu vào lạ (ngoại lệ chưa xử lý).
- *Kiểm thử tay bắt tốt* **IDOR** — phản hồi trả HTTP **200 trông hợp lệ**, fuzzer không có "oracle" để biết dữ liệu đó là của người khác; **chuỗi cung ứng** — lỗi nằm ở cấu hình (một dòng requirements thiếu `==`, một thẻ script thiếu `integrity`), không tạo ra phản hồi bất thường nào để fuzzer bắt; và **loại dương tính giả** (một lần phản hồi chậm 7.4 giây, chạy lại không tái hiện → con người loại bỏ).

### 4.2. Mô hình "mỗi lỗ hổng một nhánh git" (A01, A07)

Để minh họa **đối chứng rõ ràng giữa code sai và code đúng**:

- Nhánh **`main`**: code chuẩn, **đã có phòng thủ**.
- Nhánh **`vuln/<mã>`**: gỡ **đúng một** lớp phòng thủ, cố ý gài **đúng một** lỗ hổng. Mỗi dòng hỏng có comment `# VULN <mã> (CỐ Ý GÀI LỖI — KHÔNG MERGE)`.

Với mỗi lỗ hổng: `git switch vuln/<mã>` → quay cảnh **tấn công thành công**; `git switch main` → quay cảnh **bị chặn**; đọc đối chứng bằng lệnh chỉ-đọc `git show vuln/A01-1:src/app/controllers/student.py`.

> Quy tắc an toàn: nhánh `vuln/*` **không bao giờ** merge vào `main`, không deploy, không public.

### 4.3. Rà soát & mô phỏng (A03, A10)

Hai nhóm mới được kiểm theo cách khác, vì bản chất lỗ hổng khác:
- **A03** là lỗi **cấu hình và quy trình**, không phải một dòng logic. Nhóm **rà soát toàn bộ** phụ thuộc (10 gói Python, 2 thư viện CDN trên 6 template), đối chiếu với một **bản lỗi giả định** (không ghim, thiếu SRI) và chứng minh cơ chế chặn bằng **phép tính SHA-256 thật** trên trang demo.
- **A10** được kiểm bằng **fuzzing đầu vào** (23 payload dị dạng → đếm lỗi 5xx) và **soi mã các nhánh `except`**: mỗi chỗ bắt ngoại lệ trả về gì, có cho qua không, có rollback không, có lộ chi tiết không.
- Cả hai được **mô phỏng trên trang demo** `demo/index.html` (bản lỗi ↔ bản vá), dùng nguyên văn thông báo lỗi và tên hàm của code `main`.

### 4.4. Quy trình 4 bước (lặp cho mỗi lỗ hổng)

1. **Soi mã nguồn** — nơi nhận `id` từ client, các nhánh `except`, danh sách thư viện bên ngoài, hàng rào phân quyền.
2. **Dựng bản có lỗ hổng** — nhánh `vuln/*` (A01, A07) hoặc bản lỗi giả định trên trang demo (A03, A10).
3. **Khai thác thật** — đổi `student_id`, vượt quyền giảng viên, dội đăng nhập, gửi dữ liệu dị dạng, thay thư viện bị sửa — và **kiểm chứng** (CSDL, log, console trình duyệt).
4. **Vá & kiểm lại** — sửa ở `main`, thêm **pytest** chống tái phát; CI chạy lại mỗi lần push.

### 4.5. Công cụ PoC tự viết

Các script PoC dùng **thư viện chuẩn Python** (urllib); mỗi script tự lấy CSRF token, giữ cookie phiên và ghi log vào `pentest/evidence/`:

| Script | Lỗ hổng | Mô tả |
|---|---|---|
| `a07_1_bruteforce.py` | A07-1 | Dội sai mật khẩu đến khi bị khóa 429. |
| `a07_2_otp_enum.py` | A07-2 | Chứng minh `/auth/api/send-otp` trả phản hồi đồng nhất cho tài khoản thật/giả. |
| `a01_3_role_escalation.py` | A01-3 | Student truy cập `/master/*` → kỳ vọng 302 (không cho vào). |
| `fuzz_content.py`, `fuzz_input.py` | A10, A07 | Dò 69 đường dẫn; bơm 23 payload dị dạng. *Hai script này chưa được đưa vào repo; kết quả còn lưu dưới dạng ảnh log trên slide 11.* |
| `a05_3_headers.py` | A05-3 (phụ lục) | Liệt kê & đánh giá security header. |

Trang demo **`demo/index.html`** mô phỏng cả 4 nhóm để trình chiếu (xem mục 6.4).

---

## 5. KẾT QUẢ KIỂM THỬ THEO 4 NHÓM OWASP 2025

Nhóm phân tích **14 lỗ hổng** thuộc 4 nhóm trọng tâm. A01 và A07 được **khai thác thật** trên nhánh `vuln/*`; A03 và A10 được **rà soát trên `main`** và **mô phỏng** trên trang demo. Phân bố mức độ:

| Nhóm | 🔴 Nghiêm trọng | 🟠 Cao | 🟡 Trung bình | Cách kiểm |
|---|---|---|---|---|
| **A01** Broken Access Control | A01-3 (student → master) | A01-1, A01-2, A01-4 | | Nhánh `vuln/*`, khai thác thật |
| **A03** Supply Chain Failures *(mới)* | A03-1 (CDN không SRI), A03-2 (gói không ghim) | | A03-3 (quy trình build) | Rà soát + mô phỏng |
| **A07** Authentication Failures | | A07-1, A07-3 | A07-2 | Nhánh `vuln/*`, khai thác thật |
| **A10** Exceptional Conditions *(mới)* | | A10-1 (fail-open), A10-2 (lộ lỗi) | A10-3 (dở dang), A10-4 (tài nguyên) | Fuzzing + soi `except` + mô phỏng |

Mỗi lỗ hổng trình bày theo cấu trúc: **mô tả → mức độ & tiền đề → code sai ↔ code đúng → kịch bản khai thác → hậu quả → cách vá & vì sao hiệu quả**.

---

### 5.1. A01:2025 — Broken Access Control

> **Ý tưởng chung:** server **phải tự xác định "bạn là ai, được phép gì" từ phiên đăng nhập**, không tin thông tin client gửi lên, và phải kiểm **ở từng request** chứ không chỉ ẩn nút trên giao diện.

#### A01-1 · IDOR — tin tham số `student_id` trên link
- **File:** `app/controllers/student.py:51` · **Commit:** `496b764` · **Mức độ:** 🟠 Cao
- **Tiền đề:** 1 tài khoản sinh viên đã onboarding; biết `users.id` của SV khác (số nguyên tăng dần, dễ đoán).

**Code sai (`vuln/A01-1`):**
```python
def view_grades():
    # VULN A01-1: tin tham số student_id trên link
    sid = request.args.get('student_id') or session['user_id']
    raw_grades = Grade.get_all_grades_by_student(sid)
```
**Code đúng (`main`):**
```python
def view_grades():
    raw_grades = Grade.get_all_grades_by_student(session['user_id'])
    overall = Grade.calculate_gpa(raw_grades)
```
- **Kịch bản khai thác:** đăng nhập bằng tài khoản sinh viên, sửa URL thành `/student/grades?student_id=<id khác>`.
- **Hậu quả:** xem được bảng điểm, GPA và hồ sơ (kèm **PII/CCCD**) của **bất kỳ sinh viên nào**.
- **Cách vá & vì sao hiệu quả:** `main` luôn lấy danh tính từ `session['user_id']` — giá trị do máy chủ gán lúc đăng nhập, nằm trong cookie đã ký, **client không sửa được**. Tham số URL bị bỏ hoàn toàn, nên mỗi người chỉ truy vấn được điểm của chính mình.

#### A01-2 · Vượt quyền giảng viên — sửa điểm lớp không phụ trách
- **File:** `app/controllers/admin.py:414` · **Commit:** `5282e49` · **Mức độ:** 🟠 Cao
- **Tiền đề:** 2 tài khoản giảng viên (gv.001 chủ lớp, gv.002 kẻ tấn công); biết `grade_id` ô điểm mục tiêu.

**Code sai (`vuln/A01-2`):** API auto-save chỉ kiểm dòng điểm **có tồn tại** hay không:
```python
    # VULN A01-2: bỏ kiểm quyền sở hữu lớp (lecturer_id)
    if not row:
        return jsonify({'success': False, 'message': 'Không tìm thấy dòng điểm.'}), 404
```
**Code đúng (`main`):**
```python
    if not row or row['lecturer_id'] != user_id:
        return jsonify({'success': False,
            'message': '⛔ Bạn không có quyền chỉnh sửa điểm của lớp học phần này!'}), 403
```
- **Kịch bản khai thác:** gv.002 (không dạy lớp 243198) gọi `POST /admin/grades/api/auto-save` với `grade_id` của lớp gv.001.
- **Hậu quả:** một giảng viên bất kỳ có thể **sửa trộm điểm của mọi lớp toàn trường**.
- **Cách vá & vì sao hiệu quả:** `main` so chủ sở hữu lớp (`lecturer_id`) với người đang đăng nhập (`user_id`); không khớp → **403**. Kiểm quyền ở **từng request**, đúng mô hình "giảng viên chỉ thao tác lớp của mình". Luồng nhập điểm theo lớp cũng có kiểm tra tương tự (`admin.py:250–252`).

#### A01-3 · Leo thang đặc quyền — bỏ kiểm vai trò trong `role_required`
- **File:** `app/utils/decorators.py:14` · **Commit:** `50768c3` · **Mức độ:** 🔴 Nghiêm trọng
- **Tiền đề:** 1 tài khoản sinh viên đã onboarding.

**Code sai (`vuln/A01-3`):** bỏ hẳn phép so vai trò:
```python
            user_role = session.get('role')
            # VULN A01-3: bỏ kiểm vai trò -> ai đăng nhập cũng vào mọi route
            if not User.is_account_active(session.get('user_id'), user_role, session.get('pw_fp', '')):
```
**Code đúng (`main`):**
```python
            user_role = session.get('role')
            if user_role not in allowed_roles:
                dashboard_map = {'master': '/master', 'admin': '/admin', 'student': '/student'}
                return redirect(dashboard_map.get(user_role, '/login'))
```
- **Kịch bản khai thác:** tài khoản sinh viên truy cập thẳng `/master/...`.
- **Hậu quả:** `role_required` là **hàng rào phân quyền trung tâm** cho mọi route; bỏ phép so khiến **bất kỳ ai đã đăng nhập** (kể cả sinh viên) đều gọi được route của master/admin → **chiếm toàn quyền hệ thống**.
- **Cách vá & vì sao hiệu quả:** `main` so vai trò trong session với danh sách được phép; sai vai trò → chuyển hướng về đúng dashboard (302). Phần kiểm `is_account_active` (thu hồi session) vẫn giữ.

#### A01-4 · Vượt quyền cố vấn — xem được lớp hành chính không được phân công
- **File:** `app/controllers/admin.py:42` (+ `profile_model.py`) · **Commit:** `3434b6b` · **Mức độ:** 🟠 Cao
- **Tiền đề:** 1 tài khoản cố vấn; biết tên một lớp mình **không** phụ trách.

**Code sai (`vuln/A01-4`):** vô hiệu hóa kiểm quyền bằng thủ thuật `if False and ...`:
```python
    if requested_class:
        # VULN A01-4: mở ranh giới cố vấn -> xem được mọi lớp
        if False and not StudentProfile.is_class_assigned_to_advisor(requested_class, current_username):
            abort(403)
```
**Code đúng (`main`):**
```python
    if requested_class:
        if not StudentProfile.is_class_assigned_to_advisor(requested_class, current_username):
            abort(403)
    # ... decrypt_in_rows(results, 'id_card')  # giải mã CCCD có kiểm soát
```
- **Kịch bản khai thác:** cố vấn đổi tham số `?class_name=<lớp khác>`.
- **Hậu quả:** cố vấn xem được danh sách sinh viên (kèm PII) của **mọi lớp hành chính**, kể cả lớp không được phân công.
- **Cách vá & vì sao hiệu quả:** `main` gọi thật `is_class_assigned_to_advisor` (chỉ cho qua nếu lớp có sinh viên mà `advisor_email` trùng username cố vấn), quyền theo từng sinh viên dùng `is_student_assigned_to_advisor`; CCCD chỉ được giải mã **có kiểm soát** khi hiển thị qua `decrypt_in_rows`.

---

### 5.2. A03:2025 — Software Supply Chain Failures *(mới)*

> **Ý tưởng chung:** mã của nhóm an toàn chưa đủ — mọi dòng mã **người khác viết** mà ứng dụng tải về và chạy (thư viện Python, script CDN, image Docker, action CI) cũng là bề mặt tấn công. Phòng thủ là **ghim chính xác thứ mình tin** (phiên bản, mã băm) và **kiểm lại mỗi lần cài**.
>
> A03:2025 mở rộng hạng mục "Vulnerable and Outdated Components" (A06:2021): không chỉ thư viện **cũ có CVE**, mà cả thư viện **mới nhưng bị đầu độc**. Tức là "luôn cập nhật bản mới nhất" **không còn đồng nghĩa với an toàn**.

**Kết quả rà soát trên `main`:**

| Hạng mục | Kết quả | Đánh giá |
|---|---|---|
| Gói Python trong `src/requirements.txt` | **10/10** ghim `==` | ✅ |
| Thẻ `<script>` tải từ CDN | **6/6** template có `integrity` + `crossorigin`; **0** thẻ CDN thiếu SRI | ✅ |
| CSP giới hạn nguồn script | `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net` | ✅ (còn `unsafe-inline`) |
| Docker / CI cài từ file đã ghim | `Dockerfile` và GitHub Actions đều `pip install -r requirements*.txt` | ✅ |
| Ghim mã băm gói Python (`--require-hashes`) | Chưa có | ⚠️ còn thiếu |
| Quét CVE thư viện tự động (pip-audit, Dependabot) | Chưa có | ⚠️ còn thiếu |
| Image Docker và GitHub Actions | Ghim theo tag (`python:3.12-slim`, `actions/checkout@v4`), chưa theo digest/SHA | ⚠️ còn thiếu |

#### A03-1 · Script CDN không ghim phiên bản, không kiểm toàn vẹn (SRI)
- **Vị trí:** 6 template — `auth/login.html`, `auth/forgot_password.html`, `auth/onboarding.html`, `layouts/ui_macros.html`, `master/dashboard.html`, `student/dashboard.html` · **Mức độ:** 🔴 Nghiêm trọng (ảnh hưởng **mọi người dùng cùng lúc**)
- **Tiền đề:** kẻ tấn công kiểm soát được file trên CDN (chiếm tài khoản npm của tác giả, chiếm tên miền CDN như vụ polyfill.io, hoặc đầu độc bản phát hành).

**Code sai (bản lỗi giả định):**
```html
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@latest/dist/sweetalert2.all.min.js"></script>
```
**Code đúng (`main`, `auth/login.html:7`):**
```html
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11.10.5/dist/sweetalert2.all.min.js"
        integrity="sha256-+0Qf8IHMJWuYlZ2lQDBrF1+2aigIRZXEdSvegtELo2I="
        crossorigin="anonymous"></script>
```
- **Kịch bản khai thác (mô phỏng trên trang demo, tab A03):** file thư viện bị chèn thêm một đoạn lắng nghe sự kiện `submit`, gửi `username`, `password` và `document.cookie` sang máy chủ kẻ tấn công bằng `navigator.sendBeacon`. Nạn nhân mở `/login`, gõ mật khẩu, bấm Đăng nhập.
- **Hậu quả:** mã độc chạy **trong ngữ cảnh của EduFlaw** — đọc được mật khẩu đang gõ, CSRF token, nội dung trang (điểm, CCCD) — trên **trình duyệt của mọi người dùng** mở trang. CSP không chặn được vì `cdn.jsdelivr.net` là nguồn được phép. `@latest` còn khiến bản độc **tự động** được nạp ngay khi phát hành.
- **Cách vá & vì sao hiệu quả:**
  - **Ghim phiên bản** (`@11.10.5`) → không tự nhận bản mới.
  - **SRI** → trình duyệt tính SHA-256 của file tải về; khác giá trị ghim là **từ chối chạy** và báo `Failed to find a valid digest in the 'integrity' attribute … The resource has been blocked.` Mã băm nằm **trong repo của nhóm**, kẻ chiếm CDN không sửa được; tạo file độc trùng SHA-256 là bất khả thi.
  - **`crossorigin="anonymous"`** → bắt buộc để trình duyệt được đọc nội dung file khác nguồn mà so khớp.
  - Quy trình đổi phiên bản (ghi trong `CLAUDE.md`): lấy lại hash từ API `data.jsdelivr.com/v1/packages/npm/<gói>@<phiên bản>?structure=flat`, không tự tính từ file đang có trên máy.
- **Giới hạn của SRI:** SRI chống **bị sửa**, không chống **CDN sập** (trang mất hộp thoại/biểu đồ nhưng không bị chiếm). Muốn khả dụng cao hơn thì tự host file, vẫn giữ SRI.

#### A03-2 · Gói Python không ghim phiên bản
- **Vị trí:** `src/requirements.txt` · **Mức độ:** 🔴 Nghiêm trọng
- **Tiền đề:** một gói phụ thuộc (hoặc gói tên gần giống — *typosquatting*) bị đẩy bản độc lên PyPI.

**Code sai (bản lỗi giả định):**
```text
Flask
cryptography>=40
```
**Code đúng (`main`):**
```text
Flask==3.1.3
mysql-connector-python==26.7.0
pandas==3.0.6
openpyxl==3.1.5
xlrd==2.0.2
python-dotenv==1.2.4
Flask-WTF==1.3.0
waitress==3.0.2
cryptography==50.0.2
certifi==2026.7.22
```
- **Kịch bản khai thác (mô phỏng):** `pip install -r requirements.txt` trên máy chủ hoặc trong `docker build` kéo về bản mới nhất `Flask-99.0.0` (số phiên bản giả định) do kẻ tấn công đẩy lên; mã trong gói chạy **ngay lúc cài/import** với quyền của server.
- **Hậu quả:** đọc `.env` → lộ `SECRET_KEY` (rèn được cookie phiên, giải được HMAC OTP), `FIELD_ENCRYPTION_KEY` (giải mã CCCD), mật khẩu CSDL. Đây là kịch bản **xấu nhất** vì vượt qua mọi lớp phòng thủ ở tầng ứng dụng.
- **Cách vá & vì sao hiệu quả:** ghim `==` cho **toàn bộ 10 gói** → bản 99.0.0 không khớp và bị bỏ qua; nâng cấp trở thành **thay đổi có kiểm soát** (đọc changelog → đổi số → CI chạy lại 171 test → merge). `pip` cũng tự kiểm hash của file tải từ PyPI so với chỉ mục, nhưng chỉ ghim `--require-hashes` mới chặn được trường hợp chính phiên bản đó bị thay thế.

#### A03-3 · Quy trình build/CI không tái lập được
- **Vị trí:** `Dockerfile`, `.github/workflows/tests.yml` · **Mức độ:** 🟡 Trung bình
- **Rủi ro:** nếu image nền hoặc action CI không cố định, cùng một commit có thể build ra hai sản phẩm khác nhau; một action bị chiếm có thể đọc secret của CI.
- **Hiện trạng `main`:** `Dockerfile` copy `requirements.txt` rồi cài **trước** khi copy mã (cache layer, và chỉ cài đúng danh sách đã ghim); CI cài `requirements-dev.txt` (= `requirements.txt` + `pytest==9.1.1`) và chạy toàn bộ test trên **Ubuntu + Windows** mỗi lần push; CI không giữ secret thật (chỉ `SECRET_KEY` giả cho test).
- **Còn thiếu:** image `python:3.12-slim`, `mysql:8.4` và `actions/checkout@v4`, `actions/setup-python@v5` được ghim theo **tag** (có thể bị trỏ lại), chưa theo **digest/commit SHA**. Đây là hướng làm cứng tiếp theo (mục 8.4).


---

### 5.3. A07:2025 — Authentication Failures

#### A07-1 · Không giới hạn số lần đăng nhập sai (brute-force)
- **File:** `app/controllers/auth.py:15` · **Commit:** `ae8611e` · **Mức độ:** 🟠 Cao
- **Tiền đề:** không cần đăng nhập (chỉ cần một username để thử).

**Code sai (`vuln/A07-1`):**
```python
LOGIN_MAX_ATTEMPTS = 10**9  # VULN A07-1: thực tế không bao giờ khóa
```
**Code đúng (`main`):**
```python
LOGIN_MAX_ATTEMPTS = 5
```
- **Hậu quả:** ngưỡng khóa = 1 tỷ → thực tế không bao giờ đạt tới → kẻ tấn công thử mật khẩu **không giới hạn**.
- **Cách vá & vì sao hiệu quả:** `main` đặt `= 5`; sau 5 lần sai trả **429**, khóa tạm theo **cả IP lẫn tài khoản**. Trạng thái khóa lưu trong CSDL (`SecurityState`, tăng bằng `INSERT ... ON DUPLICATE KEY UPDATE` nguyên tử) nên đúng với nhiều worker và không mất khi restart.
- **Bằng chứng (`evidence/a07_1_bruteforce.log`):** lần 1–3 HTTP 200 (sai mật khẩu), lần 4 báo sắp khóa, **lần 5–7 HTTP 429 (KHÓA)** → phòng thủ brute-force hoạt động.

#### A07-2 · Tiết lộ sự tồn tại tài khoản/Gmail (account enumeration)
- **File:** `app/controllers/auth.py:409` · **Commit:** `2285d23` · **Mức độ:** 🟡 Trung bình
- **Tiền đề:** không cần đăng nhập.

**Code sai (`vuln/A07-2`):**
```python
        # VULN A07-2: lộ sự tồn tại tài khoản/Gmail
        return jsonify({'success': False, 'message': 'Tài khoản hoặc Gmail không tồn tại.'}), 404
```
**Code đúng (`main`):**
```python
        # Trả cùng một phản hồi dù khớp hay không, để tránh dò tài khoản
        return jsonify({'success': True, 'message': GENERIC_OTP_SENT_MESSAGE})
```
- **Hậu quả:** phản hồi khi không khớp khác hẳn khi khớp → kẻ tấn công **dò ra tài khoản nào có thật** và Gmail nào đã liên kết (phục vụ phishing, brute-force có mục tiêu).
- **Cách vá & vì sao hiệu quả:** `main` luôn trả **cùng một phản hồi** (`success: True`, `GENERIC_OTP_SENT_MESSAGE`) bất kể khớp hay không.
- **Bằng chứng (`evidence/a07_2_otp_enum.log`):** tài khoản thật (email sai) và tài khoản giả đều trả **HTTP 200, success=True, cùng message, t≈370ms** → không thể enumerate.

#### A07-3 · Không thu hồi phiên cũ khi đổi mật khẩu
- **File:** `app/models/user_model.py:89` · **Commit:** `50a1e1e` · **Mức độ:** 🟠 Cao
- **Tiền đề:** 1 tài khoản; giữ một phiên đã đăng nhập ở cửa sổ A.

**Code sai (`vuln/A07-3`):**
```python
                if not (user and user['is_active'] and user['role'] == role):
                    return False
                # VULN A07-3: không thu hồi phiên khi đổi mật khẩu
                return True
```
**Code đúng (`main`):**
```python
                if password_fp is None:
                    return True
                return hmac.compare_digest(password_fp, cls.password_fingerprint(user['password']))
```
- **Hậu quả:** `is_account_active` luôn `return True`, bỏ qua `password_fp`. Vì session nằm trong cookie, **đổi/quên/reset mật khẩu đều không vô hiệu hóa phiên cũ** — kẻ đã chiếm cookie vẫn truy cập mãi.
- **Cách vá & vì sao hiệu quả:** `main` so `password_fp` trong session với vân tay mật khẩu hiện tại bằng `hmac.compare_digest` (so sánh chống timing attack). Đổi mật khẩu → vân tay đổi → **mọi phiên cũ lập tức mất hiệu lực**.

---

### 5.4. A10:2025 — Mishandling of Exceptional Conditions *(mới)*

> **Ý tưởng chung:** lỗi là chuyện **chắc chắn xảy ra** — CSDL ở xa timeout, người dùng gửi dữ liệu lạ, tệp quá lớn. Câu hỏi bảo mật là: **khi lỗi xảy ra, hệ thống đóng lại hay mở ra?** Ba nguyên tắc: (1) **fail-closed** — không xác minh được thì từ chối; (2) **người dùng thấy câu chung, log giữ chi tiết**; (3) **không để lại trạng thái dở dang**.

#### A10-1 · Fail-open khi kiểm tra tài khoản gặp lỗi CSDL
- **File:** `app/models/user_model.py:80` (`User.is_account_active`), gọi từ `app/utils/decorators.py:25` (`role_required`) · **Mức độ:** 🟠 Cao
- **Tiền đề:** kẻ tấn công còn giữ cookie phiên của một tài khoản **đã bị Master khóa** (`is_active = 0`) hoặc **đã đổi mật khẩu**; có thể làm CSDL quá tải/timeout (dội request nặng, hoặc lợi dụng lúc CSDL ở xa chập chờn).

**Code sai (bản lỗi giả định):**
```python
    @classmethod
    def is_account_active(cls, user_id, role, password_fp=None):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                ...
        except Exception:
            return True   # lỗi thì coi như hợp lệ
```
**Code đúng (`main`):**
```python
    @classmethod
    def is_account_active(cls, user_id, role, password_fp=None):
        """... Lỗi CSDL => từ chối."""
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT is_active, role, password FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not (user and user['is_active'] and user['role'] == role):
                    return False
                if password_fp is None:
                    return True
                return hmac.compare_digest(password_fp, cls.password_fingerprint(user['password']))
        except Exception:
            return False
```
và trong `role_required`:
```python
            if not User.is_account_active(session.get('user_id'), user_role, session.get('pw_fp', '')):
                session.clear()
                return redirect('/login')
```
- **Kịch bản khai thác (mô phỏng trên trang demo, tab A10 — thí nghiệm 2):** CSDL trả `OperationalError: 2013 Lost connection to MySQL server during query` → bản lỗi rơi vào `except` và `return True` → `GET /student/grades` trả **200** cho tài khoản đã bị khóa.
- **Hậu quả:** **lỗi biến thành quyền**. Mọi cơ chế thu hồi — khóa tài khoản, thu hồi phiên khi đổi mật khẩu (`pw_fp`, A07-3) — đều có thể bị vô hiệu chỉ bằng cách khiến CSDL lỗi. Đây là ví dụ điển hình cho lý do OWASP tách A10 thành hạng mục riêng: lỗ hổng **không nằm ở nhánh chạy bình thường**, nên test "đường vui" không bắt được.
- **Cách vá & vì sao hiệu quả:** `main` trả `False` trong mọi nhánh lỗi; decorator `session.clear()` và về `/login`. Kẻ tấn công **không thể biến lỗi thành quyền**; tệ nhất là người dùng thật phải đăng nhập lại khi CSDL chập chờn — một đánh đổi khả dụng **có chủ đích**.
- **Kiểm thử:** `tests/test_session_revocation.py` kiểm các nhánh tài khoản bị khóa và phiên bị thu hồi; **chưa có test riêng cho nhánh lỗi CSDL** (giả lập `get_db_cursor` ném exception) — đề xuất ở mục 8.4.

#### A10-2 · Lộ stack trace và chi tiết lỗi cho người dùng
- **File:** `app/utils/error_pages.py`, `app/controllers/admin.py` (`/admin/grades/api/auto-save`) · **Mức độ:** 🟠 Cao
- **Tiền đề:** một tài khoản giảng viên (hoặc bất kỳ endpoint nào nhận dữ liệu); không cần quyền đặc biệt.

**Code sai (bản lỗi giả định):** không bắt lỗi chuyển kiểu, để ngoại lệ rơi ra trang lỗi mặc định/debug:
```python
    parsed_value = float(raw_value)          # 'abc' -> ValueError -> HTTP 500 + traceback
    Grade.save_single_score(grade_id, field_name, parsed_value, user_id)
```
**Code đúng (`main`):** kiểm tra đầu vào trả **400** với thông báo chung, và handler 500 chỉ ghi log:
```python
    if not grade_id.isdecimal() or field_name not in allowed_fields:
        return jsonify({'success': False, 'message': 'Dữ liệu đầu điểm không hợp lệ.'}), 400
    ...
        try:
            parsed_value = float(raw_value)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Điểm số phải là số hợp lệ.'}), 400
        if not Grade.is_valid_score(parsed_value):
            return jsonify({'success': False, 'message': 'Điểm phải nằm trong khoảng 0–10.'}), 400
```
```python
    @app.errorhandler(InternalServerError)
    def handle_internal_error(error):
        # Chi tiết lỗi chỉ ghi log phía máy chủ, không hiển thị cho người dùng
        app.logger.exception('Lỗi máy chủ khi xử lý %s %s', request.method, request.path)
        return _error_response(500, *ERROR_MESSAGES[500])
```
- **Kịch bản khai thác (mô phỏng trên trang demo, tab A10 — thí nghiệm 1):** gửi `value` = `abc`, `nan`, `1e999`, `15`. Bản lỗi trả HTTP 500 kèm traceback chứa **đường dẫn máy chủ**, tên file và số dòng, **câu SQL `UPDATE grades SET score_thi = …`**, tên cột, phiên bản Werkzeug/Python, tên máy CSDL; giá trị `15` còn được **lưu luôn** vì không kiểm khoảng.
- **Hậu quả:** kẻ tấn công có **bản đồ nội bộ** (cấu trúc bảng, đường dẫn, phiên bản thư viện để tra CVE) cho bước tấn công tiếp theo. Trang debug Werkzeug còn tệ hơn: cho **chạy mã tùy ý** (xem Phụ lục A05-1); fuzzer của nhóm từng phát hiện `/console` còn bật trên bản lỗi.
- **Cách vá & vì sao hiệu quả:**
  - **Kiểm tra đầu vào trước** → lỗi dự đoán được trả **400** với câu tiếng Việt cố định, không phụ thuộc nội dung exception.
  - **Lỗi không dự đoán được** → handler 500 trả *"Hệ thống gặp sự cố"*; với `/api/` trả JSON `{success: false, message}`; chi tiết `logger.exception` kèm method + path chỉ nằm trong **log máy chủ**.
  - Thống nhất mã lỗi 400/403/404/405/413/429/500 cho cả trang HTML lẫn API.
- **Bằng chứng:** `fuzz_input.py` bơm **23 payload dị dạng** vào bản `main` → **0 lỗi 5xx** (mục 6.1).

#### A10-3 · Để lại giao dịch dở dang khi lỗi giữa chừng
- **File:** `app/utils/db_helper.py` (`get_db_cursor`), `db.py` (`SafePooledConnection`) · **Mức độ:** 🟡 Trung bình
- **Rủi ro:** EduFlaw dùng **một kết nối chung cho mỗi request** và **pool tắt `pool_reset_session`** (với TiDB, mỗi lần reset tốn ~375 ms). Nếu lỗi xảy ra giữa lúc nhập điểm cả lớp mà không rollback, kết nối trả về pool **còn transaction mở** → request **của người khác** có thể commit nhầm nửa bảng điểm, hoặc đọc snapshot cũ.

**Code đúng (`main`):**
```python
    except Exception as err:
        # Rollback với mọi lỗi (không chỉ lỗi CSDL): kết nối được dùng tiếp trong request,
        # nên thay đổi dở dang không được để lại cho khối commit sau
        if connection is not None and commit:
            try:
                connection.rollback()
            except mysql.connector.Error:
                pass
```
```python
class SafePooledConnection:
    def close(self):
        try:
            if self._connection.in_transaction:
                self._connection.rollback()
        except mysql.connector.Error:
            pass
        finally:
            self._connection.close()
```
- **Vì sao hiệu quả:** rollback ở **hai tầng** — trong khối ghi (mọi exception, không chỉ lỗi CSDL) và lúc trả kết nối về pool. Nhập điểm theo lớp còn gom vào **một câu `UPDATE … CASE`** và một lần `executemany` cho nhật ký, nên hoặc lưu cả lớp, hoặc không lưu gì. Auto-save từng ô khóa dòng bằng `FOR UPDATE` để hai ô lưu gần như cùng lúc không đè nhau.

#### A10-4 · Không giới hạn tài nguyên đầu vào
- **File:** `config.py` (`MAX_CONTENT_LENGTH`), `app/services/student_import_service.py` (`MAX_ROWS`) · **Mức độ:** 🟡 Trung bình
- **Rủi ro:** tệp import khổng lồ hoặc hàng trăm nghìn dòng làm cạn RAM/CPU (pandas đọc cả tệp vào bộ nhớ), khiến server rơi vào trạng thái ngoại lệ hàng loạt.
- **Code đúng (`main`):** `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` → request quá 16 MB nhận **413** với trang lỗi tiếng Việt *"Tệp quá lớn"*; import tối đa **5000 dòng** mỗi lần (`Mỗi lần chỉ được import tối đa 5000 sinh viên.`); ghi danh tối đa 500 sinh viên mỗi lần.
- **Vì sao hiệu quả:** từ chối **trước khi** xử lý, với thông báo rõ ràng — tình huống bất thường được biến thành một nhánh xử lý bình thường có kiểm soát.


---

## 6. BẰNG CHỨNG FUZZING, RÀ SOÁT & DEMO

### 6.1. Fuzzing dò nội dung & đầu vào

Số liệu từ fuzzer tự viết (Python, chạy localhost); log gốc chụp trên slide 11:

| Chỉ số | Giá trị | Ý nghĩa | Nhóm |
|---|---|---|---|
| Đường dẫn đã dò (`fuzz_content.py`) | **69** | Quét không gian URL | — |
| Endpoint trả 404 | **29** | Phần lớn không tồn tại | — |
| Phát hiện trên bản lỗi | **/console** còn bật | Trang debug hiện stack trace và cho chạy mã khi có ngoại lệ | A10 (và A05-1 phụ lục) |
| Payload dị dạng (`fuzz_input.py`) | **23** | Chuỗi rỗng, cực dài, ký tự SQL, script, JSON hỏng… | A10 |
| Lỗi 5xx trên `main` | **0** | Mọi đầu vào lạ đều được xử lý có kiểm soát | **A10** |
| Phản hồi chậm 7.4 s (1 lần) | Không tái hiện | **Dương tính giả**, đã loại sau khi chạy lại | — |

### 6.2. Dội đăng nhập: trước và sau khi vá (A07-1)

Cùng một kịch bản dội sai mật khẩu, khác nhau **đúng một dòng** `LOGIN_MAX_ATTEMPTS`:

| Phiên bản | Kết quả |
|---|---|
| **Bản chưa vá** (`vuln/A07-1`) | 12/12 lần đều **không bị khóa** — brute-force vô hạn. |
| **Bản đã vá** (`main`) | Từ lần **5 trả HTTP 429** (lần 4 đã báo sắp khóa) — khóa theo IP & tài khoản. |

**Kiểm chứng CSDL:** `SELECT throttle_key, attempts, lockout_until FROM login_attempts;` — log gốc `pentest/evidence/a07_1_bruteforce.log`.

### 6.3. Rà soát chuỗi cung ứng (A03)

| Kiểm tra | Lệnh (chạy trong `src/`) | Kết quả |
|---|---|---|
| Gói Python đã ghim | `grep -c "==" requirements.txt` | 10/10 dòng |
| Template có SRI | `grep -rl 'integrity=' app/templates` | 6 tệp |
| Thẻ CDN thiếu SRI | `grep -rn '<script src="http' app/templates \| grep -v integrity` | 0 |
| CSP giới hạn nguồn script | `grep -n "script-src" app/__init__.py` | `'self' 'unsafe-inline' https://cdn.jsdelivr.net` |

### 6.4. Trang demo mô phỏng

Trang **`demo/index.html`** (một tệp HTML, chạy offline; có bản online riêng tư) mô phỏng 4 nhóm với công tắc **Có lỗ hổng / Đã vá**. Hướng dẫn và kịch bản bấm từng bước: `demo/README.md`.

| Tab | Bản lỗi | Bản vá |
|---|---|---|
| **A01** | Đổi `student_id` → đọc điểm + CCCD người khác, HTTP 200 | Tham số bị bỏ qua, chỉ trả dữ liệu của mình |
| **A03** | Thư viện bị sửa gửi email + mật khẩu + cookie ra ngoài; pip kéo `Flask-99.0.0` độc | Trình duyệt tính **SHA-256 thật** (Web Crypto), không khớp → chặn; pip chỉ cài `Flask==3.1.3` |
| **A07** | 12 lần thử, 0 lần khóa, đoán trúng ở lần 12 | 4 lần sai, từ lần 5 trả 429, kể cả mật khẩu đúng |
| **A10** | Lộ traceback (đường dẫn, SQL, tên máy CSDL); tài khoản bị khóa vẫn vào được khi CSDL lỗi | 400 với câu chung, chi tiết vào log; lỗi CSDL → `session.clear()` → 302 `/login` |

> Trang demo là **mô phỏng**: không gọi tới EduFlaw hay CSDL nào, dữ liệu đều giả; thông báo lỗi và tên hàm ở chế độ "Đã vá" được chép nguyên văn từ `main`. Bằng chứng chạy thật là log trong `pentest/evidence/` và các nhánh `vuln/*`.

---

## 7. TỔNG HỢP CÁC LỚP PHÒNG THỦ

| Nhóm OWASP 2025 | Lớp phòng thủ trong EduFlaw |
|---|---|
| **A01 — Kiểm soát truy cập** | Danh tính lấy từ **phiên** (không tin tham số client → chặn IDOR); kiểm **quyền sở hữu ở từng request**, sai → 403; `role_required` so vai trò; cố vấn kiểm `is_class_assigned_to_advisor`. |
| **A03 — Chuỗi cung ứng** | **Ghim `==`** 10 gói Python; **ghim phiên bản + SRI + crossorigin** cho mọi script CDN; CSP chỉ cho script từ `self` và jsDelivr; Docker và CI cài đúng danh sách đã ghim, CI chạy 171 test trên 2 hệ điều hành mỗi lần push. |
| **A07 — Xác thực & phiên** | **Khóa brute-force 5 lần** theo IP & tài khoản (429), lưu trong CSDL; **chống dò tài khoản** (phản hồi đồng nhất); **thu hồi phiên** khi đổi mật khẩu (`pw_fp`). |
| **A10 — Xử lý ngoại lệ** | **Fail-closed** (`is_account_active` lỗi → `False` → hủy phiên); kiểm đầu vào trả **400**; handler 500 **chỉ ghi log**; **rollback hai tầng**; giới hạn **16 MB** (413) và **5000 dòng** import. |

### Bảng tổng hợp 14 lỗ hổng trọng tâm

| Mã | Tên ngắn | Vị trí | Mức độ | Mấu chốt phòng thủ ở `main` |
|---|---|---|---|---|
| A01-1 | IDOR tin `student_id` | `student.py:51` | 🟠 Cao | Danh tính từ `session['user_id']` |
| A01-2 | Vượt quyền GV sửa điểm | `admin.py:414` | 🟠 Cao | Kiểm `lecturer_id != user_id` → 403 |
| A01-3 | Leo thang vai trò | `decorators.py:14` | 🔴 Nghiêm trọng | `role_required` so vai trò → điều hướng |
| A01-4 | Vượt quyền cố vấn | `admin.py:42` | 🟠 Cao | `is_class_assigned_to_advisor` + giải mã có kiểm soát |
| A03-1 | Script CDN không SRI | 6 template | 🔴 Nghiêm trọng | Ghim `@11.10.5` + `integrity` + `crossorigin` |
| A03-2 | Gói Python không ghim | `requirements.txt` | 🔴 Nghiêm trọng | `==` cho 10/10 gói |
| A03-3 | Build/CI không tái lập | `Dockerfile`, CI | 🟡 Trung bình | Cài từ file đã ghim; CI chạy test mỗi push |
| A07-1 | Không khóa brute-force | `auth.py:15` | 🟠 Cao | `LOGIN_MAX_ATTEMPTS = 5` + khóa IP/tài khoản |
| A07-2 | Dò tài khoản qua send-otp | `auth.py:409` | 🟡 Trung bình | Luôn trả `GENERIC_OTP_SENT_MESSAGE` |
| A07-3 | Không thu hồi phiên | `user_model.py:89` | 🟠 Cao | So `pw_fp` bằng `hmac.compare_digest` |
| A10-1 | Fail-open khi CSDL lỗi | `user_model.py:80` | 🟠 Cao | `except: return False` → `session.clear()` |
| A10-2 | Lộ stack trace | `error_pages.py`, auto-save | 🟠 Cao | 400 với câu chung; 500 chỉ ghi log |
| A10-3 | Giao dịch dở dang | `db_helper.py`, `db.py` | 🟡 Trung bình | Rollback mọi exception + khi trả pool |
| A10-4 | Không giới hạn tài nguyên | `config.py`, import | 🟡 Trung bình | 16 MB → 413; tối đa 5000 dòng |

---

## 8. KẾT QUẢ, BÀI HỌC, HẠN CHẾ & HƯỚNG PHÁT TRIỂN

### 8.1. Kết quả đạt được

- **Kiểm thử:** áp dụng hộp trắng kết hợp mô phỏng hộp xám/đen; thủ công (gồm rà chuỗi cung ứng) và fuzzing.
- **Khai thác:** theo **OWASP Top 10:2025**, gồm cả **hai hạng mục mới** A03 và A10: 7 lỗ hổng A01/A07 khai thác thật trên nhánh `vuln/*`; 7 lỗ hổng A03/A10 rà soát trên `main` và mô phỏng trên trang demo; thêm **6 lỗ hổng A02/A05** (bản 2021) ở phụ lục.
- **Phòng thủ:** mọi lỗ hổng đều có bản vá trên `main`; bộ **171 test pytest** chạy trên CI mỗi lần push.
- **Trình bày:** trang demo `demo/index.html` để thầy và các bạn tự bấm thử từng lỗ hổng.

### 8.2. Bài học

- **Bảo mật là một vòng đời:** kiểm **ở server mỗi request**, vá **từ gốc** kèm test hồi quy.
- **Không tin dữ liệu từ client:** danh tính và quyền suy ra từ phiên đã xác thực, không từ tham số URL hay giao diện.
- **Không tin thứ mình không viết:** thư viện và CDN cũng là bề mặt tấn công — ghim phiên bản, ghim mã băm, cập nhật có kiểm soát.
- **Lỗi thì đóng, không mở:** mọi nhánh `except` phải trả về trạng thái **an toàn**; người dùng thấy câu chung, log giữ chi tiết.
- **Hiểu cơ chế, không chỉ "đã chặn":** với mỗi bản vá nhóm giải thích *vì sao* hiệu quả (SHA-256 kháng va chạm, `hmac.compare_digest` chống timing, rollback hai tầng…).
- **Phòng thủ chiều sâu:** SRI + CSP, khóa đăng nhập + thu hồi phiên + fail-closed bổ trợ nhau, không dựa vào một hàng rào duy nhất.

### 8.3. Hạn chế

- **Fuzzer còn cơ bản** — tự viết bằng urllib, chưa dùng scanner chuyên dụng (Burp Suite, ffuf, AFL++); hai script `fuzz_content.py`, `fuzz_input.py` **chưa được đưa vào repo**, chỉ còn ảnh log.
- **A03 và A10 chưa có nhánh `vuln/*`** để khai thác trên ứng dụng thật như A01/A07; được chứng minh bằng rà soát mã, fuzzing đầu vào và mô phỏng.
- **Chuỗi cung ứng chưa làm cứng hết:** chưa `--require-hashes`, chưa pip-audit/Dependabot, image Docker và GitHub Actions ghim theo tag chứ chưa theo digest/SHA; CSP còn `'unsafe-inline'`.
- **Chưa có test riêng** cho nhánh lỗi CSDL của `is_account_active`.
- **Phạm vi lab:** chỉ chạy `localhost`, dữ liệu seed giả; chưa kiểm thử tải và hạ tầng.

### 8.4. Hướng phát triển

- **A03:** thêm `pip-audit` và Dependabot vào CI; sinh `requirements.txt` có hash (`pip-compile --generate-hashes`) và cài bằng `--require-hashes`; ghim `actions/*` theo commit SHA và image Docker theo digest; tạo SBOM; bỏ `'unsafe-inline'` khỏi CSP bằng nonce.
- **A10:** test giả lập `get_db_cursor` ném exception cho mọi hàm kiểm quyền; kiểm thử hỗn loạn (ngắt CSDL giữa request) để chắc mọi nhánh lỗi đều fail-closed; cảnh báo khi tỷ lệ lỗi 500 tăng đột biến.
- Đưa script fuzzer vào repo và chạy định kỳ; tích hợp scanner chuyên dụng.
- Bổ sung **MFA**, rate-limit tinh hơn (backoff lũy tiến), kiểm thử sâu XSS/CSRF và kiểm thử tải.
- Tạo nhánh `vuln/A03-*`, `vuln/A10-*` để khai thác trên ứng dụng thật.

---

## 9. PHỤ LỤC

### 9.1. Các lỗ hổng A02 & A05 (bản 2021) đã kiểm thử ngoài trọng tâm

Trước khi chuyển sang chuẩn 2025, nhóm đã khai thác và vá **6 lỗ hổng** thuộc A02:2021 Cryptographic Failures (nay là **A04:2025**) và A05:2021 Security Misconfiguration (nay là **A02:2025**). Các bản vá này **vẫn có trên `main`**; nhánh đối chứng `vuln/A02-*`, `vuln/A05-*` vẫn được giữ.

#### 9.1.1. A02:2021 — Cryptographic Failures (nay là A04:2025)

##### A02-1 · Lưu CCCD (PII) dạng rõ, không mã hóa trường
- **File:** `app/models/profile_model.py:144` · **Commit:** `53cf68d` · **Mức độ:** 🟠 Cao
- **Tiền đề:** quyền sửa hồ sơ (master/cố vấn) để ghi một CCCD; truy cập CSDL để kiểm chứng.

**Code sai (`vuln/A02-1`):**
```python
                if 'id_card' in valid_data:
                    valid_data['id_card'] = valid_data['id_card']  # VULN A02-1: lưu CCCD dạng rõ
```
**Code đúng (`main`):**
```python
                if 'id_card' in valid_data:
                    valid_data['id_card'] = encrypt_field(valid_data['id_card'])  # mã hóa AES-GCM
```
- **Hậu quả:** gán `id_card = id_card` không mã hóa gì — số CCCD lưu thẳng plaintext vào CSDL; rò rỉ CSDL là **lộ ngay toàn bộ CCCD**.
- **Cách vá & vì sao hiệu quả:** `main` mã hóa trường bằng `encrypt_field` (`field_crypto.py:56`) — **AES-GCM**, khóa dẫn xuất qua HKDF, nonce ngẫu nhiên mỗi lần, có tiền tố nhận dạng (`enc:v1:`). Đọc ra thì `decrypt_field` giải mã; bản mã trong CSDL **vô nghĩa nếu không có `FIELD_ENCRYPTION_KEY`** (khóa để ngoài CSDL).

##### A02-2 · Lưu mật khẩu dạng plaintext (không băm)
- **File:** `app/models/user_model.py:164,193` (+ `auth.py:119`) · **Commit:** `a9077bc` · **Mức độ:** 🔴 Nghiêm trọng
- **Tiền đề:** 1 tài khoản để đổi mật khẩu; truy cập CSDL để kiểm chứng.

**Code sai (`vuln/A02-2`):**
```python
                hashed_password = new_password  # VULN A02-2: lưu mật khẩu dạng thường
                cursor.execute("UPDATE users SET password = %s ... WHERE id = %s", (hashed_password, ...))
```
**Code đúng (`main`):**
```python
                hashed_password = generate_password_hash(new_password)   # băm một chiều
                ...
                if not User.is_password_hashed(user.password):
                    if User.upgrade_legacy_password(user.id, password):   # nâng cấp plaintext cũ
                        session['pw_fp'] = User.current_password_fingerprint(user.id)
```
- **Hậu quả:** mật khẩu người dùng lưu đúng dạng chữ; ai đọc được bảng `users` (rò rỉ CSDL, backup, admin tò mò) **thấy ngay mật khẩu thật của mọi người** — rủi ro lan sang dịch vụ khác do người dùng hay tái sử dụng mật khẩu.
- **Cách vá & vì sao hiệu quả:** `main` dùng `generate_password_hash` (Werkzeug — scrypt/pbkdf2) ở mọi chỗ đặt/đổi mật khẩu → chỉ lưu **hash một chiều**, không khôi phục được. Khi gặp mật khẩu cũ chưa băm, `main` tự `upgrade_legacy_password` để dần loại bỏ plaintext tồn đọng.

##### A02-3 · Lộ mã OTP ra response của API
- **File:** `app/controllers/auth.py:428` · **Commit:** `0a5da4b` · **Mức độ:** 🔴 Nghiêm trọng
- **Tiền đề:** biết username + Gmail cá nhân đã liên kết của nạn nhân (không cần đăng nhập).

**Code sai (`vuln/A02-3`):**
```python
        # VULN A02-3: lộ mã OTP ra response
        return jsonify({'success': True, 'message': GENERIC_OTP_SENT_MESSAGE, 'otp': otp_code})
```
**Code đúng (`main`):**
```python
        # Không bao giờ trả mã OTP về client, kể cả ở chế độ mô phỏng
        return jsonify({'success': True, 'message': GENERIC_OTP_SENT_MESSAGE})
```
- **Hậu quả:** kẻ tấn công chỉ cần gọi API gửi OTP rồi **đọc mã ngay trong phản hồi**, không cần truy cập Gmail nạn nhân → chiếm tài khoản qua "quên mật khẩu".
- **Cách vá & vì sao hiệu quả:** `main` chỉ trả thông báo chung, **không bao giờ gửi mã về client**; mã chỉ đến hộp thư Gmail. Phía máy chủ chỉ lưu **băm HMAC** của OTP (`token_service.py` `_hash_otp`, dùng `SECRET_KEY`), nên lộ CSDL cũng không đọc ngược ra mã.


#### 9.1.2. A05:2021 — Security Misconfiguration (nay là A02:2025)

##### A05-1 · Bật Werkzeug debugger (nguy cơ RCE)
- **File:** `run.py` · **Commit:** `fe6133d` · **Mức độ:** 🔴 Nghiêm trọng
- **Tiền đề:** truy cập được app đang bật debug và kích được một lỗi chưa bắt.

**Code sai (`vuln/A05-1`):**
```python
    # VULN A05-1: bật Werkzeug debugger (RCE nếu lộ)
    app.run(host='127.0.0.1', port=..., debug=True)
```
**Code đúng (`main`):**
```python
    app.run(host=os.getenv('HOST') or '127.0.0.1', port=int(os.getenv('PORT') or 5000))
```
- **Hậu quả:** `debug=True` bật console gỡ lỗi tương tác — khi có lỗi 500, trang debug cho **chạy mã Python tùy ý** ngay trên trình duyệt. Nếu server lộ ra mạng → **RCE**, chiếm máy chủ.
- **Cách vá & vì sao hiệu quả:** `main` không bật debug; lỗi 500 xử lý qua `register_error_handlers` — chỉ **ghi log**, trả trang lỗi chung, không lộ stack trace. Production còn được `_validate_production_config` kiểm tra cấu hình bắt buộc trước khi chạy.

##### A05-2 · Thiếu `SECRET_KEY` vẫn chạy với khóa đoán được
- **File:** `app/__init__.py:50` · **Commit:** `6b28eac` · **Mức độ:** 🔴 Nghiêm trọng
- **Tiền đề:** biết/đoán khóa mặc định (`dev-insecure-key`) — hằng số công khai trong mã.

**Code sai (`vuln/A05-2`):**
```python
    # VULN A05-2: bỏ kiểm thiếu SECRET_KEY -> chạy với khóa đoán được
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-insecure-key'  # KHÔNG an toàn
```
**Code đúng (`main`):**
```python
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('Thiếu SECRET_KEY: hãy đặt SECRET_KEY trong file .env.')
```
- **Hậu quả:** cookie session ký bằng khóa công khai → kẻ tấn công **tự rèn cookie** (đặt `role=master`, đổi `user_id`) đăng nhập thành bất kỳ ai, **không cần mật khẩu**. CSRF token và HMAC của OTP/`pw_fp` cũng mất tác dụng vì đều phái sinh từ khóa này.
- **Cách vá & vì sao hiệu quả:** `main` **dừng khởi động ngay** (`raise RuntimeError`) nếu thiếu `SECRET_KEY` → buộc đặt khóa bí mật thật. Nguyên tắc **fail-fast**: lỗi lộ ra lúc khởi động chứ không âm thầm chạy bằng khóa yếu.

##### A05-3 · Content-Security-Policy tối thiểu (mất phòng thủ XSS)
- **File:** `app/__init__.py:76` · **Commit:** `38c4659` · **Mức độ:** 🟡 Trung bình
- **Tiền đề:** không cần đăng nhập (chỉ cần xem header response).

**Code sai (`vuln/A05-3`):**
```python
    # VULN A05-3: CSP tối thiểu, không có script-src/default-src
    content_security_policy = "frame-ancestors 'none'"
```
**Code đúng (`main`):**
```python
    content_security_policy = '; '.join((
        "default-src 'self'", "base-uri 'self'", "object-src 'none'",
        "frame-ancestors 'none'", "form-action 'self'",
        "img-src 'self' data: https:", "font-src 'self' data:",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "connect-src 'self'",
    ))
```
- **Hậu quả:** CSP chỉ còn `frame-ancestors 'none'`, **không giới hạn nguồn script** — nếu có lỗ XSS, trình duyệt sẽ nạp script từ **host lạ bất kỳ**. Lỗ hổng này không tự gây hại nhưng **khuếch đại** mọi lỗ XSS.
- **Cách vá & vì sao hiệu quả:** `main` khai báo CSP đầy đủ; đặc biệt `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net` chỉ cho nạp script từ chính site và CDN đã ghim → dù lỡ có XSS, script host lạ vẫn bị chặn.


#### Bảng tóm tắt 6 lỗ hổng phụ lục

| Mã | Tên ngắn | File:dòng | Mức độ | Mấu chốt phòng thủ ở `main` |
|---|---|---|---|---|
| A02-1 | CCCD lưu dạng rõ | `profile_model.py:144` | 🟠 Cao | `encrypt_field` (AES-GCM) |
| A02-2 | Mật khẩu plaintext | `user_model.py:164,193` | 🔴 Nghiêm trọng | `generate_password_hash` + nâng cấp cũ |
| A02-3 | Lộ OTP ra response | `auth.py:428` | 🔴 Nghiêm trọng | Không trả OTP; lưu băm HMAC |
| A05-1 | Bật Werkzeug debugger | `run.py` | 🔴 Nghiêm trọng | Tắt debug; 500 chỉ ghi log |
| A05-2 | SECRET_KEY đoán được | `__init__.py:50` | 🔴 Nghiêm trọng | Thiếu → `raise RuntimeError` |
| A05-3 | CSP tối thiểu | `__init__.py:76` | 🟡 Trung bình | CSP đầy đủ (`default-src`/`script-src`) |

**Kiểm chứng CSDL sau khi vá (A02):** cột `password` là chuỗi băm scrypt/pbkdf2; cột `id_card` là chuỗi mã hóa có tiền tố `enc:v1:…`. **Kiểm tra header (A05-3):** `pentest/a05_3_headers.py`, log `pentest/evidence/a05_3_headers.log`.

### 9.2. Danh mục script PoC

| Script | Lỗ hổng | Cần đăng nhập? |
|---|---|---|
| `pentest/a07_1_bruteforce.py` | A07-1 | Không |
| `pentest/a07_2_otp_enum.py` | A07-2 | Không |
| `pentest/a01_3_role_escalation.py` | A01-3 | Có (student) |
| `pentest/a05_3_headers.py` | A05-3 (phụ lục) | Không |

### 9.3. Tài khoản demo (dữ liệu seed giả — lab)

> Toàn bộ là dữ liệu sinh tự động bằng `--seed 42`, **không phải thông tin thật**. Mật khẩu tạm hết hiệu lực sau khi onboarding; file gốc đã **gitignore**, không đưa vào báo cáo.

| Vai trò | Tài khoản | Ghi chú |
|---|---|---|
| Sinh viên 1 | `b24dcat001@eduflaw.com` | Lớp D24CQAT01 |
| Sinh viên 2 | `b24dcat002@eduflaw.com` | Cùng lớp (dùng cho IDOR) |
| GV chủ lớp | `gv.001@eduflaw.com` | Dạy lớp id=243198 |
| GV kẻ tấn công | `gv.002@eduflaw.com` | Dùng cho A01-2 |

### 9.4. Lệnh đọc đối chứng code (chỉ-đọc, an toàn)

```bash
git show vuln/A01-1:src/app/controllers/student.py
git show main:src/app/controllers/student.py
```

### 9.5. Tài liệu liên quan trong repo

- `NOI-DUNG-THUYET-TRINH.md` — lời dẫn thuyết trình theo từng slide (khớp `EduFlaw-OWASP2025.pptx`).
- `GIAI-THICH-KIEN-THUC-VA-QA.md` — kiến thức nền & ngân hàng câu hỏi.
- `demo/index.html`, `demo/README.md` — trang demo và kịch bản demo.
- `pentest/GIAI-THICH-CODE-VULN-VS-MAIN.md`, `pentest/HUONG-DAN-DEMO-DAY-DU.md` — đối chứng code và hướng dẫn demo trên nhánh `vuln/*`.

---

*Báo cáo kết thúc. Mọi hoạt động khai thác trong tài liệu này chỉ nhằm mục đích học tập, thực hiện trên môi trường lab cô lập của nhóm với dữ liệu giả.*
