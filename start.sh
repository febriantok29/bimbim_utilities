#!/usr/bin/env bash
cd "$(dirname "$0")"

DEFAULT_PORT=5050
PORT="$DEFAULT_PORT"

port_busy() {
  lsof -i ":$1" >/dev/null 2>&1
}

# --- venv ---
# venv nyimpen path absolut; kalau folder project dipindah, venv lama rusak (pip/python nggak ketemu)
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

# --- cek port, tawarkan ganti kalau bentrok ---
while port_busy "$PORT"; do
  echo ""
  echo "Port $PORT lagi dipakai proses lain (di Mac, port 5000 sering kepakai AirPlay Receiver)."
  read -r -p "Pakai port berapa? (kosongkan untuk coba $((PORT + 1))) " new_port
  if [ -z "$new_port" ]; then
    PORT=$((PORT + 1))
  elif [[ "$new_port" =~ ^[0-9]+$ ]]; then
    PORT="$new_port"
  else
    echo "Input tidak valid, harus angka."
  fi
done

echo ""
echo "Jalan di http://127.0.0.1:$PORT"
open "http://127.0.0.1:$PORT" 2>/dev/null &

PORT="$PORT" python app.py
