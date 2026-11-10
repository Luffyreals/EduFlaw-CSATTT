# Hướng dẫn chạy EduFlaw

Tài liệu này đi từ máy mới tinh đến lúc có một link HTTPS để cả nhóm cùng vào test. Làm lần lượt từng mục; mục nào đã xong thì bỏ qua.

> Toàn bộ mã nằm trong `src/`. Mọi lệnh bên dưới chạy từ thư mục `src/`, trừ khi ghi khác. Các lệnh viết cho **PowerShell trên Windows**.

| Muốn làm gì | Đọc mục |
|---|---|
| Cài lần đầu | 1 (một lệnh `setup.ps1`), 2 nếu là DB mới |
| Chạy để lập trình, sửa lỗi trên máy mình | 3 |
| Mở web cho nhiều máy cùng test | 4 |
| Gặp lỗi | 6 |

---

## 0. Dễ nhất: chạy toàn bộ bằng Docker

Chỉ cần [Docker Desktop](https://www.docker.com/products/docker-desktop/), không cần cài Python:

```bash
git clone https://github.com/Luffyreals/EduFlaw.git
cd EduFlaw
docker compose up
```

Mở **http://localhost:8000**, đăng nhập `master@eduflaw.com` / `MasterEduFlaw@123`. Docker tự dựng MySQL, tạo bảng và seed dữ liệu mẫu. Tắt bằng `docker compose down` (thêm `-v` để xóa dữ liệu). Các khóa trong `docker-compose.yml` chỉ để chạy thử local — đổi khi triển khai thật. Các mục dưới đây dành cho khi chạy trực tiếp bằng Python.

## 1. Cài đặt (một lần cho mỗi máy)

Yêu cầu: **Python ≥ 3.11** (pandas 3 không cài được trên bản cũ hơn) và **Git**. Máy chưa có thì cài bằng winget, rồi **mở terminal mới** và kiểm tra:

```powershell
winget install --id Python.Python.3.13
winget install --id Git.Git
```

```powershell
python --version
git --version
```

Nếu `python` mở Microsoft Store thay vì in phiên bản: Python chưa cài hoặc terminal chưa được mở lại sau khi cài.

Tải mã nguồn. Nhánh mặc định **`main`** là bản ổn định; `develop` là bản đang phát triển (thành viên nhóm làm việc trên nhánh này và gửi PR vào `develop`, khi ổn định mới gộp lên `main`):

```powershell
git clone https://github.com/Luffyreals/EduFlaw.git
cd EduFlaw\src
```

### Cài bằng một lệnh (khuyến nghị)

Nên bật MySQL local trước bằng Docker (chạy ở gốc repo): `docker compose up -d db`. Sau đó:

- **Windows:** `powershell -ExecutionPolicy Bypass -File .\setup.ps1`
- **macOS/Linux:** `chmod +x setup.sh && ./setup.sh`

Hai script tương đương nhau; làm lần lượt (chạy lại nhiều lần vẫn an toàn, bước nào xong rồi thì bỏ qua):

1. Kiểm tra Python ≥ 3.11 (báo cách cài nếu thiếu hoặc nếu `python` chỉ là lối tắt Microsoft Store).
2. Tạo `.venv` và cài thư viện (`requirements-dev.txt`; lần đầu mất vài phút).
3. Tạo `.env` từ `.env.example` nếu chưa có, **tự sinh `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `MASTER_PASSWORD`** nếu đang trống (không in giá trị).
4. Chuẩn bị CSDL: CSDL mới → **tự tạo bảng + seed dữ liệu mẫu** (gồm tài khoản Master); CSDL đã có dữ liệu → giữ nguyên.
5. (Windows) Kiểm tra `cloudflared`; chạy bộ test (thêm `-SkipTests` / `--skip-tests` để bỏ qua).

Script thoát với mã 2 khi **chưa kết nối được CSDL**: bật CSDL (vd `docker compose up -d db`) hoặc sửa `MYSQL_*` trong `src\.env` rồi chạy lại script.

Mọi lệnh trong tài liệu gọi thẳng `.venv\Scripts\python`, nên **không cần** `activate` (Windows mặc định chặn `Activate.ps1` với lỗi `running scripts is disabled on this system`).

Nhóm dùng chung một CSDL TiDB Cloud: xin người quản lý DB các giá trị `MYSQL_*` và `SMTP_*`, **không** gửi file `.env` qua kênh công khai và **không** commit file này.

| Biến | Bắt buộc | Ghi chú |
|---|---|---|
| `SECRET_KEY` | Có | `setup.ps1` tự sinh. Thiếu thì app dừng ngay khi khởi động |
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB` | Có | TiDB Cloud dùng cổng 4000 |
| `SMTP_EMAIL`, `SMTP_PASSWORD` | Có khi mở cho nhiều máy | Gmail + App Password 16 ký tự, dùng để gửi OTP |
| `APP_ENV` | Không | Để `development` khi chạy trên máy mình. Script ở mục 4 tự chuyển sang `production` |

Các dòng còn trống khác trong `.env.example` (`HOST=`, `PORT=`...) cứ để trống: app tự dùng giá trị mặc định.

**Tạo Gmail App Password** (chỉ người quản lý SMTP cần làm): bật xác minh 2 bước cho Gmail, vào **Google Account → Security → App passwords**, tạo mật khẩu ứng dụng, dùng chuỗi 16 ký tự đó làm `SMTP_PASSWORD`.

### Cài thủ công (khi không dùng được script)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Dán chuỗi vừa in vào dòng `SECRET_KEY=` trong `src\.env`, điền các biến ở bảng trên, rồi kiểm tra bằng bộ test (không cần CSDL):

```powershell
.venv\Scripts\python -m pytest
```

---

## 2. Khởi tạo cơ sở dữ liệu (chỉ với CSDL mới, một lần)

**Nếu CSDL chung đã có dữ liệu thì bỏ qua mục này.** Hai lệnh dưới đây chỉ dành cho DB mới: DB của người quản lý, hoặc DB riêng của người ngoài nhóm. Cách tự tạo MySQL bằng Docker: xem [README, bước 4 cách B](../README.md#cách-b--người-ngoài-nhóm-tự-tạo-mysql-bằng-docker-khuyến-nghị). Với MySQL nhớ đổi `MYSQL_PORT` thành 3306.

```powershell
.venv\Scripts\python init_db.py                          # tạo toàn bộ bảng từ schema.sql
.venv\Scripts\python -m app.services.mvp_seed_service    # dữ liệu mẫu: 10 ngành × 3 khóa × 100 SV, giảng viên, lớp, điểm
```

- Seed cần `MASTER_PASSWORD` (≥ 12 ký tự) trong `.env` nếu DB chưa có tài khoản master.
- Seed **xóa dữ liệu học vụ cũ** (trừ khi thêm `--no-reset`): không chạy lên DB chung đang được cả nhóm test.
- Mật khẩu tạm của các tài khoản mới nằm ở `src\instance\mat_khau_tam_seed_<thời gian>.xlsx`. File chứa mật khẩu dạng rõ: chỉ phát cho người cần, không đưa lên Git hay nhóm chat công khai.
- DB tạo từ phiên bản cũ: áp thủ công các file trong `src\migrations\` theo thứ tự số, chỉ những file chưa áp. DB mới tạo bằng `init_db.py` **không** cần migration.

---

## 3. Chạy trên máy mình (phát triển)

```powershell
.venv\Scripts\python run.py
```

Mở http://127.0.0.1:5000. Chế độ này bật debug và tự in OTP ra console nếu chưa cấu hình SMTP.

> **Không** mở link công khai (mục 4) tới `run.py`: Werkzeug debugger cho phép chạy mã tùy ý trên máy bạn nếu bị lộ ra ngoài.

---

## 4. Mở web cho nhiều máy cùng test (Cloudflare Tunnel)

App chạy trên máy bạn, Cloudflare cấp một link HTTPS công khai dạng `https://<tên ngẫu nhiên>.trycloudflare.com` để mọi máy truy cập. Miễn phí, không cần tài khoản hay thẻ.

### Cài cloudflared (một lần)

```powershell
winget install --id Cloudflare.cloudflared
```

Script ở dưới tự tìm được `cloudflared` ngay sau khi cài. Muốn gõ lệnh `cloudflared` trực tiếp (cách thủ công) thì phải mở terminal mới.

### Chạy

```powershell
powershell -ExecutionPolicy Bypass -File .\run_public.ps1
```

Script `src\run_public.ps1` tự làm các việc:

1. Kiểm tra đã có `.venv`, `.env`, `cloudflared` và cổng 8000 còn trống.
2. Chạy `serve.py` (waitress) với `APP_ENV=production`, `TRUST_PROXY=1`, `HOST=127.0.0.1`. Các giá trị này chỉ áp dụng cho lần chạy đó, không sửa `.env`.
3. Chờ `/healthz` phản hồi rồi mở tunnel.

Link công khai nằm trong khung `Your quick Tunnel has been created!` mà cloudflared in ra. Tunnel cần khoảng 10–20 giây để kết nối: nếu mở link ngay thấy lỗi 530 thì chờ chút rồi tải lại. Gửi link `https://...trycloudflare.com/login` cho mọi người.

Bấm **Ctrl+C** để dừng cả tunnel lẫn máy chủ.

Tùy chọn:

| Tham số | Khi nào dùng |
|---|---|
| `-Http2` | Mạng chặn QUIC (cloudflared báo `UDP Connectivity ... FAIL` và không kết nối được) |
| `-Port 8001` | Cổng 8000 đang bị chiếm |

### Chạy thủ công (không dùng script)

Mở hai terminal trong thư mục `src`:

```powershell
# Terminal 1: máy chủ
$env:APP_ENV="production"; $env:TRUST_PROXY="1"; $env:HOST="127.0.0.1"; .venv\Scripts\python serve.py
```

```powershell
# Terminal 2: tunnel
cloudflared tunnel --url http://127.0.0.1:8000
```

Tắt Terminal 1 thì link chết theo (Cloudflare trả lỗi 502) dù Terminal 2 vẫn chạy.

### Lưu ý

- Máy chạy tunnel phải **bật suốt** lúc test: đặt **Settings → System → Power → Sleep** thành **Never** trong thời gian đó.
- **Link đổi mỗi lần chạy lại.** Cần link cố định thì phải dùng ngrok (tặng một tên miền cố định miễn phí) hoặc Cloudflare Tunnel có tên miền riêng.
- Mọi máy dùng chung CSDL thật: sửa điểm, khóa tài khoản... là sửa dữ liệu thật.
- Ở chế độ production, OTP gửi qua Gmail thật; thiếu `SMTP_*` thì chức năng onboarding/quên mật khẩu báo lỗi.

---

## 5. Kiểm tra sau khi mở link

- [ ] `https://<link>/healthz` trả `{"status": "ok"}`.
- [ ] Mở `/login` qua link HTTPS, đăng nhập master.
- [ ] Tài khoản mới bắt buộc onboarding: đặt mật khẩu mới + nhận OTP qua Gmail thật.
- [ ] Đăng nhập một tài khoản sinh viên: xem điểm, lịch học.
- [ ] Đổi mật khẩu ở một máy: máy khác đang đăng nhập cùng tài khoản bị đăng xuất ở thao tác kế tiếp.
- [ ] Nhập sai mật khẩu 5 lần: bị khóa 60 giây. Máy khác vẫn đăng nhập bình thường (nếu máy khác cũng bị khóa, xem mục 6).

---

## 6. Xử lý sự cố

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| `Thiếu SECRET_KEY` khi khởi động | Chưa điền `SECRET_KEY` trong `src\.env` (mục 1) |
| `Thiếu cấu hình CSDL cho môi trường production` | Thiếu một trong các biến `MYSQL_*` |
| Cần bản mới nhất chưa có trên `main` | Trong thư mục đã clone: `git checkout develop`, rồi chạy lại `setup.ps1` (bản đang phát triển, có thể chưa ổn định) |
| Gõ `python` thì mở Microsoft Store | Python chưa cài, hoặc chưa mở terminal mới sau khi cài (mục 1) |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | Không cần `activate`: gọi thẳng `.venv\Scripts\python ...` như trong tài liệu |
| `ModuleNotFoundError` | Đang chạy bằng `python` của hệ thống thay vì `.venv\Scripts\python`, hoặc đứng sai thư mục (phải ở `src`) |
| `pip install` lỗi khi cài pandas | Python cũ hơn 3.11: cài Python mới rồi tạo lại `.venv` |
| Trang báo lỗi kết nối CSDL / chờ rất lâu | Sai `MYSQL_*`, hoặc TiDB Cloud chưa cho phép IP của máy bạn (mục Networking của cluster) |
| Đăng nhập xong lại bị đưa về trang đăng nhập | Đang mở app production qua `http://`: cookie `Secure` chỉ chạy qua HTTPS. Dùng link `https://...trycloudflare.com`, hoặc `.venv\Scripts\python run.py` khi test trên máy mình |
| `running scripts is disabled on this system` | Chạy script đúng cách: `powershell -ExecutionPolicy Bypass -File .\setup.ps1` (tương tự với `run_public.ps1`) |
| `setup.ps1` báo `Chưa kết nối được CSDL` | Sai `MYSQL_*` trong `.env`, hoặc TiDB Cloud chưa cho phép IP của máy (mục Networking của cluster) |
| Script báo `Cổng 8000 đang bị chiếm` | App đang chạy ở terminal khác: tắt nó, hoặc thêm `-Port 8001` |
| cloudflared in `ERROR: Allow outbound QUIC traffic...` | Chỉ là cảnh báo nếu sau đó có dòng `Registered tunnel connection`. Nếu không kết nối được, chạy lại với `-Http2` |
| Mở link thấy lỗi **530** | Tunnel chưa kết nối xong: chờ 10–20 giây rồi tải lại |
| Mở link thấy lỗi **502** | Tunnel còn chạy nhưng máy chủ đã tắt: chạy lại script |
| Không nhận được OTP | Sai `SMTP_EMAIL`/`SMTP_PASSWORD` (phải là App Password, không phải mật khẩu Gmail); xem cả hộp thư Spam |
| Đang dùng thì bị đưa về trang đăng nhập | Bình thường nếu mật khẩu tài khoản vừa được đổi (ở máy khác, qua quên mật khẩu, hoặc Master/cố vấn cấp lại): mọi phiên cũ bị đăng xuất. Sau khi cập nhật lên bản có cơ chế này, mọi người cũng phải đăng nhập lại một lần |
| Một người sai mật khẩu làm mọi người bị khóa | Máy chủ không thấy đúng IP người dùng: kiểm tra đang chạy bằng script (đã đặt `TRUST_PROXY=1`) |

---

## 7. Khi có máy chủ riêng (VPS)

1. Cài như mục 1 trên máy chủ, điền `.env` với `APP_ENV=production`.
2. Chạy `.venv/bin/python serve.py` dưới `systemd` để tự khởi động lại (mặc định `0.0.0.0:8000`; đổi bằng `HOST`, `PORT`, `WAITRESS_THREADS`).
3. Đặt nginx hoặc Caddy phía trước làm reverse proxy có HTTPS (Let's Encrypt), chuyển tiếp `X-Forwarded-*`, và đặt `TRUST_PROXY=1`.

Chạy nhiều tiến trình cùng lúc được: khóa đăng nhập và OTP lưu trong CSDL nên dùng chung giữa các tiến trình.

---

## 8. Mã hóa dữ liệu (bảo mật CSDL)

Hệ thống bảo vệ dữ liệu theo nhiều lớp:

### 8.1. TLS tới CSDL (chống nghe lén / MITM)
CSDL ở xa (TiDB Cloud) phải kết nối qua kênh **mã hóa có xác thực chứng chỉ**.

**Mặc định đã an toàn:** nếu để trống `MYSQL_SSL_CA`, app tự dùng bộ CA công khai của **certifi** (đã có trong `requirements.txt`) nên kết nối tới TiDB Cloud vẫn được **xác thực chứng chỉ + danh tính máy chủ** — không cần cấu hình gì thêm.

Chỉ cần khai báo CA riêng khi CSDL dùng **CA nội bộ** (không nằm trong bộ CA công khai):

```ini
MYSQL_SSL_CA=/duong/dan/den/ca.pem   # CA nội bộ của máy chủ CSDL
MYSQL_SSL_VERIFY=true                 # xác thực cả hostname (chỉ đặt false nếu CA không khớp hostname)
```

App chỉ ghi **cảnh báo** khi vừa không đặt `MYSQL_SSL_CA` vừa không có certifi. Đặt `MYSQL_SSL_DISABLED=true` chỉ cho CSDL local không có TLS.

### 8.2. Mã hóa CCCD ở tầng ứng dụng (field-level)
CCCD (`id_card`) được mã hóa **AES-256-GCM** trước khi lưu, khóa lấy từ `FIELD_ENCRYPTION_KEY` (không nằm trong CSDL). Nhờ vậy một bản dump CSDL hoặc người có quyền đọc CSDL cũng không thấy CCCD dạng rõ.

Thiết lập:
```ini
# Tạo khóa ngẫu nhiên: python -c "import secrets; print(secrets.token_hex(32))"
FIELD_ENCRYPTION_KEY=<chuoi_ngau_nhien_dai>
```
- DB cũ: áp `migrations/010_encrypt_id_card.sql` (mở rộng cột), rồi mã hóa dữ liệu cũ:
  ```bash
  python -m app.services.pii_backfill_service            # chạy thử, đếm
  python -m app.services.pii_backfill_service --apply    # mã hóa thật
  ```
- Giải mã khoan dung với dữ liệu cũ dạng rõ nên app chạy được ngay cả khi chưa backfill.
- **Lưu ý khóa:** ĐỔI `FIELD_ENCRYPTION_KEY` sẽ khiến không giải mã được CCCD cũ. Giữ khóa cố định; nếu buộc phải xoay khóa thì giải mã bằng khóa cũ rồi mã hóa lại bằng khóa mới.

### 8.3. Mã hóa at-rest (TDE) — tầng hạ tầng
Mã hóa toàn bộ dữ liệu lưu trên đĩa (file dữ liệu, backup) là tính năng của máy chủ CSDL, không bật từ mã ứng dụng:
- **TiDB Cloud:** bật TDE sẵn ở hạ tầng; dữ liệu lưu trữ và backup được mã hóa. Kiểm tra trong bảng điều khiển dịch vụ.
- **MySQL tự quản (VPS):** bật InnoDB tablespace encryption (keyring) và mã hóa backup; tham khảo tài liệu MySQL về `innodb_redo_log_encrypt`, `innodb_undo_log_encrypt`, `--tablespace`.

TDE bảo vệ trước mất đĩa/backup; mã hóa cấp trường (8.2) bổ sung bảo vệ trước người có quyền truy vấn CSDL.
