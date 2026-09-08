"""
data_merger.py — Merge two website_classifier.py outputs back into one list.

Pipeline:
    with_websites.json + without_websites.json
                    │
                    ↓
            data_merger.py (this file; pure local merge, no network)
                    │
                    ↓
              merged.json (or --output)

Each input is a JSON list of business dicts (as produced by
website_classifier.py / maps_scraper.py). A dict wrapper like
{"businesses": [...]} (also "results"/"data"/"items") or a single
object is also accepted.

Merge behavior:
- Concatenate in input order (file1 then file2).
- Deduplicate by default (same business appearing in both files keeps
  the first occurrence). Key prefers `maps_url`, else
  name/phone/website/address.
- Optionally sort by name.

Usage:
    python data_merger.py with_websites.json without_websites.json
    python data_merger.py with_websites.json without_websites.json --output businesses_merged.json
    python data_merger.py --input1 with_websites.json --input2 without_websites.json --output merged.json --no-dedupe
    python data_merger.py a.json b.json --sort name
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WRAPPER_KEYS = ("businesses", "results", "data", "items", "leads")


def load_list(path: Path) -> list[dict]:
    """Load a JSON list of business dicts, accepting wrapper/single-object forms."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for key in WRAPPER_KEYS:
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON list of businesses")
    return [r for r in raw if isinstance(r, dict)]


def dedupe_key(record: dict) -> str:
    """Stable identity for a business: maps_url wins, else name/phone/website/address."""
    maps_url = (record.get("maps_url") or "").strip().split("?")[0].lower()
    if maps_url:
        return f"url:{maps_url}"
    parts = "|".join((str(record.get(k) or "").strip().lower()) for k in ("name", "phone", "website", "address"))
    if parts.strip("|"):
        return f"fields:{parts}"
    # Fallback: full canonical JSON so distinct unknown shapes don't collapse.
    return f"json:{json.dumps(record, sort_keys=True, ensure_ascii=False)}"


def merge_lists(first: list[dict], second: list[dict], dedupe: bool = True) -> list[dict]:
    """Concatenate two lists, optionally dropping duplicates (first occurrence wins)."""
    if not dedupe:
        return [*first, *second]
    seen: set[str] = set()
    merged: list[dict] = []
    for record in (*first, *second):
        key = dedupe_key(record)
        if key in seen:
            continue
        seen.add(key)
        merged.append(record)
    return merged


def write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge two classifier JSON lists into one (no network).")
    p.add_argument("input1", nargs="?", default=None, help="First input JSON (e.g. with_websites.json)")
    p.add_argument("input2", nargs="?", default=None, help="Second input JSON (e.g. without_websites.json)")
    p.add_argument("--input1", dest="input1_opt", default=None, help="Same as positional input1")
    p.add_argument("--input2", dest="input2_opt", default=None, help="Same as positional input2")
    p.add_argument("--output", "-o", default="merged.json", help="Output merged JSON (default: merged.json)")
    p.add_argument("--no-dedupe", dest="dedupe", action="store_false", help="Keep duplicates instead of dropping them")
    p.add_argument("--sort", choices=["none", "name"], default="none",
                   help="Sort output: 'name' sorts by business name, 'none' keeps input order (default: none)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, **kwargs) -> str | int:
    """Merge two classifier JSON lists. Returns the output path (str) or int exit code.

    Orchestrator use: ``main(input1="with_websites.json", input2="without_websites.json",
    output="merged.json")`` — any keyword matching an argparse option overrides the
    default. A bare main() call uses defaults (sys.argv is only used via the CLI).
    """
    if argv is None:
        # Plain main() uses defaults (never sys.argv); the CLI passes
        # sys.argv[1:] explicitly via the __main__ block below.
        argv = []
    args = parse_args(argv)
    for _k, _v in kwargs.items():
        if not hasattr(args, _k):
            raise TypeError(f"data_merger.main() got an unexpected option {_k!r}")
        setattr(args, _k, _v)
    in1 = Path(args.input1_opt or args.input1) if (args.input1_opt or args.input1) else None
    in2 = Path(args.input2_opt or args.input2) if (args.input2_opt or args.input2) else None
    out_path = Path(args.output)

    if in1 is None or in2 is None:
        print("[data_merger] ERROR: two input paths required.", file=sys.stderr)
        print("[data_merger] usage: python data_merger.py <file1.json> <file2.json> [--output merged.json]",
              file=sys.stderr)
        return 2

    first: list[dict] = []
    second: list[dict] = []
    for label, in_path in (("input1", in1), ("input2", in2)):
        if not in_path.exists():
            print(f"[data_merger] ERROR: {label} not found: {in_path}", file=sys.stderr)
            return 2
        try:
            records = load_list(in_path)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[data_merger] ERROR reading {in_path}: {e}", file=sys.stderr)
            return 2
        if label == "input1":
            first = records
        else:
            second = records

    before = len(first) + len(second)
    merged = merge_lists(first, second, dedupe=args.dedupe)
    removed = before - len(merged)

    if args.sort == "name":
        merged.sort(key=lambda r: (str(r.get("name") or "").lower(), str(r.get("maps_url") or "")))

    write_json(out_path, merged)

    print(f"[data_merger] input1: {in1} ({len(first)})", flush=True)
    print(f"[data_merger] input2: {in2} ({len(second)})", flush=True)
    if args.dedupe:
        print(f"[data_merger] duplicates removed: {removed}", flush=True)
    print(f"[data_merger] merged -> {out_path} ({len(merged)})", flush=True)
    return str(out_path)


if __name__ == "__main__":
    result = main(sys.argv[1:])
    raise SystemExit(result if isinstance(result, int) else 0)
