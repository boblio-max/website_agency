"""
deployment_manager.py (Bot 7) — Deploy a QA-approved site.

Input:
    generated_sites/<lead_id>/ + its qa_report.json

Process:
    1. Verify QA passed (CRITICAL RULE: no green light from Bot 6 → no deploy).
    2. Deploy via --provider: auto | vercel | render | local.
       - vercel: uses the Vercel CLI (`vercel deploy`) if installed.
       - render: uses RENDER_API_KEY/RENDER_SERVICE_ID if configured.
       - local: offline fallback — copies the site to deployments/<lead_id>/
         and records a file:// preview URL.
    3. Capture the deployment URL + metadata.

Output (deployment record JSON):
    {"lead_id": "lead_00421", "status": "deployed",
     "preview_url": "https://...", "deployment_id": "...",
     "deployed_at": "...", "provider": "vercel", "qa_score": 94}

Usage:
    python deployment_manager.py --site generated_sites/lead_00001
    python deployment_manager.py --lead lead_00001 --provider local
    python deployment_manager.py --site generated_sites/lead_00001 --qa-report generated_sites/lead_00001/qa_report.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

try:  # Windows consoles default to cp1252; keep unicode output from crashing
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_qa(site_dir: Path, qa_arg: str | None) -> tuple[dict | None, Path | None]:
    candidates: list[Path] = []
    if qa_arg:
        candidates.append(Path(qa_arg))
    candidates += [site_dir / "qa_report.json", Path(f"qa_{site_dir.name}.json"),
                   Path("qa_report.json")]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")), p
            except json.JSONDecodeError:
                return None, p
    return None, None


def verify_qa(qa: dict | None, min_score: int) -> tuple[bool, str]:
    if not isinstance(qa, dict) or not qa:
        return False, "no qa_report found — run Bot 6 (qa_bot.py) first"
    if not qa.get("passed"):
        return False, (f"QA did not pass (score={qa.get('score')}). "
                       "Fix issues in Bot 5 and re-run QA — deploy blocked.")
    try:
        s = float(qa.get("score", 0))
    except (TypeError, ValueError):
        s = 0
    if s < min_score:
        return False, f"QA score {s} below minimum {min_score} — deploy blocked."
    return True, ""


def deploy_vercel(site_dir: Path) -> tuple[str, str]:
    """Returns (preview_url, deployment_id). Raises RuntimeError."""
    try:
        proc = subprocess.run(["vercel", "deploy", "--yes", "--cwd", str(site_dir)],
                              capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        raise RuntimeError("Vercel CLI not found (npm i -g vercel). Use --provider local.")
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    urls = re.findall(r"https://[A-Za-z0-9\-.]+\.vercel\.app[^\s]*", out)
    if proc.returncode != 0 or not urls:
        raise RuntimeError(f"Vercel deploy failed: {out[-800:]}")
    return urls[-1], f"vercel_{uuid.uuid4().hex[:8]}"


def deploy_render(site_dir: Path) -> tuple[str, str]:
    """Static deploy via Render API. Raises RuntimeError if unconfigured."""
    api_key = os.environ.get("RENDER_API_KEY", "")
    service_id = os.environ.get("RENDER_SERVICE_ID", "")
    if not api_key or not service_id:
        raise RuntimeError("Render needs RENDER_API_KEY + RENDER_SERVICE_ID env vars. "
                           "Use --provider local or vercel.")
    import urllib.request
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{service_id}/deploys",
        data=json.dumps({"clearCache": "clear"}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Render API error: {e}")
    dep_id = str(payload.get("id", f"render_{uuid.uuid4().hex[:8]}"))
    url = os.environ.get("RENDER_SERVICE_URL", f"https://{service_id}.onrender.com")
    return url, dep_id


def deploy_local(site_dir: Path, lead_id: str) -> tuple[str, str]:
    dest = Path("deployments") / lead_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(site_dir, dest)
    return (dest / "index.html").resolve().as_uri(), f"local_{uuid.uuid4().hex[:8]}"


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Bot 7: deploy QA-approved site (QA gate enforced)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--site", default=None, help="Path to generated_sites/<lead_id>")
    g.add_argument("--lead", default=None, help="Lead id under --sites-dir")
    p.add_argument("--sites-dir", default="generated_sites")
    p.add_argument("--qa-report", default=None, help="Explicit qa_report.json path")
    p.add_argument("--provider", default="auto", choices=["auto", "vercel", "render", "local"])
    p.add_argument("--output", "-o", default=None, help="Deployment record path")
    p.add_argument("--min-score", type=int, default=80)
    p.add_argument("--force", action="store_true",
                   help="Deploy even if QA failed (recorded as deployed_forced)")
    return p.parse_args(argv)


def main(argv=None, **kwargs) -> str | int:
    """Deploy a QA-approved site. Returns the deployment record path (str) or int exit code.

    Orchestrator use: ``main(site="generated_sites/lead_00001", provider="local")`` —
    any keyword matching an argparse option overrides the default. A bare main()
    call uses defaults (sys.argv is only used via the CLI). QA-gate block returns 3.
    """
    if argv is None:
        # Plain main() uses defaults (never sys.argv); the CLI passes
        # sys.argv[1:] explicitly via the __main__ block below.
        argv = []
    args = parse_args(argv)
    for _k, _v in kwargs.items():
        if not hasattr(args, _k):
            raise TypeError(f"deployment_manager.main() got an unexpected option {_k!r}")
        setattr(args, _k, _v)
    site_dir = Path(args.site) if args.site else (Path(args.sites_dir) / (args.lead or ""))
    if not args.site and not args.lead:
        print("[deployment_manager] ERROR: pass --site or --lead", file=sys.stderr)
        return 2
    if not site_dir.exists() or not (site_dir / "index.html").exists():
        print(f"[deployment_manager] ERROR: site not found: {site_dir}", file=sys.stderr)
        return 2
    lead_id = site_dir.name
    qa, qa_path = load_qa(site_dir, args.qa_report)
    ok, reason = verify_qa(qa, args.min_score)
    if not ok and not args.force:
        print(f"[deployment_manager] BLOCKED: {reason}", file=sys.stderr)
        print("[deployment_manager] CRITICAL RULE: Bot 7 cannot deploy without Bot 6 green light.",
              file=sys.stderr)
        return 3
    forced = not ok and args.force
    if forced:
        print(f"[deployment_manager] WARNING: overriding QA gate (--force): {reason}", flush=True)

    provider = args.provider
    if provider == "auto":
        provider = "vercel" if shutil.which("vercel") else "local"
        print(f"[deployment_manager] auto-selected provider: {provider}", flush=True)
    try:
        if provider == "vercel":
            url, dep_id = deploy_vercel(site_dir)
        elif provider == "render":
            url, dep_id = deploy_render(site_dir)
        else:
            url, dep_id = deploy_local(site_dir, lead_id)
    except RuntimeError as e:
        print(f"[deployment_manager] ERROR: {e}", file=sys.stderr)
        return 2

    record = {"lead_id": lead_id,
              "status": "deployed_forced" if forced else "deployed",
              "preview_url": url, "deployment_id": dep_id,
              "deployed_at": utc_now_iso(), "provider": provider,
              "qa_score": (qa or {}).get("score"),
              "qa_report": str(qa_path) if qa_path else None}
    out = Path(args.output) if args.output else (Path("deployments") / f"{lead_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[deployment_manager] {record['status']} {lead_id} via {provider}", flush=True)
    print(f"[deployment_manager] preview_url: {url}", flush=True)
    print(f"[deployment_manager] record -> {out}", flush=True)
    return str(out)


if __name__ == "__main__":
    _rc = main(sys.argv[1:])
    raise SystemExit(_rc if isinstance(_rc, int) else 0)
