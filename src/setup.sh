#!/usr/bin/env bash
# Cài đặt EduFlaw trên macOS/Linux (và Git Bash trên Windows) bằng một lệnh. Chạy lại nhiều lần vẫn an toàn.
#
#   cd src && ./setup.sh                 # cài + tạo bảng + seed (nếu CSDL mới) + chạy test
#   ./setup.sh --skip-tests              # bỏ qua bước chạy test
#
# Tự sinh SECRET_KEY / FIELD_ENCRYPTION_KEY / MASTER_PASSWORD vào .env (không in giá trị bí mật).
# Mặc định dùng MySQL của docker-compose ở gốc repo: chạy `docker compose up -d` trước.
set -euo pipefail
cd "$(dirname "$0")"

SKIP_TESTS=0
[ "${1:-}" = "--skip-tests" ] && SKIP_TESTS=1

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    OK: %s\n' "$1"; }
note() { printf '    CHU Y: %s\n' "$1"; }
die()  { printf '    LOI: %s\n' "$1" >&2; exit 1; }

export PYTHONIOENCODING=utf-8

# ---------- 1. Python >= 3.11 ----------
step 'Kiem tra Python (can ban 3.11 tro len)'
SYS_PY=""
for name in python3 python; do
  if command -v "$name" >/dev/null 2>&1; then
    if "$name" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
      SYS_PY="$name"; break
    fi
  fi
done
if [ -z "$SYS_PY" ] && [ ! -x ".venv/bin/python" ] && [ ! -x ".venv/Scripts/python.exe" ]; then
  die 'Chua co Python >= 3.11. Cai Python 3.11+ (macOS: brew install python; Ubuntu: sudo apt install python3 python3-venv) roi chay lai.'
fi

# ---------- 2. Moi truong ao .venv ----------
step 'Tao moi truong ao .venv'
venv_python() {
  if [ -x ".venv/bin/python" ]; then echo ".venv/bin/python";
  elif [ -x ".venv/Scripts/python.exe" ]; then echo ".venv/Scripts/python.exe";
  else echo ""; fi
}
VENV_PY="$(venv_python)"
if [ -n "$VENV_PY" ]; then
  ok '.venv da co, dung lai.'
else
  "$SYS_PY" -m venv .venv || die 'Khong tao duoc .venv.'
  VENV_PY="$(venv_python)"
  [ -n "$VENV_PY" ] || die 'Khong tao duoc .venv.'
  ok 'Da tao .venv.'
fi

# ---------- 3. Thu vien ----------
step 'Cai thu vien (requirements-dev.txt), lan dau mat vai phut'
"$VENV_PY" -m pip install --disable-pip-version-check -q -r requirements-dev.txt || die 'pip install that bai.'
ok 'Thu vien da du.'

# ---------- 4. File .env + khoa bi mat ----------
step 'Chuan bi .env va sinh khoa bi mat'
"$VENV_PY" ensure_env.py || die 'Khong chuan bi duoc .env.'

# ---------- 5. CSDL: tu tao bang + seed neu la CSDL moi ----------
step 'Chuan bi CSDL (tu tao bang + seed neu CSDL moi)'
DB_READY=1
"$VENV_PY" bootstrap_db.py || { rc=$?; [ "$rc" -eq 3 ] && DB_READY=0 || die "Loi chuan bi CSDL (ma $rc)."; }

# ---------- 6. Test ----------
if [ "$SKIP_TESTS" -eq 0 ]; then
  step 'Chay bo test (khong can CSDL)'
  "$VENV_PY" -m pytest -q || die 'Co test that bai.'
  ok 'Toan bo test deu qua.'
fi

printf '\nCai dat xong. Lenh tiep theo (trong thu muc src):\n'
printf '    %s run.py        # chay tren may minh: http://127.0.0.1:5000\n' "$VENV_PY"
printf '    Dang nhap Master: tai khoan trong MASTER_USERNAME, mat khau trong MASTER_PASSWORD cua .env\n'
if [ "$DB_READY" -eq 0 ]; then
  note 'Chua ket noi duoc CSDL. Khoi dong CSDL (vd: docker compose up -d o goc repo) roi chay lai ./setup.sh'
  exit 2
fi
