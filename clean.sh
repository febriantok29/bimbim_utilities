#!/usr/bin/env bash
cd "$(dirname "$0")"

DRY_RUN=0
ASSUME_YES=0
ALL=0

usage() {
  echo "Pemakaian: ./clean.sh [--dry-run] [--yes] [--all]"
  echo "  --dry-run  cuma tampilkan apa yang akan dihapus"
  echo "  --yes      lewati semua konfirmasi"
  echo "  --all      termasuk .venv dan cache graphify (tetap tanya konfirmasi)"
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --all) ALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opsi tidak dikenal: $arg"; usage; exit 1 ;;
  esac
done

confirm() {
  [ "$ASSUME_YES" -eq 1 ] && return 0
  read -r -p "$1 [y/N] " answer
  [[ "$answer" =~ ^[yY]$ ]]
}

# --- sampah build/cache, aman dihapus (.venv dan .git nggak disentuh) ---
JUNK=()
while IFS= read -r p; do
  JUNK+=("$p")
done < <(find . \( -path ./.venv -o -path ./.git \) -prune -o \
  \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \
     -o -name '_temp_*.png' -o -name '*.log' -o -name .DS_Store \) -print)

if [ "${#JUNK[@]}" -eq 0 ]; then
  echo "Nggak ada cache/sampah sementara."
else
  echo "Cache & file sementara (${#JUNK[@]} item):"
  printf '  %s\n' "${JUNK[@]}"
  if [ "$DRY_RUN" -eq 0 ]; then
    rm -rf "${JUNK[@]}"
    echo "Dihapus."
  fi
fi

# --- isi folder hasil kerja: export/ dan import/ (folder tetap dipertahankan) ---
for dir in export import; do
  [ -d "$dir" ] || continue
  if [ -z "$(ls -A "$dir")" ]; then
    continue
  fi
  echo ""
  echo "Isi $dir/: $(du -sh "$dir" | cut -f1) ($(ls -A "$dir" | wc -l | tr -d ' ') item)"
  if [ "$DRY_RUN" -eq 1 ]; then
    continue
  fi
  if confirm "Kosongkan isi $dir/?"; then
    find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    echo "$dir/ dikosongkan."
  else
    echo "$dir/ dilewati."
  fi
done

# --- opsional: .venv dan cache graphify ---
if [ "$ALL" -eq 1 ]; then
  for target in .venv graphify-out/cache; do
    [ -d "$target" ] || continue
    echo ""
    echo "$target: $(du -sh "$target" | cut -f1)"
    if [ "$DRY_RUN" -eq 1 ]; then
      continue
    fi
    if [ "$ASSUME_YES" -eq 0 ] && ! confirm "Hapus $target?"; then
      echo "$target dilewati."
      continue
    fi
    rm -rf "$target"
    echo "$target dihapus."
  done
fi

[ "$DRY_RUN" -eq 1 ] && echo "" && echo "(dry-run: belum ada yang dihapus)"
exit 0
