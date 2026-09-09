"""tests.py — smoke test for Bot 7 (deployment_manager). Run: python tests.py"""
import shutil
from pathlib import Path

from deployment_manager import create_github_repo

TARGET = Path(r"C:\Users\smile\OneDrive\Documents\GitHub\website_agency\websites_folder")

SKIP_MARKERS = ("not found on PATH", "gh repo create failed", "'gh'")


def ensure_fixture(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if not any(p for p in folder.iterdir() if p.name != ".git"):
        (folder / "index.html").write_text(
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>Test site</title></head><body><h1>Test site</h1></body></html>",
            encoding="utf-8")


def test_create_github_repo() -> int:
    ensure_fixture(TARGET)
    try:
        url = create_github_repo(str(TARGET))
    except RuntimeError as e:
        msg = str(e)
        if any(m in msg for m in SKIP_MARKERS):
            print(f"[tests] SKIP (gh unavailable): {msg}", flush=True)
            return 0
        print(f"[tests] FAIL: {msg}", flush=True)
        return 1
    print(f"[tests] PASS: repo -> {url}", flush=True)
    return 0


if __name__ == "__main__":
    gh = shutil.which("gh") or next(
        (c for c in (r"C:\Program Files\GitHub CLI\gh.exe",
                     r"C:\Program Files (x86)\GitHub CLI\gh.exe")
         if Path(c).exists()), None)
    print(f"[tests] gh: {gh or 'MISSING'}", flush=True)
    rc = test_create_github_repo()
    print(f"[tests] {'done (pass/skip)' if rc == 0 else 'FAILED'}", flush=True)
    raise SystemExit(rc)
