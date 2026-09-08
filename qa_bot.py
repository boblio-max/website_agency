"""
qa_bot.py (Bot 6) — Independently judge whether a Bot 5 site is deployable.

Input:
    generated_sites/<lead_id>/   (index.html + styles.css + script.js)

Inspects (critical, independent of Bot 5):
    visual quality · desktop layout · mobile layout · navigation ·
    buttons/links · forms · content accuracy · responsiveness ·
    accessibility · performance · broken elements · professionalism

Output (single lead):
    {"passed": true, "score": 94, "issues": [], "recommendations": [...], ...}

If it fails:
    {"passed": false, "score": 71,
     "issues": ["Mobile navigation overlaps hero content", ...], ...}

A failed QA stops the pipeline (exit code 1) — no automatic retry loop.

Usage:
    python qa_bot.py --site generated_sites/lead_00001
    python qa_bot.py --lead lead_00001 --sites-dir generated_sites --leads target_leads.json
    python qa_bot.py --all --sites-dir generated_sites --output qa_reports.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

try:  # Windows consoles default to cp1252; keep unicode output from crashing
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

PASS_THRESHOLD = 80


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_lead(leads_path: Path | None, lead_id: str) -> dict:
    if not leads_path or not leads_path.exists():
        return {}
    try:
        raw = json.loads(leads_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(raw, dict):
        for k in ("leads", "businesses", "results", "data"):
            if isinstance(raw.get(k), list):
                raw = raw[k]
                break
    for r in (raw if isinstance(raw, list) else []):
        if isinstance(r, dict) and r.get("lead_id") == lead_id:
            return r
    return {}


def check_site(site_dir: Path, lead: dict, threshold: int) -> dict:
    issues: list[str] = []
    recommendations: list[str] = []
    details: dict = {}
    score = 100
    lid = lead.get("lead_id") or site_dir.name

    def penalize(points: int, issue: str, recommendation: str = ""):
        nonlocal score
        score -= points
        issues.append(issue)
        if recommendation:
            recommendations.append(recommendation)

    index = site_dir / "index.html"
    css_p = site_dir / "styles.css"
    js_p = site_dir / "script.js"
    for f, w in ((index, 25), (css_p, 8), (js_p, 5)):
        if not f.exists():
            penalize(w, f"Missing required file: {f.name}",
                     f"Bot 5 must generate {f.name} before deploy")

    html = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
    css = css_p.read_text(encoding="utf-8", errors="replace") if css_p.exists() else ""
    js = js_p.read_text(encoding="utf-8", errors="replace") if js_p.exists() else ""
    soup = BeautifulSoup(html, "html.parser") if html else None
    details["bytes"] = {"html": len(html), "css": len(css), "js": len(js),
                        "total_kb": round((len(html) + len(css) + len(js)) / 1024, 1)}

    if soup is None:
        return {"lead_id": lid, "passed": False, "score": 0, "issues": issues,
                "recommendations": recommendations, "checked_at": utc_now_iso(),
                "site_dir": str(site_dir), "details": details}

    # -- Document basics ------------------------------------------------
    if not re.match(r"\s*<!doctype html>", html[:200], re.I):
        penalize(4, "Missing or invalid <!DOCTYPE html>", "Start index.html with <!DOCTYPE html>")
    html_tag = soup.find("html")
    if not html_tag or not (html_tag.get("lang") or "").strip():
        penalize(3, "Missing lang attribute on <html>", 'Add lang="en" for accessibility/SEO')
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    if len(title) < 5:
        penalize(4, "Missing/empty <title>", "Add a descriptive title with the business name")
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if not meta_desc or not (meta_desc.get("content") or "").strip():
        penalize(3, "Missing meta description", "Add <meta name='description'> for SEO")
    h1s = soup.find_all("h1")
    if len(h1s) == 0:
        penalize(5, "No <h1> heading", "Add exactly one <h1> with the business name")
    elif len(h1s) > 1:
        penalize(2, "Multiple <h1> headings", "Keep a single <h1>; use <h2> for sections")

    # -- Responsive / mobile ---------------------------------------------
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    if not viewport:
        penalize(10, "No viewport meta — mobile layout will break",
                 "Add <meta name='viewport' content='width=device-width, initial-scale=1'>")
    if not re.search(r"@media", css):
        penalize(8, "No responsive CSS breakpoints", "Add @media queries for small screens")
        recommendations.append("Verify the mobile nav toggle works at 360px width")
    if "nav-toggle" in html and "open" not in js and "toggle" not in js.lower():
        penalize(4, "Mobile navigation overlaps hero content (toggle has no JS handler)",
                 "Wire .nav-toggle to open/close .nav-links in script.js")

    # -- Navigation / buttons / links --------------------------------------
    nav = soup.find("nav")
    links = soup.find_all("a", href=True)
    if not nav:
        penalize(5, "Missing <nav> landmark", "Wrap main links in <nav aria-label='Main navigation'>")
    if len(links) < 3:
        penalize(4, "Too few navigable links", "Add Services / About / Reviews / Contact links")
    if not soup.find("a", href=re.compile(r"^tel:", re.I)):
        penalize(5, "No tel: call link", "Add a Call Now button with href='tel:+1...'")
    cta_text = soup.get_text(" ", strip=True)
    if not re.search(r"call|quote|book|schedule|appointment|contact", cta_text, re.I):
        penalize(4, "CTA button has insufficient prominence", "Add a visible Call/Quote/Book button above the fold")

    # -- Forms ---------------------------------------------------------------
    forms = soup.find_all("form")
    if not forms:
        penalize(5, "No contact/quote form", "Add a contact form with name/phone/message + validation")
    else:
        for f in forms:
            inputs = f.find_all(["input", "textarea"])
            unlabeled = [i for i in inputs if not (i.get("aria-label") or i.get("id"))
                         and not f.find("label")]
            if unlabeled:
                penalize(2, "Form inputs missing labels", "Associate each input with a <label>")
                break
            if not any(i.has_attr("required") for i in inputs):
                penalize(1, "Form has no required-field validation", "Mark required fields + JS check")
                break

    # -- Content accuracy (vs lead data) ---------------------------------------
    name = (lead.get("name") or "").strip()
    if name and name.lower() not in soup.get_text(" ", strip=True).lower():
        penalize(6, f"Business name '{name}' not found in page content",
                 "Use the exact business name from target_leads.json — do not invent one")
    phone = "".join(c for c in (lead.get("phone") or "") if c.isdigit())
    if phone and phone[-7:] not in re.sub(r"\D", "", soup.get_text()):
        penalize(4, "Business phone number missing from page", "Render the exact lead phone number")

    # -- Accessibility -----------------------------------------------------------
    imgs_no_alt = [i for i in soup.find_all("img") if not (i.get("alt") or "").strip()]
    if imgs_no_alt:
        penalize(3, f"{len(imgs_no_alt)} image(s) missing alt text", "Add descriptive alt attributes")
    if re.search(r"<button[^>]*>\s*</button>", html):
        penalize(2, "Empty <button> element", "Give every button visible text")
    m = re.search(r"\.btn-primary\s*\{([^}]*)\}", css)
    if m and not ("background" in m.group(1) and "color" in m.group(1)):
        penalize(2, "CTA button has insufficient contrast definition",
                 "Set both background and color on .btn-primary (contrast ≥ 4.5:1)")

    # -- Performance ---------------------------------------------------------------
    if details["bytes"]["total_kb"] > 500:
        penalize(4, f"Page weight {details['bytes']['total_kb']}KB is heavy",
                 "Compress images, drop unused CSS/JS")
    if len(re.findall(r"<img", html, re.I)) > 15:
        penalize(2, "Many unoptimized images", "Lazy-load below-fold images (loading='lazy')")

    # -- Broken local elements -------------------------------------------------------
    for tag, attr in (("a", "href"), ("img", "src"), ("link", "href"), ("script", "src")):
        for el in soup.find_all(tag, **{attr: True}):
            ref = (el.get(attr) or "").strip()
            if not ref or ref.startswith(("#", "http", "https:", "mailto:", "tel:", "data:")):
                continue
            if not (site_dir / ref.split("?")[0].split("#")[0]).exists():
                penalize(3, f"Broken {tag} reference: {ref}", f"Fix or remove the dead '{ref}' link")
                break

    score = max(0, min(100, score))
    passed = score >= threshold
    if not passed:
        recommendations.append("Fix the issues above in Bot 5, then re-run QA (no auto-loop)")
    return {"lead_id": lid, "passed": passed, "score": score, "issues": issues,
            "recommendations": sorted(set(recommendations)), "checked_at": utc_now_iso(),
            "site_dir": str(site_dir), "details": details}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Bot 6: QA a generated site (fail stops pipeline)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--site", default=None, help="Path to generated_sites/<lead_id>")
    g.add_argument("--lead", default=None, help="Lead id (resolved under --sites-dir)")
    p.add_argument("--all", action="store_true", help="QA every site under --sites-dir")
    p.add_argument("--sites-dir", default="generated_sites")
    p.add_argument("--leads", default="target_leads.json", help="For content-accuracy checks")
    p.add_argument("--threshold", "-t", type=int, default=PASS_THRESHOLD)
    p.add_argument("--output", "-o", default="qa_report.json",
                   help="Report path for single-site mode (multi-site: qa_reports.json)")
    return p.parse_args(argv)


def main(argv=None, **kwargs) -> str | int:
    """QA generated site(s). Returns the report path (str) when QA passes, int otherwise.

    Orchestrator use: ``main(site="generated_sites/lead_00001")`` or
    ``main(all=True)`` — any keyword matching an argparse option overrides the
    default. A bare main() call uses defaults (sys.argv is only used via the CLI).
    A failed gate returns 1 (no usable output); missing input returns 2.
    """
    if argv is None:
        # Plain main() uses defaults (never sys.argv); the CLI passes
        # sys.argv[1:] explicitly via the __main__ block below.
        argv = []
    args = parse_args(argv)
    for _k, _v in kwargs.items():
        if not hasattr(args, _k):
            raise TypeError(f"qa_bot.main() got an unexpected option {_k!r}")
        setattr(args, _k, _v)
    sites_root = Path(args.sites_dir)
    leads_path = Path(args.leads) if args.leads else None

    if args.all:
        if not sites_root.exists():
            print(f"[qa_bot] ERROR: {sites_root} not found", file=sys.stderr)
            return 2
        dirs = sorted(d for d in sites_root.iterdir()
                      if d.is_dir() and (d / "index.html").exists())
        if not dirs:
            print(f"[qa_bot] ERROR: no sites in {sites_root}", file=sys.stderr)
            return 2
        reports = [check_site(d, load_lead(leads_path, d.name), args.threshold) for d in dirs]
        for r in reports:
            (sites_root / r["lead_id"] / "qa_report.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        out = Path("qa_reports.json" if args.output == "qa_report.json" else args.output)
        out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        n_pass = sum(1 for r in reports if r["passed"])
        print(f"[qa_bot] {n_pass}/{len(reports)} passed (threshold {args.threshold}) -> {out}", flush=True)
        for r in reports:
            print(f"  {'PASS' if r['passed'] else 'FAIL'} {r['score']:3d} {r['lead_id']} "
                  f"({len(r['issues'])} issues)", flush=True)
        if n_pass != len(reports):
            return 1
        return str(out)

    site_dir = Path(args.site) if args.site else (sites_root / (args.lead or ""))
    if not args.site and not args.lead:
        print("[qa_bot] ERROR: pass --site or --lead (or --all)", file=sys.stderr)
        return 2
    if not site_dir.exists():
        print(f"[qa_bot] ERROR: site not found: {site_dir}", file=sys.stderr)
        return 2
    report = check_site(site_dir, load_lead(leads_path, site_dir.name), args.threshold)
    (site_dir / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "PASS" if report["passed"] else "FAIL"
    print(f"[qa_bot] {status} score={report['score']} {report['lead_id']} -> {args.output}", flush=True)
    for i in report["issues"]:
        print(f"  - {i}", flush=True)
    if not report["passed"]:
        print("[qa_bot] FAILED QA stops the pipeline (fix in Bot 5, re-run QA)", file=sys.stderr)
        return 1
    return str(Path(args.output))


if __name__ == "__main__":
    _rc = main(sys.argv[1:])
    raise SystemExit(_rc if isinstance(_rc, int) else 0)
