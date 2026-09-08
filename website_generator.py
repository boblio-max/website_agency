"""
website_generator.py (Bot 5) — Build a real working website per target lead.

Inputs:
    target_leads.json (+ business info; plus website_analysis when the
    lead comes from bad_websites.json)

Process:
    no-website lead:   business info → OpenCode → new website
    bad-website lead:  business info + existing problems → OpenCode →
                       completely improved website

    The bot creates generated_sites/<lead_id>/ and calls
    run_opencode_command(target_dir, prompt). If the OpenCode CLI is
    unavailable (or --no-opencode), it falls back to a built-in
    responsive template so the pipeline stays testable offline.

Output:
    generated_sites/
    └── <lead_id>/
        ├── index.html
        ├── styles.css
        ├── script.js
        └── meta.json

    The goal is an actual working website, not a description of one.

Usage:
    python website_generator.py --lead lead_00001
    python website_generator.py --all --limit 5
    python website_generator.py --lead lead_00001 --force --no-opencode
    python website_generator.py --lead lead_00001 --feedback feedback.json  (Bot 10 revision)
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:  # Windows consoles default to cp1252; keep unicode output from crashing
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

OPENCODE_CMD = "opencode"


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def esc(s) -> str:
    return htmlmod.escape(str(s or ""), quote=True)


# ---------------------------------------------------------------------------
# OpenCode bridge
# ---------------------------------------------------------------------------

def run_opencode_command(target_dir: Path, prompt: str, timeout: int = 600) -> str:
    """Run OpenCode in target_dir with prompt; return stdout.

    Uses `opencode run "<prompt>"`. Raises RuntimeError if the CLI is
    missing or exits non-zero — caller falls back to the template engine.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [OPENCODE_CMD, "run", prompt],
            cwd=str(target_dir), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError(f"OpenCode CLI '{OPENCODE_CMD}' not found on PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("OpenCode run timed out")
    if proc.returncode != 0:
        raise RuntimeError(f"OpenCode exited {proc.returncode}: {(proc.stderr or '')[:500]}")
    return proc.stdout or ""


def build_prompt(b: dict, feedback: dict | None) -> str:
    name = b.get("name") or "Local Business"
    category = b.get("category") or "local business"
    address = b.get("address") or ""
    phone = b.get("phone") or ""
    rating = b.get("rating")
    reviews = b.get("review_count")
    problems = (b.get("website_analysis") or {}).get("problems") or []
    lines = [
        f"Build a complete, professional, mobile-responsive small-business website for '{name}' ({category}).",
        f"Business details: address='{address}', phone='{phone}', "
        f"rating={rating} ({reviews} reviews)." if (rating or reviews) else
        f"Business details: address='{address}', phone='{phone}'.",
        "Output exactly three files in the current directory: index.html, styles.css, script.js.",
        "Requirements: semantic HTML with <nav>, <h1>, CTA buttons (Call Now, Get a Quote, Book Appointment),",
        "tel: link, contact form with validation, viewport meta, responsive CSS with media queries,",
        "meta description, favicon (inline SVG data URI is fine), alt text on images, readable typography.",
        "Use only vanilla HTML/CSS/JS, no external build step. Do not invent a different business name,",
        "address, or phone number — use exactly what is given. Reply with a one-line summary when done.",
    ]
    if problems:
        lines.append("The old site had these problems — every one must be fixed: " + "; ".join(problems))
    if feedback and feedback.get("requested_changes"):
        lines.append("CLIENT REVISION REQUEST — apply each item: "
                     + "; ".join(feedback["requested_changes"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback template engine (offline)
# ---------------------------------------------------------------------------

def render_template(b: dict, feedback: dict | None) -> dict[str, str]:
    name = b.get("name") or "Local Business"
    category = b.get("category") or "Local Business"
    address = b.get("address") or "Contact us for our location"
    phone = (b.get("phone") or "").strip()
    rating = b.get("rating")
    reviews = b.get("review_count")
    maps_url = b.get("maps_url") or "#"
    problems = (b.get("website_analysis") or {}).get("problems") or []
    changes = (feedback or {}).get("requested_changes") or []

    tel = "tel:" + "".join(c for c in phone if c.isdigit() or c == "+") if phone else "#contact"
    rating_block = (f'<p class="rating">★ {rating} <span>({reviews} Google reviews)</span></p>'
                    if rating else "")
    fixes_block = ("<section class='fixes'><h2>What we improved</h2><ul>"
                   + "".join(f"<li>Fixed: {esc(p)}</li>" for p in problems) + "</ul></section>"
                   if problems else "")
    rev_block = ("<section class='revisions'><h2>Latest updates per your feedback</h2><ul>"
                 + "".join(f"<li>{esc(c)}</li>" for c in changes) + "</ul></section>"
                 if changes else "")

    index = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(name)} — {esc(category)}. Call today for a free estimate.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>★</text></svg>">
<title>{esc(name)} — {esc(category)}</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header class="site-header">
  <nav aria-label="Main navigation">
    <a class="brand" href="#top">{esc(name)}</a>
    <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false">☰</button>
    <ul class="nav-links">
      <li><a href="#services">Services</a></li>
      <li><a href="#about">About</a></li>
      <li><a href="#reviews">Reviews</a></li>
      <li><a href="#contact">Contact</a></li>
    </ul>
    <a class="btn btn-primary" href="{esc(tel)}">Call Now{((' — ' + esc(phone)) if phone else '')}</a>
  </nav>
</header>
<main id="top">
  <section class="hero">
    <h1>{esc(name)}</h1>
    <p class="tagline">Trusted {esc(category)} — quality work, fair prices.</p>
    {rating_block}
    <div class="cta-row">
      <a class="btn btn-primary" href="{esc(tel)}">Get a Free Quote</a>
      <a class="btn btn-secondary" href="#contact">Book an Appointment</a>
    </div>
  </section>
  <section id="services"><h2>Our Services</h2>
    <ul class="cards">
      <li><h3>Repairs &amp; Service</h3><p>Fast, reliable {esc(category)} services with clear pricing.</p></li>
      <li><h3>Inspections</h3><p>Thorough inspections with honest recommendations.</p></li>
      <li><h3>Maintenance</h3><p>Preventive care that saves you money long-term.</p></li>
    </ul>
  </section>
  <section id="about"><h2>About Us</h2>
    <p>Locally owned {esc(category)} serving our community at {esc(address)}.</p>
  </section>
  <section id="reviews"><h2>Customer Reviews</h2>{rating_block or '<p>Ask us about recent customer feedback.</p>'}</section>
  {fixes_block}
  {rev_block}
  <section id="contact"><h2>Contact Us</h2>
    <address>{esc(address)}<br>{('<a href="' + esc(tel) + '">' + esc(phone) + '</a><br>') if phone else ''}<a href="{esc(maps_url)}" rel="noopener">Find us on Google Maps</a></address>
    <form id="quote-form" novalidate>
      <label>Name<input name="name" required autocomplete="name"></label>
      <label>Phone<input name="phone" type="tel" required autocomplete="tel"></label>
      <label>Message<textarea name="message" rows="4" required></textarea></label>
      <button class="btn btn-primary" type="submit">Request Callback</button>
      <p class="form-note" role="status" aria-live="polite"></p>
    </form>
  </section>
</main>
<footer><p>© {datetime.datetime.now().year} {esc(name)} · {esc(address)}</p></footer>
<script src="script.js"></script>
</body>
</html>
"""
    css = """:root{--brand:#0b5fff;--ink:#1a1a1a;--bg:#fff;--muted:#f4f6fb}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);line-height:1.6}
.site-header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid #e5e8f0;z-index:10}
nav{max-width:1000px;margin:auto;display:flex;gap:1rem;align-items:center;padding:.75rem 1rem;flex-wrap:wrap}
.brand{font-weight:800;text-decoration:none;color:var(--ink);margin-right:auto}
.nav-links{display:flex;gap:1rem;list-style:none;margin:0;padding:0}
.nav-links a{text-decoration:none;color:var(--ink)}
.nav-toggle{display:none;background:none;border:1px solid #ccc;border-radius:.5rem;padding:.25rem .6rem;font-size:1.1rem}
.btn{display:inline-block;padding:.7rem 1.2rem;border-radius:.6rem;text-decoration:none;font-weight:700}
.btn-primary{background:var(--brand);color:#fff}.btn-secondary{border:2px solid var(--brand);color:var(--brand)}
.hero{max-width:1000px;margin:auto;padding:3rem 1rem;text-align:center}
.rating{font-size:1.2rem}.cta-row{display:flex;gap:.75rem;justify-content:center;flex-wrap:wrap;margin-top:1rem}
section{max-width:1000px;margin:auto;padding:2rem 1rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;list-style:none;padding:0}
.cards li{background:var(--muted);border-radius:.75rem;padding:1rem}
form{display:grid;gap:.75rem;max-width:480px}input,textarea{width:100%;padding:.6rem;border:1px solid #bbb;border-radius:.5rem;font:inherit}
footer{text-align:center;padding:2rem;color:#555}
@media(max-width:640px){.nav-links{display:none;width:100%;flex-direction:column}.nav-links.open{display:flex}.nav-toggle{display:block}.hero{padding:2rem 1rem}}
"""
    js = """document.querySelector('.nav-toggle').addEventListener('click',e=>{const l=document.querySelector('.nav-links');const open=l.classList.toggle('open');e.currentTarget.setAttribute('aria-expanded',open)});
document.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',e=>{const t=document.querySelector(a.getAttribute('href'));if(t){e.preventDefault();t.scrollIntoView({behavior:'smooth'})}}));
document.getElementById('quote-form').addEventListener('submit',e=>{e.preventDefault();const f=e.target;const note=f.querySelector('.form-note');if(!f.name.value.trim()||!f.phone.value.trim()||!f.message.value.trim()){note.textContent='Please fill in every field.';return}note.textContent='Thanks! We will call you back shortly.';f.reset()});
"""
    return {"index.html": index, "styles.css": css, "script.js": js}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def load_leads(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for k in ("leads", "businesses", "results", "data"):
            if isinstance(raw.get(k), list):
                raw = raw[k]
                break
        else:
            raw = [raw]
    return [r for r in raw if isinstance(r, dict)]


def select_leads(leads: list[dict], lead_id: str | None, limit: int) -> list[dict]:
    if lead_id:
        hit = [l for l in leads if l.get("lead_id") == lead_id]
        if not hit:
            raise ValueError(f"lead {lead_id} not in {len(leads)} leads")
        return hit
    return leads[:limit] if limit and limit > 0 else leads


def generate_one(lead: dict, out_root: Path, feedback: dict | None,
                 use_opencode: bool, force: bool) -> dict:
    lid = lead.get("lead_id") or "lead_unknown"
    target = out_root / lid
    if target.exists() and (target / "index.html").exists() and not force:
        return {"lead_id": lid, "dir": str(target), "skipped": True, "engine": "cached"}
    target.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(lead, feedback)
    engine = "template"
    if use_opencode:
        try:
            run_opencode_command(target, prompt)
            if (target / "index.html").exists():
                engine = "opencode"
            else:
                raise RuntimeError("OpenCode finished but index.html missing")
        except RuntimeError as e:
            print(f"[website_generator] {lid}: OpenCode unavailable ({e}) — using template", flush=True)
            files = render_template(lead, feedback)
            for name, content in files.items():
                (target / name).write_text(content, encoding="utf-8")
    else:
        files = render_template(lead, feedback)
        for name, content in files.items():
            (target / name).write_text(content, encoding="utf-8")
    meta = {"lead_id": lid, "business": {k: lead.get(k) for k in
            ("name", "category", "address", "phone", "website", "rating", "review_count")},
            "lead_type": lead.get("lead_type"), "opportunity_score": lead.get("opportunity_score"),
            "engine": engine, "created_at": utc_now_iso(),
            "feedback_applied": bool(feedback and feedback.get("requested_changes"))}
    (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"lead_id": lid, "dir": str(target), "skipped": False, "engine": engine}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Bot 5: build working sites -> generated_sites/<lead_id>/")
    p.add_argument("--leads", default="target_leads.json")
    p.add_argument("--lead", default=None, help="Single lead_id to build")
    p.add_argument("--all", action="store_true", help="Build all leads (default if no --lead)")
    p.add_argument("--limit", type=int, default=0, help="Max sites to build (0 = all)")
    p.add_argument("--output-dir", default="generated_sites")
    p.add_argument("--force", action="store_true", help="Regenerate even if index.html exists")
    p.add_argument("--no-opencode", action="store_true", help="Skip OpenCode, use template directly")
    p.add_argument("--feedback", default=None, help="Bot 10 feedback JSON path (revision requests)")
    return p.parse_args(argv)


def main(argv=None, **kwargs) -> str | int:
    """Build working sites. Returns the sites root dir (str) or int exit code.

    Orchestrator use: ``main(leads="target_leads.json", output_dir="generated_sites",
    lead="lead_00001")`` — any keyword matching an argparse option overrides the
    default. A bare main() call uses defaults (sys.argv is only used via the CLI).
    """
    if argv is None:
        # Plain main() uses defaults (never sys.argv); the CLI passes
        # sys.argv[1:] explicitly via the __main__ block below.
        argv = []
    args = parse_args(argv)
    for _k, _v in kwargs.items():
        if not hasattr(args, _k):
            raise TypeError(f"website_generator.main() got an unexpected option {_k!r}")
        setattr(args, _k, _v)
    leads_path = Path(args.leads)
    if not leads_path.exists():
        print(f"[website_generator] ERROR: {leads_path} not found", file=sys.stderr)
        return 2
    try:
        leads = load_leads(leads_path)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[website_generator] ERROR: {e}", file=sys.stderr)
        return 2
    try:
        selected = select_leads(leads, args.lead, args.limit)
    except ValueError as e:
        print(f"[website_generator] ERROR: {e}", file=sys.stderr)
        return 2
    feedback = None
    if args.feedback:
        feedback = json.loads(Path(args.feedback).read_text(encoding="utf-8"))
    out_root = Path(args.output_dir)
    print(f"[website_generator] building {len(selected)} site(s) via "
          f"{'template' if args.no_opencode else 'opencode→template fallback'}", flush=True)
    built, skipped = 0, 0
    for lead in selected:
        res = generate_one(lead, out_root, feedback, not args.no_opencode, args.force)
        if res["skipped"]:
            skipped += 1
            print(f"[website_generator] skip {res['lead_id']} (exists, use --force)", flush=True)
        else:
            built += 1
            print(f"[website_generator] built {res['lead_id']} [{res['engine']}] -> {res['dir']}", flush=True)
    print(f"[website_generator] done: {built} built, {skipped} skipped", flush=True)
    return str(out_root)


if __name__ == "__main__":
    _rc = main(sys.argv[1:])
    raise SystemExit(_rc if isinstance(_rc, int) else 0)
