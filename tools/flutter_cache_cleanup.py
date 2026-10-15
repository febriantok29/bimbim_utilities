from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from tools.flutter_cleanup import dir_size, find_flutter_projects

EXCLUDED_PROJECT_PARTS = {"build", ".dart_tool", "ephemeral", ".symlinks", ".pub-cache"}
GIT_ENTRY_PATTERN = re.compile(r"^(?P<name>.+)-(?P<sha>[0-9a-f]{40})$")
HOSTED_ENTRY_PATTERN = re.compile(r"^(?P<name>[A-Za-z0-9_]+)-(?P<version>\d.*)$")
ACTIVE_PROJECT_PATTERN = re.compile(r"^\* (?P<path>.+)$")
RECOVER_PATTERN = re.compile(r"^Would recover (?P<amount>.+)\.$")
DU_CHUNK_SIZE = 200
TOP_HOSTED_COUNT = 10


def pub_cache_dir(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    raw = env.get("PUB_CACHE")
    return Path(raw).expanduser() if raw else Path.home() / ".pub-cache"


def run_command(args: list[str], cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=dart_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def flutter_root() -> Path | None:
    raw = os.environ.get("FLUTTER_ROOT")
    if raw and Path(raw).is_dir():
        return Path(raw)
    flutter = shutil.which("flutter")
    if not flutter:
        return None
    return Path(flutter).resolve().parent.parent


def find_dart() -> str | None:
    dart = shutil.which("dart")
    if dart:
        return dart
    root = flutter_root()
    if root and (root / "bin" / "dart").is_file():
        return str(root / "bin" / "dart")
    return None


def dart_env() -> dict:
    env = dict(os.environ)
    root = flutter_root()
    if root:
        env["FLUTTER_ROOT"] = str(root)
    return env


def du_sizes(paths: list[Path]) -> dict[Path, int]:
    sizes: dict[Path, int] = {}
    for start in range(0, len(paths), DU_CHUNK_SIZE):
        chunk = paths[start:start + DU_CHUNK_SIZE]
        try:
            result = subprocess.run(
                ["du", "-sk", *[str(p) for p in chunk]],
                capture_output=True, text=True, timeout=600,
            )
            for line in result.stdout.splitlines():
                kilobytes, _, raw_path = line.partition("\t")
                if kilobytes.isdigit() and raw_path:
                    sizes[Path(raw_path)] = int(kilobytes) * 1024
        except (OSError, subprocess.TimeoutExpired):
            pass
        for path in chunk:
            if path not in sizes and path.exists():
                sizes[path] = dir_size(path)
    return sizes


def fast_size(path: Path) -> int:
    if not path.exists():
        return 0
    return du_sizes([path]).get(path, 0)


def list_projects(root: Path) -> list[Path]:
    projects = []
    for project in find_flutter_projects(root):
        try:
            relative_parts = project.relative_to(root).parts
        except ValueError:
            relative_parts = project.parts
        if EXCLUDED_PROJECT_PARTS.intersection(relative_parts):
            continue
        projects.append(project)
    return projects


def cache_summary(cache: Path | None = None) -> dict:
    cache = cache or pub_cache_dir()
    sections = []
    if cache.is_dir():
        children = sorted(p for p in cache.iterdir() if p.is_dir())
        sizes = du_sizes(children)
        sections = [{"name": p.name, "size": sizes.get(p, 0)} for p in children]
        sections.sort(key=lambda s: s["size"], reverse=True)

    checkouts: dict[str, int] = {}
    git_dir = cache / "git"
    if git_dir.is_dir():
        for entry in git_dir.iterdir():
            match = GIT_ENTRY_PATTERN.match(entry.name)
            if entry.is_dir() and entry.name != "cache" and match:
                checkouts[match.group("name")] = checkouts.get(match.group("name"), 0) + 1

    return {
        "path": cache,
        "exists": cache.is_dir(),
        "total_size": sum(s["size"] for s in sections),
        "sections": sections,
        "git_checkouts": dict(sorted(checkouts.items(), key=lambda kv: kv[1], reverse=True)),
    }


def parse_gc_output(text: str, cache: Path | None = None) -> dict:
    cache = cache or pub_cache_dir()
    active_projects: list[str] = []
    recover = None
    entries: list[Path] = []
    in_entries = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if in_entries:
            if line.strip():
                entries.append(Path(line.strip()))
            continue
        if line.startswith("Would delete") or line.startswith("Deleting"):
            in_entries = True
            continue
        active = ACTIVE_PROJECT_PATTERN.match(line)
        if active:
            active_projects.append(active.group("path"))
            continue
        recover_match = RECOVER_PATTERN.match(line)
        if recover_match:
            recover = recover_match.group("amount")

    hosted: dict[str, list[str]] = {}
    git_checkouts: dict[str, list[str]] = {}
    git_mirrors: list[str] = []
    hash_files = 0
    other: list[str] = []

    for entry in entries:
        try:
            parts = entry.relative_to(cache).parts
        except ValueError:
            other.append(str(entry))
            continue
        if len(parts) >= 3 and parts[0] == "hosted":
            match = HOSTED_ENTRY_PATTERN.match(parts[2])
            if match:
                hosted.setdefault(match.group("name"), []).append(match.group("version"))
            else:
                other.append(str(entry))
        elif parts and parts[0] == "hosted-hashes":
            hash_files += 1
        elif len(parts) >= 3 and parts[0] == "git" and parts[1] == "cache":
            match = GIT_ENTRY_PATTERN.match(parts[2])
            git_mirrors.append(match.group("name") if match else parts[2])
        elif len(parts) >= 2 and parts[0] == "git":
            match = GIT_ENTRY_PATTERN.match(parts[1])
            if match:
                git_checkouts.setdefault(match.group("name"), []).append(match.group("sha")[:8])
            else:
                other.append(str(entry))
        else:
            other.append(str(entry))

    return {
        "active_projects": active_projects,
        "recover": recover,
        "entries": entries,
        "hosted": hosted,
        "git_checkouts": git_checkouts,
        "git_mirrors": sorted(set(git_mirrors)),
        "hash_files": hash_files,
        "other": other,
    }


def find_unregistered(projects: list[Path], active_projects: list[str]) -> list[Path]:
    active = set()
    for raw in active_projects:
        try:
            active.add(Path(raw).resolve())
        except OSError:
            active.add(Path(raw))
    unregistered = []
    for project in projects:
        try:
            resolved = project.resolve()
        except OSError:
            resolved = project
        if resolved not in active:
            unregistered.append(project)
    return unregistered


def preview_gc(cache: Path | None = None, with_sizes: bool = True) -> dict:
    cache = cache or pub_cache_dir()
    dart = find_dart()
    if dart is None:
        return {"ok": False, "error": "Perintah dart tidak ditemukan di PATH maupun di folder Flutter."}

    result = run_command([dart, "pub", "cache", "gc", "--dry-run"])
    if result.returncode != 0:
        return {"ok": False, "error": _tail(result.stderr or result.stdout)}

    parsed = parse_gc_output(result.stdout, cache)
    if not with_sizes:
        parsed["ok"] = True
        return parsed

    sizes = du_sizes(parsed["entries"])
    parsed["total_bytes"] = sum(sizes.get(p, 0) for p in parsed["entries"])
    hosted_entries = [
        p for p in parsed["entries"]
        if _relative_parts(p, cache)[:1] == ("hosted",)
    ]
    largest = sorted(hosted_entries, key=lambda p: sizes.get(p, 0), reverse=True)[:TOP_HOSTED_COUNT]
    parsed["largest_hosted"] = [{"name": p.name, "size": sizes.get(p, 0)} for p in largest]
    parsed["ok"] = True
    return parsed


def run_gc(collect_recent: bool = False, cache: Path | None = None) -> dict:
    cache = cache or pub_cache_dir()
    dart = find_dart()
    if dart is None:
        return {"ok": False, "error": "Perintah dart tidak ditemukan di PATH maupun di folder Flutter."}

    before = fast_size(cache)
    args = [dart, "pub", "cache", "gc", "--force"]
    if collect_recent:
        args.append("--collect-recent")
    result = run_command(args)
    after = fast_size(cache)
    if result.returncode != 0:
        return {"ok": False, "error": _tail(result.stderr or result.stdout)}
    return {
        "ok": True,
        "before": before,
        "after": after,
        "freed": max(before - after, 0),
        "output": _tail(result.stdout, 1200),
    }


def register_project(project: Path, allow_download: bool = False) -> dict:
    base = {"path": str(project), "name": project.name}
    dart = find_dart()
    if dart is None:
        return {**base, "ok": False, "mode": None, "message": "dart tidak ditemukan"}

    offline = run_command([dart, "pub", "get", "--offline"], cwd=project)
    if offline.returncode == 0:
        return {**base, "ok": True, "mode": "offline", "message": ""}

    if allow_download:
        online = run_command([dart, "pub", "get"], cwd=project)
        if online.returncode == 0:
            return {**base, "ok": True, "mode": "online", "message": ""}
        return {**base, "ok": False, "mode": None, "message": _tail(online.stderr or online.stdout)}

    return {
        **base,
        "ok": False,
        "mode": None,
        "message": _tail(offline.stderr or offline.stdout),
    }


class RegistrationJob:
    def __init__(self, projects: list[Path], allow_download: bool) -> None:
        self.projects = projects
        self.allow_download = allow_download
        self.results: list[dict] = []
        self.current: str | None = None
        self.finished = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        for project in self.projects:
            with self._lock:
                self.current = project.name
            try:
                outcome = register_project(project, self.allow_download)
            except Exception as error:  # noqa: BLE001
                outcome = {
                    "path": str(project), "name": project.name,
                    "ok": False, "mode": None, "message": str(error),
                }
            with self._lock:
                self.results.append(outcome)
        with self._lock:
            self.current = None
            self.finished = True

    def snapshot(self) -> dict:
        with self._lock:
            results = list(self.results)
            return {
                "total": len(self.projects),
                "done": len(results),
                "current": self.current,
                "finished": self.finished,
                "ok": sum(1 for r in results if r["ok"]),
                "failed": [r for r in results if not r["ok"]],
                "results": results,
            }


_job_lock = threading.Lock()
_current_job: RegistrationJob | None = None


def start_registration(projects: list[Path], allow_download: bool) -> bool:
    global _current_job
    with _job_lock:
        if _current_job is not None and not _current_job.finished:
            return False
        _current_job = RegistrationJob(projects, allow_download)
        _current_job.start()
        return True


def registration_status() -> dict:
    with _job_lock:
        job = _current_job
    if job is None:
        return {"total": 0, "done": 0, "current": None, "finished": False, "ok": 0, "failed": [], "results": []}
    return job.snapshot()


def _relative_parts(path: Path, cache: Path) -> tuple[str, ...]:
    try:
        return path.relative_to(cache).parts
    except ValueError:
        return ()


def _tail(text: str, limit: int = 500) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else "…" + text[-limit:]
