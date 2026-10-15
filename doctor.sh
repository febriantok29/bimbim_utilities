#!/usr/bin/env bash
cd "$(dirname "$0")"

PORT="${PORT:-5050}"
FAILED=0

ok()   { echo "  ✓ $1"; }
warn() { echo "  ✗ $1"; }

# Binary opsional: nama fitur, perintah, cara install
check_bin() {
  local feature="$1" bin="$2" hint="$3"
  if command -v "$bin" >/dev/null 2>&1; then
    ok "$bin ($feature)"
  else
    warn "$bin belum ada — $feature nggak bakal jalan. Install: $hint"
  fi
}

echo "Python & virtualenv"
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
  ok "$(python3 --version)"
else
  warn "butuh Python 3.9 atau lebih baru"
  FAILED=1
fi

if [ ! -d .venv ]; then
  warn ".venv belum ada (jalankan ./start.sh sekali)"
  FAILED=1
elif ! grep -q "VIRTUAL_ENV=\"$PWD/.venv\"" .venv/bin/activate; then
  warn ".venv menunjuk ke lokasi lain (folder dipindah), jalankan ./start.sh buat bikin ulang"
  FAILED=1
else
  ok ".venv valid"
  if .venv/bin/python -m pip check >/dev/null 2>&1; then
    ok "dependency konsisten (pip check)"
  else
    warn "pip check ada masalah, jalankan ./update.sh atau .venv/bin/python -m pip check"
    FAILED=1
  fi
fi

echo ""
echo "Tool eksternal (opsional, per fitur)"
check_bin "Video & WebM converter" ffmpeg "brew install ffmpeg"
check_bin "OCR" tesseract "brew install tesseract tesseract-lang"
check_bin "OCR" gs "brew install ghostscript"
check_bin "PDF ke gambar" pdftoppm "brew install poppler"
check_bin "Flutter cache cleanup" flutter "https://docs.flutter.dev/get-started/install"
check_bin "cek port di start.sh" lsof "bawaan macOS"

echo ""
echo "Port"
if lsof -i ":$PORT" >/dev/null 2>&1; then
  warn "port $PORT lagi dipakai (start.sh bakal nanya port lain)"
else
  ok "port $PORT bebas"
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "Lingkungan siap. Tool yang bertanda ✗ cuma mempengaruhi fitur terkait."
else
  echo "Ada masalah di Python/virtualenv, beresin dulu yang bertanda ✗ di atas."
fi
exit "$FAILED"
