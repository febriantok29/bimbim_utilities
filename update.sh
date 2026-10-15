#!/usr/bin/env bash
cd "$(dirname "$0")"

# --- pastikan git repo & tree bersih ---
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Folder ini bukan git repo, nggak bisa update."
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Ada perubahan yang belum di-commit, update dibatalkan biar kerjaan nggak ketimpa:"
  git status --short
  exit 1
fi

# --- tarik perubahan terbaru ---
BEFORE="$(git rev-parse HEAD)"
echo "Tarik perubahan terbaru..."
if ! git pull --ff-only; then
  echo ""
  echo "git pull gagal (branch lokal mungkin sudah menyimpang dari remote). Selesaikan manual dulu."
  exit 1
fi
AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
  echo "Sudah paling baru."
else
  echo ""
  echo "Commit baru yang masuk:"
  git log --oneline "$BEFORE..$AFTER"
fi

# --- venv ---
# venv nyimpen path absolut; kalau folder project dipindah, venv lama rusak
if [ -d .venv ] && ! grep -q "VIRTUAL_ENV=\"$PWD/.venv\"" .venv/bin/activate; then
  echo "Virtualenv lama menunjuk ke lokasi lain (folder dipindah), bikin ulang..."
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  echo "Belum ada virtualenv, bikin dulu..."
  if ! python3 -m venv .venv; then
    echo "Gagal bikin virtualenv. Pastikan python3 terpasang, lalu coba lagi."
    exit 1
  fi
fi

source .venv/bin/activate

# --- install deps, dengan retry kalau gagal ---
while true; do
  echo ""
  echo "Install dependencies..."
  if python -m pip install -q -r requirements.txt; then
    break
  fi
  echo ""
  echo "Install dependencies gagal (lihat error di atas)."
  read -r -p "Coba lagi? [y/n/skip] " choice
  case "$choice" in
    y|Y) continue ;;
    skip|s|S) echo "Lanjut tanpa install ulang (mungkin ada modul yang belum lengkap)."; break ;;
    *) echo "Dibatalkan."; exit 1 ;;
  esac
done

# --- refresh graphify (khusus file kode, tanpa LLM) ---
if [ "$BEFORE" != "$AFTER" ] && [ -d graphify-out ] && command -v graphify >/dev/null 2>&1; then
  echo ""
  echo "Refresh graphify..."
  graphify update . || echo "graphify update gagal, graph tidak diperbarui."
  echo "Catatan: perubahan template HTML / requirements.txt perlu '/graphify . --update' di Claude Code."
fi

echo ""
echo "Selesai. Jalankan ./start.sh buat nyalain aplikasinya."
