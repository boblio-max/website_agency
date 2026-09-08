"""
website_classifier.py (Bot 2) — Split businesses by website presence.

Pipeline:
    businesses.json
           │
           ↓
    website_classifier.py   (this file; pure local filter, no network)
           │
           ├───────────────┐
           ↓               ↓
      has website      no website
           ↓               ↓
    with_websites.json  without_websites.json

It does NOT:
- visit the website
- analyze design / mobile / performance
- use AI
- decide whether to target the business

It only checks whether the `website` field is present and non-empty.

Usage:
    python website_classifier.py businesses.json
    python website_classifier.py businesses.json --with with_websites.json --without without_websites.json
    python website_classifier.py --input businesses.json --with businesses_with_websites.json --without businesses_without_websites.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLACEHOLDER_VALUES = {"", "null", "none", "n/a", "na", "-", "--", "nan", "undefined"}


def has_website(record: dict) -> bool:
    """Return True if record has a usable website value.

    Strictly a presence check — no HTTP requests, no validation of
    whether the site actually loads.
    """
    if not isinstance(record, dict):
        return False
    value = record.get("website")
    if value is None:
        return False
    if not isinstance(value, str):
        # Non-string truthy values (rare) count as present if non-empty.
        return bool(str(value).strip())
    text = value.strip()
    if text.lower() in PLACEHOLDER_VALUES:
        return False
    if len(text) < 4:  # shortest plausible: "a.io", "t.co"
        return False
    # Require at least a dot (domain) or an http(s) scheme.
    lowered = text.lower()
    if lowered.startswith(("http://", "https://")):
        return len(text) > len("https://") + 2
    return "." in text


def load_businesses(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Accept bare list (normal), {"businesses": [...]} wrapper, or single object.
    if isinstance(raw, dict):
        for key in ("businesses", "results", "data", "items"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON list of businesses")
    return [r for r in raw if isinstance(r, dict)]


def classify(businesses: list[dict]) -> tuple[list[dict], list[dict]]:
    with_sites = [b for b in businesses if has_website(b)]
    without_sites = [b for b in businesses if not has_website(b)]
    return with_sites, without_sites


def write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Split businesses.json into with/without websites (no network, no AI).")
    p.add_argument("input", nargs="?", default="businesses.json", help="Input JSON (default: businesses.json)")
    p.add_argument("--input", "-i", dest="input_opt", default=None, help="Same as positional input")
    p.add_argument("--with", dest="with_path", default="with_websites.json",
                   help="Output for businesses WITH a website (default: with_websites.json)")
    p.add_argument("--without", dest="without_path", default="without_websites.json",
                   help="Output for businesses WITHOUT a website (default: without_websites.json)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, **kwargs) -> tuple[str, str] | int:
    """Split input into with/without-website files.

    Returns ``(with_path, without_path)`` as str on success, int exit code on
    error. Orchestrator use: ``main(input="businesses.json")`` — any keyword
    matching an argparse option (input, with_path, without_path, ...) overrides
    the default. A bare main() call uses defaults (sys.argv is only used via the CLI).
    """
    if argv is None:
        # Plain main() uses defaults (never sys.argv); the CLI passes
        # sys.argv[1:] explicitly via the __main__ block below.
        argv = []
    args = parse_args(argv)
    for _k, _v in kwargs.items():
        if not hasattr(args, _k):
            raise TypeError(f"website_classifier.main() got an unexpected option {_k!r}")
        setattr(args, _k, _v)
    in_path = Path(args.input_opt or args.input)
    with_path = Path(args.with_path)
    without_path = Path(args.without_path)

    if not in_path.exists():
        print(f"[website_classifier] ERROR: input not found: {in_path}", file=sys.stderr)
        return 2

    try:
        businesses = load_businesses(in_path)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[website_classifier] ERROR reading {in_path}: {e}", file=sys.stderr)
        return 2

    with_sites, without_sites = classify(businesses)
    write_json(with_path, with_sites)
    write_json(without_path, without_sites)

    print(f"[website_classifier] input: {in_path} ({len(businesses)} total)", flush=True)
    print(f"[website_classifier] with website -> {with_path} ({len(with_sites)})", flush=True)
    
    print(f"[website_classifier] without website -> {without_path} ({len(without_sites)})", flush=True)
    return str(with_path), str(without_path)


if __name__ == "__main__":
    _rc = main(sys.argv[1:])
    raise SystemExit(_rc if isinstance(_rc, int) else 0)
